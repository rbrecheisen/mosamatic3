from pydantic import BaseModel


class TaskDefinition(BaseModel):
  key: str
  name: str
  description: str | None = None
  celery_task_name: str
  parameter_schema: type[BaseModel]

  class Config:
    arbitrary_types_allowed = True