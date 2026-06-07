from pydantic import BaseModel, ConfigDict

class TaskDefinition(BaseModel):
    key: str
    name: str
    description: str | None = None
    celery_task_name: str
    parameter_schema: type[BaseModel]
    model_config = ConfigDict(arbitrary_types_allowed=True)
