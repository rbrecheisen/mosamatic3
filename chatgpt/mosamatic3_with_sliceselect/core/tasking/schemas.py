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
    dataset_id: UUID | None = Field(default=None, title='Dataset', json_schema_extra={'ui_widget': 'dataset_select'})
    dataset_ids: list[UUID] = Field(default_factory=list, title='Datasets', json_schema_extra={'ui_widget': 'dataset_multiselect'})

class RescaleDicomImagesTaskParameters(BaseModel):
    dataset_id: UUID = Field(title='Dataset', description='Dataset containing the DICOM files to rescale', json_schema_extra={'ui_widget': 'dataset_select'})
    target_size: int = Field(default=512, title='Target size', ge=64, le=4096, description='Target square image size in pixels')

class SliceSelectTaskParameters(BaseModel):
    dataset_id: UUID = Field(
        title='Dataset',
        description='Dataset containing DICOM files grouped in patient/scan folders',
        json_schema_extra={'ui_widget': 'dataset_select'},
    )
    vertebral_level: Literal[
        'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11', 'T12',
        'L1', 'L2', 'L3', 'L4', 'L5',
    ] = Field(default='L3', title='Vertebral level')
    output_name: str = Field(default='Slice Select output', title='Output dataset name')
    fast_mode: bool = Field(
        default=True,
        title='Use TotalSegmentator fast mode',
        description='Faster vertebra segmentation, usually sufficient for slice selection',
    )
    create_review_pngs: bool = Field(
        default=True,
        title='Create review PNGs',
        description='Creates axial and sagittal PNG images for manual checking',
    )
    patient_id_path_part_index: int = Field(
        default=0,
        title='Patient ID path part index',
        ge=0,
        le=20,
        description='0-based folder index used for output filenames. For patient/scan/file.dcm use 0.',
    )
