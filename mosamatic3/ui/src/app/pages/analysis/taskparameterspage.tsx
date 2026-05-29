import { FormEvent, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getTaskParameters, saveTaskParameters } from '../../../api/tasks';

const TASK_NAMES: Record<string, string> = {
  demo: 'Demo task',
};

export function TaskParametersPage() {
  const { taskKey } = useParams();
  const navigate = useNavigate();

  const [seconds, setSeconds] = useState('5');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolvedTaskKey = taskKey ?? '';
  const taskName = TASK_NAMES[resolvedTaskKey] ?? resolvedTaskKey;

  useEffect(() => {
    let cancelled = false;

    async function loadSavedParameters() {
      if (!resolvedTaskKey) {
        setError('Missing task key.');
        setLoading(false);
        return;
      }

      try {
        const savedParameters = await getTaskParameters(resolvedTaskKey);

        if (cancelled) return;

        const savedSeconds = savedParameters.parameters.seconds;

        if (typeof savedSeconds === 'number' || typeof savedSeconds === 'string') {
          setSeconds(String(savedSeconds));
        }
      } catch (loadError) {
        if (cancelled) return;

        console.error(loadError);
        setError(loadError instanceof Error ? loadError.message : 'Could not load task parameters');
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSavedParameters();

    return () => {
      cancelled = true;
    };
  }, [resolvedTaskKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!resolvedTaskKey) {
      setError('Missing task key.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      await saveTaskParameters(resolvedTaskKey, {
        task_key: resolvedTaskKey,
        parameters: {
          seconds: Number(seconds),
        },
      });

      navigate('/analysis');
    } catch (saveError) {
      console.error(saveError);
      setError(saveError instanceof Error ? saveError.message : 'Could not save task parameters');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card stack">
      <div>
        <p className="eyebrow">Task parameters</p>
        <h2>{taskName}</h2>
        <p className="muted">
          Configure the parameters for this task. Saving validates the parameters on the server.
        </p>
      </div>

      {loading ? (
        <p className="muted">Loading parameters...</p>
      ) : (
        <form className="stack" onSubmit={handleSubmit}>
          {resolvedTaskKey === 'demo' ? (
            <label>
              Seconds
              <input
                type="number"
                min="1"
                max="300"
                value={seconds}
                onChange={(event) => setSeconds(event.target.value)}
                required
              />
            </label>
          ) : (
            <p className="message">
              No parameter form has been configured for task <code>{resolvedTaskKey}</code>.
            </p>
          )}

          {error && <p className="message">{error}</p>}

          <div className="row">
            <button type="submit" disabled={saving || resolvedTaskKey !== 'demo'}>
              {saving ? 'Saving...' : 'Save parameters'}
            </button>

            <button type="button" className="secondary" onClick={() => navigate('/analysis')}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}