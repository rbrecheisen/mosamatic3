import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { renderWithRouter } from '../../../../test/render';
import { DataDetailsPage } from '../datadetailspage';

vi.mock('../../../../api/files', () => ({
  getDataset: vi.fn(),
  downloadDataset: vi.fn(),
}));

import { downloadDataset, getDataset } from '../../../../api/files';

const mockedGetDataset = vi.mocked(getDataset);
const mockedDownloadDataset = vi.mocked(downloadDataset);

describe('DataDetailsPage', () => {
  it('shows dataset metadata and file rows', async () => {
    mockedGetDataset.mockResolvedValueOnce({
      id: 'dataset-1',
      name: 'CT upload',
      kind: 'input',
      created_at: '2026-06-05T08:00:00Z',
      file_count: 2,
      total_size_bytes: 3072,
      files: [
        { id: 'file-1', relative_path: 'scan/001.dcm', size_bytes: 1024, created_at: '2026-06-05T08:01:00Z' },
        { id: 'file-2', relative_path: 'scan/002.dcm', size_bytes: 2048, created_at: '2026-06-05T08:02:00Z' },
      ],
    });

    renderWithRouter(
      <Routes>
        <Route path="/data/:datasetId" element={<DataDetailsPage />} />
      </Routes>,
      ['/data/dataset-1'],
    );

    expect(await screen.findByRole('heading', { name: /ct upload/i })).toBeInTheDocument();
    expect(screen.getByText(/2 file\(s\), 3.0 KB total/i)).toBeInTheDocument();
    expect(screen.getByText('scan/001.dcm')).toBeInTheDocument();
    expect(screen.getByText('scan/002.dcm')).toBeInTheDocument();
  });

  it('calls the download endpoint when Download ZIP is clicked', async () => {
    const user = userEvent.setup();
    mockedGetDataset.mockResolvedValueOnce({
      id: 'dataset-1',
      name: 'CT upload',
      kind: 'input',
      created_at: '2026-06-05T08:00:00Z',
      file_count: 0,
      total_size_bytes: 0,
      files: [],
    });
    mockedDownloadDataset.mockResolvedValueOnce(undefined);

    renderWithRouter(
      <Routes>
        <Route path="/data/:datasetId" element={<DataDetailsPage />} />
      </Routes>,
      ['/data/dataset-1'],
    );

    await user.click(await screen.findByRole('button', { name: /download zip/i }));

    await waitFor(() => expect(mockedDownloadDataset).toHaveBeenCalledWith('dataset-1'));
  });
});
