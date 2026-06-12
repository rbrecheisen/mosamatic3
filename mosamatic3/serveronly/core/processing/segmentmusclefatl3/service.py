import json
import tempfile
import zipfile
import numpy as np
from io import BytesIO
from pathlib import Path
from celery.exceptions import Ignore

from ...common.dicom import load_dicom, get_pixels_from_dicom_object, is_dicom
from ...common.utils import normalize_between, convert_labels_to_157
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile, get_dataset_file_path, dataset_upload_root, safe_relative_path
from ...models import Dataset
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import SegmentMuscleFatL3TensorFlowTaskParameters


class ParamLoader:
    def __init__(self, json_path: Path):
        with open(json_path, encoding='utf-8') as f:
            self.__dict__.update(json.load(f))

    @property
    def dict(self):
        return self.__dict__


def find_model_files(model_dataset: Dataset, user_id: str, model_version: str) -> tuple[Path, Path | None, Path]:
    expected_model = f'model-{model_version}.zip'
    expected_contour_model = f'contour_model-{model_version}.zip'
    expected_params = f'params-{model_version}.json'

    model_path = None
    contour_model_path = None
    params_path = None

    for dataset_file in model_dataset.files.all():
        name = Path(dataset_file.relative_path).name
        path = get_dataset_file_path(user_id, model_dataset.id, dataset_file.relative_path)

        if name == expected_model:
            model_path = path
        elif name == expected_contour_model:
            contour_model_path = path
        elif name == expected_params:
            params_path = path

    missing = []
    if model_path is None:
        missing.append(expected_model)
    if params_path is None:
        missing.append(expected_params)

    if missing:
        raise RuntimeError(f'Missing model files: {", ".join(missing)}')

    return model_path, contour_model_path, params_path


def load_keras_model_from_zip(zip_path: Path):
    import tensorflow as tf

    temp_dir = tempfile.TemporaryDirectory(prefix='mosamatic3_tf_model_')
    model_root = Path(temp_dir.name)

    with zipfile.ZipFile(zip_path) as zip_file:
        zip_file.extractall(model_root)

    # Common case: zip directly contains saved_model.pb
    if (model_root / 'saved_model.pb').exists():
        model = tf.keras.models.load_model(model_root, compile=False)
        return model, temp_dir

    # Common case: zip contains one nested model directory
    candidates = list(model_root.rglob('saved_model.pb'))
    if not candidates:
        temp_dir.cleanup()
        raise RuntimeError(f'No saved_model.pb found inside {zip_path.name}')

    model_dir = candidates[0].parent
    model = tf.keras.models.load_model(model_dir, compile=False)
    return model, temp_dir


def load_models_and_params(model_dataset: Dataset, user_id: str, model_version: str):
    model_zip, contour_model_zip, params_json = find_model_files(model_dataset, user_id, model_version)

    model, model_temp_dir = load_keras_model_from_zip(model_zip)

    contour_model = None
    contour_temp_dir = None
    if contour_model_zip is not None:
        contour_model, contour_temp_dir = load_keras_model_from_zip(contour_model_zip)

    params = ParamLoader(params_json)

    return model, contour_model, params, [model_temp_dir, contour_temp_dir]


def extract_contour(image: np.ndarray, contour_model, params: ParamLoader) -> np.ndarray:
    ct = np.copy(image)
    ct = normalize_between(
        ct,
        params.dict['min_bound_contour'],
        params.dict['max_bound_contour'],
    )

    img = np.expand_dims(ct, 0)
    img = np.expand_dims(img, -1)

    pred = contour_model.predict([img], verbose=0)
    pred_squeeze = np.squeeze(pred)
    pred_max = pred_squeeze.argmax(axis=-1)

    return np.uint8(pred_max)


def segment_muscle_and_fat(image: np.ndarray, model, *, probabilities: bool = False) -> np.ndarray:
    img = np.expand_dims(image, 0)
    img = np.expand_dims(img, -1)

    pred = model.predict([img], verbose=0)
    pred_squeeze = np.squeeze(pred)

    if probabilities:
        return pred_squeeze

    return pred_squeeze.argmax(axis=-1)


def numpy_to_output_file(relative_path: str, array: np.ndarray) -> OutputDatasetFile:
    buffer = BytesIO()
    np.save(buffer, array)
    return OutputDatasetFile(relative_path=relative_path, content=buffer.getvalue())


def process_dicom_file(
    *,
    dicom_path: Path,
    relative_path: str,
    model,
    contour_model,
    model_params: ParamLoader,
    probabilities: bool,
    copy_input_dicoms: bool,
) -> list[OutputDatasetFile]:
    dicom_object = load_dicom(dicom_path)
    if dicom_object is None:
        return []

    pixels = get_pixels_from_dicom_object(dicom_object)

    if contour_model is not None:
        mask = extract_contour(pixels, contour_model, model_params)
        pixels = normalize_between(
            pixels,
            model_params.dict['min_bound'],
            model_params.dict['max_bound'],
        )
        pixels = pixels * mask
    else:
        pixels = normalize_between(
            pixels,
            model_params.dict['min_bound'],
            model_params.dict['max_bound'],
        )

    pixels = pixels.astype(np.float32)

    segmentation = segment_muscle_and_fat(
        pixels,
        model,
        probabilities=probabilities,
    )

    source_path = Path(relative_path)
    source_name = source_path.name
    safe_prefix = "_".join(source_path.parts[:-1])
    safe_prefix = safe_prefix.replace(" ", "_")
    flat_name = f"{safe_prefix}_{source_name}" if safe_prefix else source_name

    if probabilities:
        segmentation_relative_path = f'{flat_name}_prob.seg.npy'
    else:
        segmentation = convert_labels_to_157(segmentation)
        segmentation_relative_path = f'{flat_name}.seg.npy'

    output_files = [
        numpy_to_output_file(segmentation_relative_path, segmentation)
    ]

    if copy_input_dicoms:
        output_files.append(
            OutputDatasetFile(
                relative_path=f'{flat_name}',
                content=dicom_path.read_bytes(),
            )
        )

    return output_files


def normalize_path_prefix(prefix: str | None) -> str:
    value = (prefix or '').strip().replace('\\', '/').strip('/')
    return f'{value}/' if value else ''


def get_slice_select_manifest_selected_files(dataset: Dataset) -> list[str]:
    if dataset.source_task_key != 'sliceselect':
        return []

    manifest_path = (
        dataset_upload_root(dataset.owner_id, dataset.id)
        / safe_relative_path(SLICE_SELECT_MANIFEST_RELATIVE_PATH)
    )

    if not manifest_path.exists():
        return []

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception:
        return []

    selected_files: list[str] = []

    for scan in manifest.get('scans', {}).values():
        if scan.get('status') != 'completed':
            continue

        selected = scan.get('selected_slice_relative_output')
        if selected:
            selected_files.append(selected)

    existing_paths = set(dataset.files.values_list('relative_path', flat=True))
    return [path for path in selected_files if path in existing_paths]


def get_segment_input_dataset_files(dataset: Dataset, user_id: str, input_path_prefix: str):
    prefix = normalize_path_prefix(input_path_prefix)
    dataset_files = list(dataset.files.all())
    if prefix:
        dataset_files = [
            file
            for file in dataset_files
            if file.relative_path.replace('\\', '/').startswith(prefix)
        ]
    dicom_files = []
    for dataset_file in dataset_files:
        path = get_dataset_file_path(
            user_id,
            dataset.id,
            dataset_file.relative_path,
        )
        if is_dicom(path):
            dicom_files.append(dataset_file)
    return dicom_files


def run_segment_muscle_fat_l3_tensorflow_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(
        task_key='segmentmusclefatl3tensorflow',
        parameters=parameters,
        parameter_model=SegmentMuscleFatL3TensorFlowTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )

    params = runtime.params
    runtime.mark_running()

    temp_dirs = []

    try:
        image_dataset = runtime.get_input_dataset(params.dataset_id)
        model_dataset = runtime.get_input_dataset(params.model_files_dataset_id)

        runtime.update_progress(
            current=0,
            total=image_dataset.files.count(),
            message='Loading TensorFlow models',
        )

        model, contour_model, model_params, temp_dirs = load_models_and_params(
            model_dataset=model_dataset,
            user_id=user_id,
            model_version=params.model_version,
        )

        input_files = get_segment_input_dataset_files(
            image_dataset,
            user_id,
            params.input_path_prefix,
        )

        total = len(input_files)
        output_files: list[OutputDatasetFile] = []

        runtime.update_progress(
            current=0,
            total=total,
            message=f'Starting muscle/fat segmentation for {total} DICOM files',
        )

        for index, dataset_file in enumerate(input_files):
            current = index + 1

            runtime.check_cancelled(
                current=index,
                total=total,
                message=f'Segment muscle/fat task cancelled after {index} of {total} files',
            )

            dicom_path = get_dataset_file_path(
                user_id,
                image_dataset.id,
                dataset_file.relative_path,
            )

            files = process_dicom_file(
                dicom_path=dicom_path,
                relative_path=dataset_file.relative_path,
                model=model,
                contour_model=contour_model,
                model_params=model_params,
                probabilities=params.probabilities,
                copy_input_dicoms=params.copy_input_dicoms,
            )
            output_files.extend(files)

            runtime.update_progress(
                current=current,
                total=total,
                message=f'Segmented DICOM file {current} of {total}',
            )

        # total = image_dataset.files.count()
        # output_files: list[OutputDatasetFile] = []
        # runtime.update_progress(
        #     current=0,
        #     total=total,
        #     message=f'Starting muscle/fat segmentation for {total} DICOM files',
        # )
        # for item in runtime.iter_dataset_files(
        #     image_dataset,
        #     message_factory=lambda current, total: f'Segmented DICOM file {current} of {total}',
        # ):
        #     files = process_dicom_file(
        #         dicom_path=item.path,
        #         relative_path=item.file.relative_path,
        #         model=model,
        #         contour_model=contour_model,
        #         model_params=model_params,
        #         probabilities=params.probabilities,
        #         copy_input_dicoms=params.copy_input_dicoms,
        #     )
        #     output_files.extend(files)

        output_dataset = runtime.create_output_dataset(
            name=f'Segment Muscle/Fat L3 TensorFlow output - {image_dataset.name}',
            files=output_files,
        )

        runtime.update_progress(
            current=total,
            total=total,
            message='Finished muscle/fat segmentation',
        )
        runtime.mark_finished()

        return {
            'current': total,
            'total': total,
            'message': 'Segment muscle/fat L3 TensorFlow task completed',
            'parameters': params.model_dump(mode='json'),
            'output_datasets': [DatasetSerializer(output_dataset).data],
        }

    except Ignore:
        raise

    except Exception:
        runtime.mark_failed()
        raise

    finally:
        for temp_dir in temp_dirs:
            if temp_dir is not None:
                temp_dir.cleanup()