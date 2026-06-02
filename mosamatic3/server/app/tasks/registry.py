from app.tasks.rescaledicomimages import task_definition as rescaledicomimagestask

TASKS = {
    task.key: task
    for task in [
        rescaledicomimagestask,
    ]
}