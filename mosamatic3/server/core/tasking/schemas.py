from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class DemoTaskParameters(BaseModel):
  text_value: str = Field(default='Hello from demo task', title='Text value')
  integer_value: int = Field(default=5, title='Iterations', ge=1, le=100)
  float_value: float = Field(default=1.5, title='Float value')
  slider_value: int = Field(default=50, title='Slider value', ge=0, le=100)
  processing_mode: Literal['fast', 'balanced', 'accurate'] = Field(default='balanced', title='Processing mode')
  enable_debug_output: bool = Field(default=False, title='Enable debug output')
  dataset_id: UUID | None = Field(default=None, title='Dataset', json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True})
  dataset_ids: list[UUID] = Field(default_factory=list, title='Datasets', json_schema_extra={'ui_widget': 'dataset_multiselect', 'dataset_reference': True})


class RescaleDicomImagesTaskParameters(BaseModel):
  dataset_id: UUID = Field(
    title='Dataset', 
    description='Dataset containing the DICOM files to rescale', 
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True}
  )
  target_size: int = Field(
    default=512, 
    title='Target size', 
    ge=64, 
    le=4096, 
    description='Target square image size in pixels'
  )


class SliceSelectTaskParameters(BaseModel):
  dataset_id: UUID = Field(
    title='Dataset', 
    description='Dataset containing the DICOM files to rescale', 
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True}
  )
  vertebral_level: Literal['L3', 'T4'] = Field(
    default='L3', 
    title='Vertebral level'
  )
  patient_id_path_part_index: int = Field(
    default=1, 
    title='Patient ID part index (advanced, default=1)'
  )


class SegmentMuscleFatL3TensorFlowTaskParameters(BaseModel):
  dataset_id: UUID = Field(
    title='Selected slice dataset',
    description='Dataset containing DICOM slices, for example the output of Slice Select',
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True},
  )
  model_files_dataset_id: UUID = Field(
    title='Model files dataset',
    description='Dataset containing model-<version>.zip, contour_model-<version>.zip and params-<version>.json',
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True},
  )
  model_version: str = Field(
    default='1',
    title='Model version',
    description='Model version used to select model-<version>.zip, contour_model-<version>.zip and params-<version>.json',
  )
  input_path_prefix: str | None = Field(
    default='',
    title='Input path prefix',
    description='Optional subfolder/prefix inside the selected slice dataset. Leave empty for root/all files. Use selected_slices for Slice Select output.',
  )
  probabilities: bool = Field(
    default=False,
    title='Output probabilities',
    description='If enabled, stores probability maps instead of hard segmentation labels',
  )


class CalculateScoresTaskParameters(BaseModel):
  input_dataset_id: UUID = Field(
    title='Input dataset',
    description='Dataset containing both DICOM images and .seg.npy segmentation files.',
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True},
  )
  patient_info_dataset_id: UUID | None = Field(
    default=None,
    title='Patient info dataset (optional)',
    description='Optional dataset containing a CSV file with columns: file, height, weight, sex, age.',
    json_schema_extra={'ui_widget': 'dataset_select', 'dataset_reference': True},
  )
  patient_info_relative_path: str | None = Field(
    default='',
    title='Patient info CSV relative path (optional)',
    description='Optional CSV path inside the patient info dataset. Leave empty if the dataset contains exactly one CSV file.',
  )
  file_type: Literal['npy', 'tag'] = Field(
    default='npy',
    title='Segmentation file type',
    description='Use npy for .seg.npy files or tag for .tag files.',
  )
  input_path_prefix: str | None = Field(
    default='',
    title='Input path prefix',
    description='Optional subfolder/prefix inside the input dataset. Leave empty for root/all files.',
  )