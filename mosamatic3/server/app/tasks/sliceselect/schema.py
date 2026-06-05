from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class SliceSelectTaskParameters(BaseModel):
  dataset_id: UUID = Field(
    title="Dataset",
    description="Dataset containing patient folders with DICOM scans",
    json_schema_extra={
      "ui_widget": "dataset_select",
    },
  )
  vertebral_level: Literal["L3", "T4"] = Field(
    default="L3",
    title="Vertebral Level",
    description="Vertebral level at which to take the slice.",
  )