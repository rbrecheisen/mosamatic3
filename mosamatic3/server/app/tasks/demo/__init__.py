from app.tasks.base import TaskDefinition
from app.tasks.demo.schema import DemoTaskParameters


task_definition = TaskDefinition(
  key="demo",
  name="Demo Task",
  description="Demonstrates all supported task parameter form fields.",
  celery_task_name="app.tasks.demo.celerytasks.run_demotask",
  celery_module="app.tasks.demo.celerytasks",
  parameter_schema=DemoTaskParameters,
)