import time
from celery.exceptions import Ignore
from ...tasking.runtime import TaskRuntime
from ...tasking.schemas import DemoTaskParameters


def run_demo_task(parameters: dict, user_id: str, celery_task=None) -> dict:
    runtime = TaskRuntime(task_key='demo', parameters=parameters, parameter_model=DemoTaskParameters, user_id=user_id, celery_task=celery_task)
    params = runtime.params
    runtime.mark_running()
    try:
        total = params.integer_value
        runtime.update_progress(current=0, total=total, message='Starting demo task')
        for index in range(total):
            runtime.check_cancelled(current=index, total=total, message=f'Task cancelled after {index} of {total} iterations')
            time.sleep(1)
            runtime.update_progress(current=index + 1, total=total, message=f'Demo task iteration {index + 1} of {total}')
        runtime.mark_finished()
        return {'current': total, 'total': total, 'message': 'Demo task completed', 'parameters': params.model_dump(mode='json')}
    except Ignore:
        raise
    except Exception:
        runtime.mark_failed()
        raise
