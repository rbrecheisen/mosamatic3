import { useEffect, useState } from 'react';
import { getTaskStatus, startDemoTask, TaskStatusResponse } from '../../api/tasks';
import { useAuth } from '../authcontext';

function isFinalTaskState(state?: string) {
  return state === 'SUCCESS' || state === 'FAILURE' || state === 'REVOKED';
}

export function HomePage() {
  const { user } = useAuth();
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [isStartingTask, setIsStartingTask] = useState(false);
  const [isPollingTask, setIsPollingTask] = useState(false);

  useEffect(() => {
    if (!taskId || isFinalTaskState(task?.state)) {
      setIsPollingTask(false);
      return;
    }
    const activeTaskId = taskId;
    let cancelled = false;
    async function pollTaskStatus() {
      try {
        const taskStatus = await getTaskStatus(activeTaskId);
        if (cancelled) return;
        setTask(taskStatus);
        setMessage(`Demo task status: ${taskStatus.state}`);
        if (isFinalTaskState(taskStatus.state)) {
          setIsPollingTask(false);
        }
      } catch (error) {
        if (cancelled) return;
        console.error(error);
        setMessage(error instanceof Error ? error.message : 'Could not fetch task status');
        setIsPollingTask(false);
      }
    }
    setIsPollingTask(true);
    pollTaskStatus();
    const intervalId = window.setInterval(pollTaskStatus, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [taskId, task?.state]);

  async function handleStartDemoTask() {
    setIsStartingTask(true);
    setMessage('Starting demo background task...');
    setTask(null);
    setTaskId(null);
    try {
      const startedTask = await startDemoTask(5);
      setTaskId(startedTask.task_id);
      setMessage(`Demo task queued with id ${startedTask.task_id}.`);
    } catch (error) {
      console.error(error);
      setMessage(error instanceof Error ? error.message : 'Could not start demo task');
    } finally {
      setIsStartingTask(false);
    }
  }
  const buttonDisabled = isStartingTask || isPollingTask;
  const buttonText = isStartingTask
    ? 'Starting...'
    : isPollingTask
      ? 'Task running...'
      : 'Run demo task';
  return (
    <section className="page">
      <div className="card">
        <p className="eyebrow">Welcome</p>
        <h2>
          Hello{user?.email ? `, ${user.email}` : ''}.
        </h2>
        <p className="muted">
          You are logged in. From here you can upload data or start an analysis.
        </p>
      </div>

      <div className="card stack">
        <div>
          <p className="eyebrow">Background tasks</p>
          <h3>Celery demo task</h3>
          <p className="muted">
            Starts the example FastAPI endpoint POST /api/tasks/demo?seconds=5 and polls the task status.
          </p>
        </div>

        <div className="row">
          <button type="button" onClick={handleStartDemoTask} disabled={buttonDisabled}>
            {buttonText}
          </button>
        </div>

        {message && <p className="message">{message}</p>}

        {taskId && (
          <p className="muted">
            Task id: <code>{taskId}</code>
          </p>
        )}

        {task && (
          <div className="message">
            <strong>Current status:</strong> {task.state}
            {typeof task.current === 'number' && typeof task.total === 'number' && (
              <span> — {task.current}/{task.total}</span>
            )}
            {task.message && <div>{task.message}</div>}
            {task.result !== undefined && (
              <pre>{JSON.stringify(task.result, null, 2)}</pre>
            )}
          </div>
        )}
      </div>
    </section>
  );
}