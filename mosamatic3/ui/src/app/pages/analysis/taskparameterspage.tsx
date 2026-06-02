import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DatasetSummary, listDatasets } from '../../../api/files';
import {
  getTaskParameters,
  getTaskSchema,
  saveTaskParameters,
  TaskParameterJsonSchemaProperty,
  TaskSchemaResponse,
} from '../../../api/tasks';

function getDefaultValue(property: TaskParameterJsonSchemaProperty): unknown {
  if (property.default !== undefined) return property.default;
  if (property.ui_widget === 'dataset_select') return '';
  if (property.ui_widget === 'dataset_multi_select') return [];
  switch (property.type) {
    case 'boolean':
      return false;
    case 'integer':
    case 'number':
      return '';
    case 'array':
      return [];
    case 'string':
    default:
      return '';
  }
}

function normalizeSubmitValue(
  property: TaskParameterJsonSchemaProperty,
  value: unknown,
): unknown {
  if (property.ui_widget === 'dataset_select') {
    return value || null;
  }
  if (property.ui_widget === 'dataset_multi_select') {
    return Array.isArray(value) ? value : [];
  }
  if (property.type === 'integer') {
    return value === '' || value === null || value === undefined ? null : Number.parseInt(String(value), 10);
  }
  if (property.type === 'number') {
    return value === '' || value === null || value === undefined ? null : Number(value);
  }
  if (property.type === 'boolean') {
    return Boolean(value);
  }
  return value;
}

function renderFieldLabel(fieldName: string, property: TaskParameterJsonSchemaProperty) {
  return property.title ?? fieldName.replace(/_/g, ' ');
}

export function TaskParametersPage() {
  const { taskKey } = useParams();
  const navigate = useNavigate();

  const resolvedTaskKey = taskKey ?? '';

  const [taskSchema, setTaskSchema] = useState<TaskSchemaResponse | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const properties = useMemo(
    () => taskSchema?.schema.properties ?? {},
    [taskSchema],
  );

  const requiredFields = useMemo(
    () => new Set(taskSchema?.schema.required ?? []),
    [taskSchema],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadPageData() {
      if (!resolvedTaskKey) {
        setError('Missing task key.');
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const [schemaResponse, savedParameters, availableDatasets] = await Promise.all([
          getTaskSchema(resolvedTaskKey),
          getTaskParameters(resolvedTaskKey),
          listDatasets(),
        ]);
        if (cancelled) return;
        setTaskSchema(schemaResponse);
        setDatasets(availableDatasets);
        const initialValues: Record<string, unknown> = {};
        for (const [fieldName, property] of Object.entries(schemaResponse.schema.properties ?? {})) {
          initialValues[fieldName] =
            savedParameters.parameters[fieldName] ?? getDefaultValue(property);
        }
        setValues(initialValues);
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
    loadPageData();
    return () => {
      cancelled = true;
    };
  }, [resolvedTaskKey]);

  function getStringArrayValue(fieldName: string): string[] {
    const value = values[fieldName];
    if (!Array.isArray(value)) {
      return [];
    }
    return value.map(String);
  }

  function addDatasetToMultiSelect(fieldName: string, datasetId: string) {
    if (!datasetId) return;
    const currentDatasetIds = getStringArrayValue(fieldName);
    if (currentDatasetIds.includes(datasetId)) {
      return;
    }
    updateValue(fieldName, [...currentDatasetIds, datasetId]);
  }

  function removeDatasetFromMultiSelect(fieldName: string, datasetId: string) {
    const currentDatasetIds = getStringArrayValue(fieldName);
    updateValue(
      fieldName,
      currentDatasetIds.filter((currentDatasetId) => currentDatasetId !== datasetId),
    );
  }

  function updateValue(fieldName: string, value: unknown) {
    setValues((currentValues) => ({
      ...currentValues,
      [fieldName]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!resolvedTaskKey || !taskSchema) {
      setError('Missing task schema.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const parameters: Record<string, unknown> = {};

      for (const [fieldName, property] of Object.entries(properties)) {
        parameters[fieldName] = normalizeSubmitValue(property, values[fieldName]);
      }

      await saveTaskParameters(resolvedTaskKey, {
        task_key: resolvedTaskKey,
        parameters,
      });

      navigate('/analysis');
    } catch (saveError) {
      console.error(saveError);
      setError(saveError instanceof Error ? saveError.message : 'Could not save task parameters');
    } finally {
      setSaving(false);
    }
  }

  function renderField(fieldName: string, property: TaskParameterJsonSchemaProperty) {
    const value = values[fieldName];
    const label = renderFieldLabel(fieldName, property);
    const isRequired = requiredFields.has(fieldName);

    if (property.ui_widget === 'dataset_multi_select') {
      const selectedDatasetIds = getStringArrayValue(fieldName);
      return (
        <div key={fieldName} className="stack">
          <label>
            {label}
            <select
              value=""
              onChange={(event) => {
                addDatasetToMultiSelect(fieldName, event.target.value);
                event.target.value = '';
              }}
            >
              <option value="">Add dataset...</option>
              {datasets
                .filter((dataset) => !selectedDatasetIds.includes(dataset.id))
                .map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name} ({dataset.file_count} files)
                  </option>
                ))}
            </select>
            {property.description && <span className="muted">{property.description}</span>}
          </label>
          {selectedDatasetIds.length === 0 ? (
            <p className="muted">No datasets selected.</p>
          ) : (
            <ul className="selected-dataset-list">
              {selectedDatasetIds.map((datasetId) => {
                const dataset = datasets.find((candidate) => candidate.id === datasetId);
                return (
                  <li key={datasetId} className="selected-dataset-row">
                    <span>
                      {dataset ? `${dataset.name} (${dataset.file_count} files)` : datasetId}
                    </span>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => removeDatasetFromMultiSelect(fieldName, datasetId)}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {requiredFields.has(fieldName) && selectedDatasetIds.length === 0 && (
            <p className="muted">Select at least one dataset.</p>
          )}
        </div>
      );
    }
    if (property.ui_widget === 'dataset_select') {
      return (
        <label key={fieldName}>
          {label}
          <select
            value={typeof value === 'string' ? value : ''}
            onChange={(event) => updateValue(fieldName, event.target.value)}
            required={isRequired}
          >
            <option value="">Select a dataset...</option>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name} ({dataset.file_count} files)
              </option>
            ))}
          </select>
          {property.description && <span className="muted">{property.description}</span>}
        </label>
      );
    }

    if (property.enum) {
      return (
        <label key={fieldName}>
          {label}
          <select
            value={String(value ?? '')}
            onChange={(event) => updateValue(fieldName, event.target.value)}
            required={isRequired}
          >
            <option value="">Select...</option>
            {property.enum.map((option) => (
              <option key={String(option)} value={String(option)}>
                {String(option)}
              </option>
            ))}
          </select>
          {property.description && <span className="muted">{property.description}</span>}
        </label>
      );
    }

    if (property.type === 'boolean') {
      return (
        <label key={fieldName} className="checkbox-row">
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => updateValue(fieldName, event.target.checked)}
          />
          {label}
          {property.description && <span className="muted">{property.description}</span>}
        </label>
      );
    }

    if (property.type === 'integer' || property.type === 'number') {
      return (
        <label key={fieldName}>
          {label}
          <input
            type="number"
            value={typeof value === 'number' || typeof value === 'string' ? value : ''}
            min={property.minimum}
            max={property.maximum}
            onChange={(event) => updateValue(fieldName, event.target.value)}
            required={isRequired}
          />
          {property.description && <span className="muted">{property.description}</span>}
        </label>
      );
    }

    return (
      <label key={fieldName}>
        {label}
        <input
          type="text"
          value={typeof value === 'string' || typeof value === 'number' ? String(value) : ''}
          onChange={(event) => updateValue(fieldName, event.target.value)}
          required={isRequired}
          maxLength={property.maxLength}
        />
        {property.description && <span className="muted">{property.description}</span>}
      </label>
    );
  }

  return (
    <section className="card stack">
      <div>
        <p className="eyebrow">Task parameters</p>
        <h2>{taskSchema?.name ?? resolvedTaskKey}</h2>
        <p className="muted">
          Configure the parameters for this task. Saving validates the parameters on the server.
        </p>
      </div>

      {loading ? (
        <p className="muted">Loading parameters...</p>
      ) : (
        <form className="stack" onSubmit={handleSubmit}>
          {Object.entries(properties).map(([fieldName, property]) =>
            renderField(fieldName, property),
          )}

          {Object.keys(properties).length === 0 && (
            <p className="message">
              This task does not define any parameters.
            </p>
          )}

          {error && <p className="message">{error}</p>}

          <div className="row">
            <button type="submit" disabled={saving || !taskSchema}>
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