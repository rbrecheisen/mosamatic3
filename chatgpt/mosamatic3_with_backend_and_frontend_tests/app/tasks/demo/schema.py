from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class DemoTaskParameters(BaseModel):
  text_value: str = Field(
    default="Hello Mosamatic",
    min_length=1,
    max_length=200,
    title="Text value",
    description="A regular text input field.",
  )
  integer_value: int = Field(
    default=5,
    ge=0,
    le=100,
    title="Integer value",
    description="A spinner-like integer number input.",
  )
  float_value: float = Field(
    default=1.5,
    ge=0,
    le=10,
    multiple_of=0.5,
    title="Float value",
    description="A spinner-like floating point number input.",
  )
  slider_value: int = Field(
    default=50,
    ge=0,
    le=100,
    multiple_of=5,
    title="Slider value",
    description="A numerical value controlled with a slider.",
    json_schema_extra={
      "ui_widget": "slider",
    },
  )
  processing_mode: Literal["fast", "balanced", "quality"] = Field(
    default="balanced",
    title="Processing mode",
    description="A regular combobox generated from an enum.",
  )
  enable_debug_output: bool = Field(
    default=False,
    title="Enable debug output",
    description="A checkbox field.",
  )
  dataset_id: UUID = Field(
    title="Single dataset",
    description="Select one dataset from a combobox.",
    json_schema_extra={
      "ui_widget": "dataset_select",
    },
  )
  dataset_ids: list[UUID] = Field(
    default_factory=list,
    min_length=1,
    title="Multiple datasets",
    description="Select multiple datasets using a combobox and list.",
    json_schema_extra={
      "ui_widget": "dataset_multi_select",
    },
  )