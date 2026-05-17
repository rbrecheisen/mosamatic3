import { useState } from 'react';
import { getTaskStatus, startDemoTask, TaskStatusResponse } from '../../api/tasks';
import { useAuth } from '../authcontext';

export function HomePage() {
  const { user } = useAuth();
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [message, setMessage] = useState('');
  const [isStartingTask, setIsStartingTask] = useState(false);

  async function handleStartDemoTask() {
    setIsStartingTask(true);
    setMessage('Starting demo background task...');
    setTask(null);

    try {
      const startedTask = await startDemoTask(5);
      const taskStatus = await getTaskStatus(startedTask.task_id);
      setTask(taskStatus);
      setMessage(`Demo task queued with id ${startedTask.task_id}.`);
    } catch (error) {
      console.error(error);
      setMessage(error instanceof Error ? error.message : 'Could not start demo task');
    } finally {
      setIsStartingTask(false);
    }
  }

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
            Starts the example FastAPI endpoint POST /api/tasks/demo?seconds=5.
          </p>
        </div>

        <div className="row">
          <button type="button" onClick={handleStartDemoTask} disabled={isStartingTask}>
            {isStartingTask ? 'Starting...' : 'Run demo task'}
          </button>
        </div>

        {message && <p className="message">{message}</p>}

        {task && (
          <div className="message">
            <strong>Current status:</strong> {task.state}
            {typeof task.current === 'number' && typeof task.total === 'number' && (
              <span> — {task.current}/{task.total}</span>
            )}
            {task.message && <div>{task.message}</div>}
          </div>
        )}
      </div>
    </section>
  );
}
