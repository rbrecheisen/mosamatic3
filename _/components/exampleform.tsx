import { useEffect, useState } from 'react';
import { createFormSubmission, FormSubmission, listFormSubmissions } from '../api/client';

export function ExampleForm() {
  const [textValue, setTextValue] = useState('Example value');
  const [enabled, setEnabled] = useState(true);
  const [choice, setChoice] = useState('option-a');
  const [notes, setNotes] = useState('');
  const [message, setMessage] = useState('');
  const [submissions, setSubmissions] = useState<FormSubmission[]>([]);

  async function refresh() {
    setSubmissions(await listFormSubmissions());
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setMessage('Saving...');
    try {
      await createFormSubmission({ text_value: textValue, enabled, choice, notes });
      await refresh();
      setMessage('Saved to SQLite');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not save form');
    }
  }

  return (
    <section className="card">
      <h2>Example form widgets</h2>
      <form onSubmit={submit} className="stack">
        <label>
          Text field
          <input value={textValue} onChange={(event) => setTextValue(event.target.value)} />
        </label>

        <label className="checkbox-row">
          <input checked={enabled} onChange={(event) => setEnabled(event.target.checked)} type="checkbox" />
          Enable option
        </label>

        <label>
          Selection menu
          <select value={choice} onChange={(event) => setChoice(event.target.value)}>
            <option value="option-a">Option A</option>
            <option value="option-b">Option B</option>
            <option value="option-c">Option C</option>
          </select>
        </label>

        <label>
          Notes
          <textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} />
        </label>

        <button type="submit">Save form</button>
      </form>
      {message && <p className="message">{message}</p>}

      <h3>Previous submissions</h3>
      {submissions.length === 0 ? (
        <p className="muted">No submissions yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Text</th>
              <th>Enabled</th>
              <th>Choice</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {submissions.map((submission) => (
              <tr key={submission.id}>
                <td>{submission.text_value}</td>
                <td>{submission.enabled ? 'yes' : 'no'}</td>
                <td>{submission.choice}</td>
                <td>{new Date(submission.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
