import { FormEvent, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DatasetSummary, listDatasets } from '../../../api/files';
import { getTaskParameters, saveTaskParameters } from '../../../api/tasks';

const TASK_NAMES: Record<string, string> = {
  demo: 'Demo',
};

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string') : [];
}

export function TaskParametersPage() {
  const { taskKey } = useParams();
  const navigate = useNavigate();
  const [seconds, setSeconds] = useState('5');
  const [singleDatasetId, setSingleDatasetId] = useState('');
  const [textValue, setTextValue] = useState('');
  const [checkboxValue, setCheckboxValue] = useState(false);
  const [sliderValue, setSliderValue] = useState('50');
  const [datasetToAdd, setDatasetToAdd] = useState('');
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resolvedTaskKey = taskKey ?? '';
  const taskName = TASK_NAMES[resolvedTaskKey] ?? resolvedTaskKey;
  const hasConfiguredForm = Object.keys(TASK_NAMES).includes(resolvedTaskKey);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedParameters() {
      if (!resolvedTaskKey) {
        setError('Missing task key.');
        setLoading(false);
        return;
      }
      try {
        const [savedParameters, availableDatasets] = await Promise.all([
          getTaskParameters(resolvedTaskKey),
          listDatasets(),
        ]);
        if (cancelled) return;

        setDatasets(availableDatasets);
        setSeconds(asString(savedParameters.parameters.seconds, '5'));
        setSingleDatasetId(asString(savedParameters.parameters.single_dataset_id, ''));
        setTextValue(asString(savedParameters.parameters.text_value, ''));
        setCheckboxValue(asBoolean(savedParameters.parameters.checkbox_value, false));
        setSliderValue(asString(savedParameters.parameters.slider_value, '50'));
        setSelectedDatasetIds(asStringArray(savedParameters.parameters.dataset_ids));
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

  function handleAddDataset() {
    if (!datasetToAdd) return;
    setSelectedDatasetIds((currentIds) => {
      if (currentIds.includes(datasetToAdd)) {
        return currentIds;
      }
      return [...currentIds, datasetToAdd];
    });
    setDatasetToAdd('');
  }

  function removeSelectedDataset(datasetId: string) {
    setSelectedDatasetIds((currentIds) => currentIds.filter((id) => id !== datasetId));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resolvedTaskKey) {
      setError('Missing task key.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      let parameters: Record<string, unknown>;
      if (resolvedTaskKey === 'demo') {
        parameters = {
          seconds: Number(seconds),
          single_dataset_id: singleDatasetId || null,
          text_value: textValue,
          checkbox_value: checkboxValue,
          slider_value: Number(sliderValue),
          dataset_ids: selectedDatasetIds,
        };
      } else {
        setError(`No parameter form has been configured for task ${resolvedTaskKey}.`);
        setSaving(false);
        return;
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
          {resolvedTaskKey === 'demo' && (
            <>
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

              <label>
                Single dataset
                <select
                  value={singleDatasetId}
                  onChange={(event) => setSingleDatasetId(event.target.value)}
                >
                  <option value="">No single dataset selected</option>
                  {datasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name} ({dataset.file_count} files)
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Text parameter
                <input
                  type="text"
                  value={textValue}
                  onChange={(event) => setTextValue(event.target.value)}
                  placeholder="Dummy text value passed to Celery"
                  maxLength={500}
                />
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={checkboxValue}
                  onChange={(event) => setCheckboxValue(event.target.checked)}
                />
                Boolean checkbox parameter
              </label>

              <label>
                Slider-driven numerical parameter: {sliderValue}
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  value={sliderValue}
                  onChange={(event) => setSliderValue(event.target.value)}
                />
              </label>

              <div className="stack">
                <label>
                  Dataset list
                  <select value={datasetToAdd} onChange={(event) => setDatasetToAdd(event.target.value)}>
                    <option value="">Select a dataset to add...</option>
                    {datasets
                      .filter((dataset) => !selectedDatasetIds.includes(dataset.id))
                      .map((dataset) => (
                        <option key={dataset.id} value={dataset.id}>
                          {dataset.name} ({dataset.file_count} files)
                        </option>
                      ))}
                  </select>
                </label>
                <div className="row">
                  <button type="button" className="secondary" onClick={handleAddDataset} disabled={!datasetToAdd}>
                    Add selected dataset
                  </button>
                  <span className="muted">
                    This creates <code>dataset_ids</code>, a list of dataset IDs sent to the backend.
                  </span>
                </div>
              </div>

              {selectedDatasetIds.length > 0 ? (
                <div className="stack">
                  <strong>Selected datasets</strong>
                  {selectedDatasetIds.map((datasetId) => {
                    const dataset = datasets.find((item) => item.id === datasetId);
                    return (
                      <div key={datasetId} className="row">
                        <span>
                          {dataset?.name ?? datasetId}
                          {dataset && <span className="muted"> — {dataset.file_count} files</span>}
                        </span>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => removeSelectedDataset(datasetId)}
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="muted">No datasets added to the list yet.</p>
              )}
            </>
          )}
          {!hasConfiguredForm && (
            <p className="message">
              No parameter form has been configured for task <code>{resolvedTaskKey}</code>.
            </p>
          )}
          {error && <p className="message">{error}</p>}
          <div className="row">
            <button type="submit" disabled={saving || !hasConfiguredForm}>
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

// import { FormEvent, useEffect, useState } from 'react';
// import { useNavigate, useParams } from 'react-router-dom';
// import { DatasetSummary, listDatasets } from '../../../api/files';
// import { getTaskParameters, saveTaskParameters } from '../../../api/tasks';

// const TASK_NAMES: Record<string, string> = {
//   demo: 'Demo',
// };

// export function TaskParametersPage() {
//   const { taskKey } = useParams();
//   const navigate = useNavigate();
//   const [seconds, setSeconds] = useState('5');
//   const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
//   const [selectedDatasetIds, setSelectedDatasetIds] = useState<string[]>([]);
//   const [loading, setLoading] = useState(true);
//   const [saving, setSaving] = useState(false);
//   const [error, setError] = useState<string | null>(null);
//   const resolvedTaskKey = taskKey ?? '';
//   const taskName = TASK_NAMES[resolvedTaskKey] ?? resolvedTaskKey;
//   const hasConfiguredForm = Object.keys(TASK_NAMES).includes(resolvedTaskKey);

//   useEffect(() => {
//     let cancelled = false;

//     async function loadSavedParameters() {
//       if (!resolvedTaskKey) {
//         setError('Missing task key.');
//         setLoading(false);
//         return;
//       }
//       try {
//         const [savedParameters, availableDatasets] = await Promise.all([
//           getTaskParameters(resolvedTaskKey),
//           listDatasets(),
//         ]);
//         // const savedParameters = await getTaskParameters(resolvedTaskKey);
//         if (cancelled) return;
//         setDatasets(availableDatasets);
//         const savedSeconds = savedParameters.parameters.seconds;
//         if (typeof savedSeconds === 'number' || typeof savedSeconds === 'string') {
//           setSeconds(String(savedSeconds));
//         }
//         const savedDatasetIds = savedParameters.parameters.dataset_ids;
//         if (Array.isArray(savedDatasetIds)) {
//           setSelectedDatasetIds(
//             savedDatasetIds.filter((id): id is string => typeof id === 'string'),
//           );
//         }
//       } catch (loadError) {
//         if (cancelled) return;
//         console.error(loadError);
//         setError(loadError instanceof Error ? loadError.message : 'Could not load task parameters');
//       } finally {
//         if (!cancelled) {
//           setLoading(false);
//         }
//       }
//     }
//     loadSavedParameters();
//     return () => {
//       cancelled = true;
//     };
//   }, [resolvedTaskKey]);

//   function handleDatasetSelect(datasetId: string) {
//     if (!datasetId) return;
//     setSelectedDatasetIds((currentIds) => {
//       if (currentIds.includes(datasetId)) {
//         return currentIds;
//       }
//       return [...currentIds, datasetId];
//     });
//   }

//   function removeSelectedDataset(datasetId: string) {
//     setSelectedDatasetIds((currentIds) =>
//       currentIds.filter((id) => id !== datasetId),
//     );
//   }

//   async function handleSubmit(event: FormEvent<HTMLFormElement>) {
//     event.preventDefault();
//     if (!resolvedTaskKey) {
//       setError('Missing task key.');
//       return;
//     }
//     setSaving(true);
//     setError(null);
//     try {
//       let parameters: Record<string, unknown>;
//       if (resolvedTaskKey === 'demo') {
//         parameters = {
//           seconds: Number(seconds),
//           dataset_ids: selectedDatasetIds,
//         }
//       } else {
//         setError(`No parameter form has been configured for task ${resolvedTaskKey}.`);
//         setSaving(false);
//         return;
//       }
//       await saveTaskParameters(resolvedTaskKey, {
//         task_key: resolvedTaskKey,
//         parameters: parameters,
//       });
//       navigate('/analysis');
//     } catch (saveError) {
//       console.error(saveError);
//       setError(saveError instanceof Error ? saveError.message : 'Could not save task parameters');
//     } finally {
//       setSaving(false);
//     }
//   }

//   return (
//     <section className="card stack">
//       <div>
//         <p className="eyebrow">Task parameters</p>
//         <h2>{taskName}</h2>
//         <p className="muted">
//           Configure the parameters for this task. Saving validates the parameters on the server.
//         </p>
//       </div>
//       {loading ? (
//         <p className="muted">Loading parameters...</p>
//       ) : (
//         <form className="stack" onSubmit={handleSubmit}>
//           {resolvedTaskKey === 'demo' && (
//             <>
//               <label>
//                 Seconds
//                 <input
//                   type="number"
//                   min="1"
//                   max="300"
//                   value={seconds}
//                   onChange={(event) => setSeconds(event.target.value)}
//                   required
//                 />
//               </label>
//               <label>
//                 Add dataset
//                 <select
//                   value=""
//                   onChange={(event) => handleDatasetSelect(event.target.value)}
//                 >
//                   <option value="">Select a dataset...</option>
//                   {datasets
//                     .filter((dataset) => !selectedDatasetIds.includes(dataset.id))
//                     .map((dataset) => (
//                       <option key={dataset.id} value={dataset.id}>
//                         {dataset.name} ({dataset.file_count} files)
//                       </option>
//                     ))}
//                 </select>
//               </label>
//               {selectedDatasetIds.length > 0 && (
//                 <div className="stack">
//                   <strong>Selected datasets</strong>
//                   {selectedDatasetIds.map((datasetId) => {
//                     const dataset = datasets.find((item) => item.id === datasetId);
//                     return (
//                       <div key={datasetId} className="row">
//                         <span>
//                           {dataset?.name ?? datasetId}
//                           {dataset && (
//                             <span className="muted"> — {dataset.file_count} files</span>
//                           )}
//                         </span>
//                         <button
//                           type="button"
//                           className="secondary"
//                           onClick={() => removeSelectedDataset(datasetId)}
//                         >
//                           Remove
//                         </button>
//                       </div>
//                     );
//                   })}
//                 </div>
//               )}
//             </>
//           )}
//           {!hasConfiguredForm && (
//               <p className="message">
//                 No parameter form has been configured for task <code>{resolvedTaskKey}</code>.
//             </p>
//           )}
//           {error && <p className="message">{error}</p>}
//           <div className="row">
//             <button type="submit" disabled={saving || !hasConfiguredForm}>
//               {saving ? 'Saving...' : 'Save parameters'}
//             </button>
//             <button type="button" className="secondary" onClick={() => navigate('/analysis')}>
//               Cancel
//             </button>
//           </div>
//         </form>
//       )}
//     </section>
//   );
// }