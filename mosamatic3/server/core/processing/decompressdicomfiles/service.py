from io import BytesIO

from celery.exceptions import Ignore

from ...common.dicom import load_dicom
from ...datasets.serializers import DatasetSerializer
from ...datasets.services import OutputDatasetFile
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import DecompressDicomFilesTaskParameters


def process_dicom_file(file_path, relative_path: str) -> tuple[OutputDatasetFile, bool]:
    """Return an uncompressed copy without changing the source file."""
    try:
        dicom = load_dicom(file_path)
        if dicom is None or 'PixelData' not in dicom:
            raise ValueError('The file is not a DICOM image containing Pixel Data')

        transfer_syntax = getattr(dicom.file_meta, 'TransferSyntaxUID', None)
        if transfer_syntax is None:
            raise ValueError('The DICOM image has no Transfer Syntax UID')

        decompressed = transfer_syntax.is_compressed
        if decompressed:
            # Preserve image identity and decoded sample values. Pydicom also
            # sets Explicit VR Little Endian and removes encapsulation.
            dicom.decompress(as_rgb=False, generate_instance_uid=False)
            buffer = BytesIO()
            dicom.save_as(buffer, enforce_file_format=True)
            content = buffer.getvalue()
        else:
            # An already uncompressed file must remain byte-for-byte identical.
            content = file_path.read_bytes()

        return OutputDatasetFile(relative_path=relative_path, content=content), decompressed
    except Exception as exc:
        raise ValueError(f'Cannot decompress DICOM file "{relative_path}": {exc}') from exc


def run_decompress_dicom_files_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(
        task_key='decompressdicomfiles',
        parameters=parameters,
        parameter_model=DecompressDicomFilesTaskParameters,
        user_id=user_id,
        celery_task=celery_task,
    )
    params = runtime.params
    runtime.mark_running()
    try:
        dataset = runtime.get_input_dataset(params.input_dataset_id)
        total = dataset.files.count()
        if total == 0:
            raise ValueError('The input dataset contains no DICOM files')

        runtime.update_progress(current=0, total=total, message='Starting DICOM decompression')
        output_files = []
        decompressed_count = 0
        copied_count = 0
        for item in runtime.iter_dataset_files(
            dataset,
            message_factory=lambda current, total: f'Processed {current} of {total} DICOM files',
        ):
            output_file, decompressed = process_dicom_file(item.path, item.file.relative_path)
            output_files.append(output_file)
            if decompressed:
                decompressed_count += 1
            else:
                copied_count += 1

        # Publish one complete dataset only after every input file succeeded.
        runtime.check_cancelled(current=total, total=total, message='DICOM decompression cancelled')
        output_dataset = runtime.create_output_dataset(
            name='Decompress DICOM Files output', files=output_files,
        )
        message = (
            f'DICOM decompression completed: {decompressed_count} decompressed, '
            f'{copied_count} already uncompressed and copied'
        )
        runtime.update_progress(current=total, total=total, message=message)
        runtime.mark_finished()
        return {
            'current': total,
            'total': total,
            'message': message,
            'parameters': params.model_dump(mode='json'),
            'decompressed_files': decompressed_count,
            'copied_files': copied_count,
            'output_datasets': [DatasetSerializer(output_dataset).data],
            'output_dataset_id': str(output_dataset.id),
        }
    except Ignore:
        raise
    except Exception:
        runtime.mark_failed()
        raise
