from uuid import UUID
from pydantic import BaseModel, Field


class RescaleDicomImagesTaskParameters(BaseModel):
  dataset_id: UUID = Field(
    title="Dataset",
    description="Dataset containing the DICOM files to rescale",
    json_schema_extra={
      "ui_widget": "dataset_select",
    },
  )
  target_size: int = Field(
    default=512,
    title="Target size",
    ge=64,
    le=4096,
    description="Target square image size in pixels",
  )
  overwrite_existing: bool = Field(
    default=False,
    title="Overwrite existing files",
    description="Overwrite existing rescaled files if they already exist",
  )