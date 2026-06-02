import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AvailableTask,
  getTaskParameters,
  getTaskStatus,
  listTasks,
  startTask,
  TaskStatusResponse,
} from '../../../api/tasks';

// type AvailableTask = {
//   id: string;
//   name: string;
// };

// const AVAILABLE_TASKS: AvailableTask[] = [
//   {
//     id: 'demo',
//     name: 'Demo',
//   },
// ];

function isFinalTaskState(state?: string) {
  return state === 'SUCCESS' || state === 'FAILURE' || state === 'REVOKED';
}

function getDisplayStatus(
  taskId: string | null,
  task: TaskStatusResponse | null,
  isStarting: boolean,
  error: string | null,
) {
  if (error) return 'failed';
  if (isStarting) return 'starting';
  if (!taskId) return 'idle';

  switch (task?.state) {
    case undefined:
    case 'PENDING':
    case 'STARTED':
    case 'RETRY':
      return 'running';
    case 'SUCCESS':
      return 'finished';
    case 'FAILURE':
      return 'failed';
    case 'REVOKED':
      return 'revoked';
    default:
      return task?.state?.toLowerCase() ?? 'unknown';
  }
}

function TaskRow({ taskDefinition }: { taskDefinition: AvailableTask }) {
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [hasValidParameters, setHasValidParameters] = useState(false);
  const [parametersChecked, setParametersChecked] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const displayStatus = getDisplayStatus(taskId, task, isStarting, error);
  const isRunning = displayStatus === 'starting' || displayStatus === 'running';
  const canRun = hasValidParameters && !isRunning;

  useEffect(() => {
    let cancelled = false;

    async function loadParameters() {
      setParametersChecked(false);

      try {
        const savedParameters = await getTaskParameters(taskDefinition.id);
        if (cancelled) return;

        setHasValidParameters(savedParameters.exists && savedParameters.is_valid);
      } catch (loadError) {
        if (cancelled) return;

        console.error(loadError);
        setHasValidParameters(false);
      } finally {
        if (!cancelled) {
          setParametersChecked(true);
        }
      }
    }

    loadParameters();

    return () => {
      cancelled = true;
    };
  }, [taskDefinition.id]);

  useEffect(() => {
    if (!taskId || isFinalTaskState(task?.state)) {
      return;
    }

    const activeTaskId = taskId;
    let cancelled = false;

    async function pollTaskStatus() {
      try {
        const taskStatus = await getTaskStatus(activeTaskId);
        if (cancelled) return;

        setTask(taskStatus);
      } catch (pollError) {
        if (cancelled) return;

        console.error(pollError);
        setError(pollError instanceof Error ? pollError.message : 'Could not fetch task status');
      }
    }

    pollTaskStatus();
    const intervalId = window.setInterval(pollTaskStatus, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [taskId, task?.state]);

  async function handleRunTask() {
    setIsStarting(true);
    setError(null);
    setTask(null);
    setTaskId(null);

    try {
      const startedTask = await startTask(taskDefinition.id);
      setTaskId(startedTask.task_id);
    } catch (startError) {
      console.error(startError);
      setError(startError instanceof Error ? startError.message : 'Could not start task');
    } finally {
      setIsStarting(false);
    }
  }

  return (
    <tr>
      <td>{taskDefinition.name}</td>

      <td>
        <button type="button" onClick={handleRunTask} disabled={!canRun}>
          Run
        </button>
      </td>

      <td>
        <strong>{displayStatus}</strong>

        {!parametersChecked && (
          <div className="muted">Checking parameters...</div>
        )}

        {parametersChecked && !hasValidParameters && (
          <div className="muted">Set parameters before running.</div>
        )}

        {task?.message && (
          <div className="muted">{task.message}</div>
        )}

        {taskId && (
          <div className="muted">
            Task id: <code>{taskId}</code>
          </div>
        )}

        {error && (
          <div className="muted">{error}</div>
        )}
      </td>

      <td>
        <Link
          to={`/analysis/${taskDefinition.id}/parameters`}
          className={`button-like ${hasValidParameters ? 'success' : 'warning'}`}
        >
          {hasValidParameters ? 'Update parameters' : 'Set parameters'}
        </Link>
      </td>
    </tr>
  );
}

export function AnalysisPage() {
  const [availableTasks, setAvailableTasks] = useState<AvailableTask[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadTasks() {
      setLoadingTasks(true);
      setError(null);

      try {
        const tasks = await listTasks();

        if (!cancelled) {
          setAvailableTasks(tasks);
        }
      } catch (loadError) {
        if (!cancelled) {
          console.error(loadError);
          setError(loadError instanceof Error ? loadError.message : 'Could not load tasks');
        }
      } finally {
        if (!cancelled) {
          setLoadingTasks(false);
        }
      }
    }

    loadTasks();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="card">
      <p className="eyebrow">Analysis</p>
      <h2>Available tasks</h2>
      <p className="muted">
        Set task parameters first. Once parameters have been saved successfully, the task can be run.
      </p>

      {loadingTasks && (
        <p className="muted">Loading tasks...</p>
      )}

      {error && (
        <p className="muted">{error}</p>
      )}

      {!loadingTasks && !error && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Action</th>
              <th>Status</th>
              <th>Parameters</th>
            </tr>
          </thead>
          <tbody>
            {availableTasks.map((taskDefinition) => (
              <TaskRow key={taskDefinition.id} taskDefinition={taskDefinition} />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// export function AnalysisPage() {
//   return (
//     <section className="card">
//       <p className="eyebrow">Analysis</p>
//       <h2>Available tasks</h2>
//       <p className="muted">
//         Set task parameters first. Once parameters have been saved successfully, the task can be run.
//       </p>
//       <table className="data-table">
//         <thead>
//           <tr>
//             <th>Task</th>
//             <th>Action</th>
//             <th>Status</th>
//             <th>Parameters</th>
//           </tr>
//         </thead>
//         <tbody>
//           {AVAILABLE_TASKS.map((taskDefinition) => (
//             <TaskRow key={taskDefinition.id} taskDefinition={taskDefinition} />
//           ))}
//         </tbody>
//       </table>
//     </section>
//   );
// }