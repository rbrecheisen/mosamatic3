import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithRouter } from '../../../../test/render';
import { AnalysisPage } from '../analysispage';

vi.mock('../../../../api/tasks', () => ({
  listTasks: vi.fn(),
  getTaskParameters: vi.fn(),
  startTask: vi.fn(),
  getTaskStatus: vi.fn(),
}));

import { getTaskParameters, getTaskStatus, listTasks, startTask } from '../../../../api/tasks';

const mockedListTasks = vi.mocked(listTasks);
const mockedGetTaskParameters = vi.mocked(getTaskParameters);
const mockedStartTask = vi.mocked(startTask);
const mockedGetTaskStatus = vi.mocked(getTaskStatus);

describe('AnalysisPage', () => {
  it('renders tasks and disables Run until valid parameters exist', async () => {
    mockedListTasks.mockResolvedValueOnce([
      { id: 'demo', name: 'Demo task', description: 'Dummy task' },
      { id: 'rescaledicomimages', name: 'Rescale DICOM images', description: 'Rescale DICOM task' },
    ]);
    mockedGetTaskParameters
      .mockResolvedValueOnce({ task_key: 'demo', exists: false, is_valid: false, parameters: {} })
      .mockResolvedValueOnce({ task_key: 'rescaledicomimages', exists: true, is_valid: true, parameters: { dataset_id: '1' } });

    renderWithRouter(<AnalysisPage />);

    const demoRow = (await screen.findByText('Demo task')).closest('tr') as HTMLTableRowElement;
    const rescaleRow = screen.getByText('Rescale DICOM images').closest('tr') as HTMLTableRowElement;

    expect(within(demoRow).getByRole('button', { name: /run/i })).toBeDisabled();
    expect(within(demoRow).getByRole('link', { name: /set parameters/i })).toHaveAttribute('href', '/analysis/demo/parameters');

    await waitFor(() => expect(within(rescaleRow).getByRole('button', { name: /run/i })).toBeEnabled());
    expect(within(rescaleRow).getByRole('link', { name: /update parameters/i })).toHaveAttribute('href', '/analysis/rescaledicomimages/parameters');
  });

  it('starts a task and shows the finished status', async () => {
    const user = userEvent.setup();
    mockedListTasks.mockResolvedValueOnce([
      { id: 'demo', name: 'Demo task', description: 'Dummy task' },
    ]);
    mockedGetTaskParameters.mockResolvedValueOnce({
      task_key: 'demo',
      exists: true,
      is_valid: true,
      parameters: { integer_value: 1 },
    });
    mockedStartTask.mockResolvedValueOnce({ task_id: 'celery-1', status: 'queued' });
    mockedGetTaskStatus.mockResolvedValueOnce({
      task_id: 'celery-1',
      state: 'SUCCESS',
      message: 'Done',
      current: 1,
      total: 1,
    });

    renderWithRouter(<AnalysisPage />);

    await user.click(await screen.findByRole('button', { name: /run/i }));

    await waitFor(() => expect(mockedStartTask).toHaveBeenCalledWith('demo'));
    expect(await screen.findByText(/finished/i)).toBeInTheDocument();
    expect(screen.getByText(/celery-1/i)).toBeInTheDocument();
  });
});
