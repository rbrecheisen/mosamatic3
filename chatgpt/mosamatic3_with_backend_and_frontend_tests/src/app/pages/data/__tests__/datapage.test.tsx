import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithRouter } from '../../../../test/render';
import { DataPage } from '../datapage';

vi.mock('../../../../api/files', () => ({
  listDatasets: vi.fn(),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}));

import { deleteDataset, listDatasets, uploadDataset } from '../../../../api/files';

const mockedListDatasets = vi.mocked(listDatasets);
const mockedUploadDataset = vi.mocked(uploadDataset);
const mockedDeleteDataset = vi.mocked(deleteDataset);

const datasets = [
  {
    id: 'input-1',
    name: 'Patient CT upload',
    kind: 'input',
    created_at: '2026-06-05T08:00:00Z',
    file_count: 2,
    total_size_bytes: 2048,
  },
  {
    id: 'output-1',
    name: 'Rescaled output',
    kind: 'output',
    source_task_key: 'rescaledicomimages',
    created_at: '2026-06-05T09:00:00Z',
    file_count: 1,
    total_size_bytes: 1024,
  },
];

describe('DataPage', () => {
  it('lists input datasets separately from output results', async () => {
    mockedListDatasets.mockResolvedValueOnce(datasets);

    renderWithRouter(<DataPage />);

    expect(await screen.findByRole('heading', { name: /input datasets/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /patient ct upload/i })).toHaveAttribute('href', '/data/input-1');
    expect(screen.getByRole('link', { name: /rescaled output/i })).toHaveAttribute('href', '/data/output-1');
    expect(screen.getByText('rescaledicomimages')).toBeInTheDocument();
  });

  it('rejects uploads when the entered dataset name already exists', async () => {
    const user = userEvent.setup();
    mockedListDatasets.mockResolvedValueOnce(datasets);
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('patient ct upload');

    renderWithRouter(<DataPage />);
    await screen.findByRole('link', { name: /patient ct upload/i });

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['dicom'], 'image.dcm', { type: 'application/dicom' });
    await user.upload(fileInput, file);

    expect(promptSpy).toHaveBeenCalledWith('Dataset name');
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
    expect(mockedUploadDataset).not.toHaveBeenCalled();
  });

  it('deletes a dataset after confirmation', async () => {
    const user = userEvent.setup();
    mockedListDatasets.mockResolvedValueOnce(datasets);
    mockedDeleteDataset.mockResolvedValueOnce(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithRouter(<DataPage />);

    const row = (await screen.findByRole('link', { name: /patient ct upload/i })).closest('tr');
    expect(row).not.toBeNull();

    await user.click(within(row as HTMLTableRowElement).getByRole('button', { name: /delete/i }));

    await waitFor(() => expect(mockedDeleteDataset).toHaveBeenCalledWith('input-1'));
    expect(screen.getByText(/deleted dataset/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /patient ct upload/i })).not.toBeInTheDocument();
  });
});
