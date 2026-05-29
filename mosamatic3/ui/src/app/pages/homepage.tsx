import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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
          You are logged in. From here you can upload <Link to="/data">data</Link> or start an <Link to="/analysis">analysis</Link>.
        </p>
      </div>
    </section>
  );
}