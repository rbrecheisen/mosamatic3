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
    dataset_id: UUID = Field(title='Dataset', description='Dataset containing patient folders with DICOM scans', json_schema_extra={'ui_widget': 'dataset_select'})
    vertebral_level: Literal['L3', 'T4'] = Field(default='L3', title='Vertebral Level')
