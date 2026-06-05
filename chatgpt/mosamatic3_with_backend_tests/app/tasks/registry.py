from app.tasks.demo import task_definition as demotask
from app.tasks.rescaledicomimages import task_definition as rescaledicomimagestask


TASKS = {
    task.key: task
    for task in [
        demotask,
        rescaledicomimagestask,
    ]
}