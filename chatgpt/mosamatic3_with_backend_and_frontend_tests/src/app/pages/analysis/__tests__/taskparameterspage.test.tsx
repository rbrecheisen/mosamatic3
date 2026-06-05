import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router-dom';
import { renderWithRouter } from '../../../../test/render';
import { TaskParametersPage } from '../taskparameterspage';

vi.mock('../../../../api/tasks', () => ({
  getTaskSchema: vi.fn(),
  getTaskParameters: vi.fn(),
  saveTaskParameters: vi.fn(),
}));

vi.mock('../../../../api/files', () => ({
  listDatasets: vi.fn(),
}));

import { listDatasets } from '../../../../api/files';
import { getTaskParameters, getTaskSchema, saveTaskParameters } from '../../../../api/tasks';

const mockedListDatasets = vi.mocked(listDatasets);
const mockedGetTaskSchema = vi.mocked(getTaskSchema);
const mockedGetTaskParameters = vi.mocked(getTaskParameters);
const mockedSaveTaskParameters = vi.mocked(saveTaskParameters);

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

const schema = {
  id: 'demo',
  name: 'Demo task',
  description: 'Demo schema',
  schema: {
    type: 'object',
    required: ['text_value', 'dataset_id'],
    properties: {
      text_value: { title: 'Text value', type: 'string', default: 'hello' },
      enable_debug_output: { title: 'Enable debug output', type: 'boolean', default: false },
      integer_value: { title: 'Integer value', type: 'integer', default: 3, minimum: 1 },
      slider_value: { title: 'Slider value', type: 'integer', ui_widget: 'slider', default: 5, minimum: 0, maximum: 10 },
      processing_mode: { title: 'Processing mode', type: 'string', enum: ['fast', 'accurate'], default: 'fast' },
      dataset_id: { title: 'Dataset', type: 'string', ui_widget: 'dataset_select' },
      dataset_ids: { title: 'Datasets', type: 'array', ui_widget: 'dataset_multi_select', items: { type: 'string' } },
    },
  },
};

const availableDatasets = [
  { id: 'dataset-1', name: 'CT upload', kind: 'input', created_at: '2026-06-05T08:00:00Z', file_count: 2, total_size_bytes: 1024 },
  { id: 'dataset-2', name: 'MRI upload', kind: 'input', created_at: '2026-06-05T08:00:00Z', file_count: 3, total_size_bytes: 2048 },
];

describe('TaskParametersPage', () => {
  it('prefills saved parameters and submits normalized values', async () => {
    const user = userEvent.setup();
    mockedGetTaskSchema.mockResolvedValueOnce(schema);
    mockedGetTaskParameters.mockResolvedValueOnce({
      task_key: 'demo',
      exists: true,
      is_valid: true,
      parameters: {
        text_value: 'previous text',
        integer_value: 7,
        slider_value: 4,
        processing_mode: 'accurate',
        enable_debug_output: true,
        dataset_id: 'dataset-1',
        dataset_ids: ['dataset-2'],
      },
    });
    mockedListDatasets.mockResolvedValueOnce(availableDatasets);
    mockedSaveTaskParameters.mockResolvedValueOnce({
      task_key: 'demo',
      exists: true,
      is_valid: true,
      parameters: {},
    });

    renderWithRouter(
      <Routes>
        <Route path="/analysis/:taskKey/parameters" element={<TaskParametersPage />} />
        <Route path="/analysis" element={<LocationProbe />} />
      </Routes>,
      ['/analysis/demo/parameters'],
    );

    expect(await screen.findByRole('heading', { name: /demo task/i })).toBeInTheDocument();
    await user.clear(screen.getByLabelText(/text value/i));
    await user.type(screen.getByLabelText(/text value/i), 'new text');
    await user.clear(screen.getByLabelText(/integer value/i));
    await user.type(screen.getByLabelText(/integer value/i), '11');
    await user.click(screen.getByLabelText(/enable debug output/i));
    await user.selectOptions(screen.getByLabelText(/^dataset$/i), 'dataset-2');

    const multiSelect = screen.getByRole('combobox', { name: /datasets/i });
    await user.selectOptions(multiSelect, 'dataset-1');

    const mriText = screen.getAllByText('MRI upload (3 files)').find((element) => element.tagName.toLowerCase() === 'span');
    expect(mriText).toBeDefined();
    const mriRow = mriText!.closest('li') as HTMLLIElement;
    await user.click(within(mriRow).getByRole('button', { name: /remove/i }));

    await user.click(screen.getByRole('button', { name: /save parameters/i }));

    await waitFor(() => expect(mockedSaveTaskParameters).toHaveBeenCalledWith('demo', {
      task_key: 'demo',
      parameters: expect.objectContaining({
        text_value: 'new text',
        integer_value: 11,
        slider_value: 4,
        processing_mode: 'accurate',
        enable_debug_output: false,
        dataset_id: 'dataset-2',
        dataset_ids: ['dataset-1'],
      }),
    }));
    expect(await screen.findByTestId('location')).toHaveTextContent('/analysis');
  });
});
