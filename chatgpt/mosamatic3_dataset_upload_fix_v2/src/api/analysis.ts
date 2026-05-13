// src/api/analyses.ts
import { request } from './client';

export type AnalysisType = {
  id: string;
  name: string;
  description: string;
};

export type CreateAnalysisRunPayload = {
  analysis_type: string;
  input_paths: string[];
  parameters: Record<string, unknown>;
};

export type AnalysisRun = {
  id: number;
  analysis_type: string;
  status: 'queued' | 'running' | 'finished' | 'failed';
  input_paths: string[];
  parameters: Record<string, unknown>;
  result_paths?: string[];
  created_at: string;
  finished_at?: string | null;
  error_message?: string | null;
};

export async function listAnalysisTypes(): Promise<AnalysisType[]> {
  return request<AnalysisType[]>('/api/analyses');
}

export async function createAnalysisRun(payload: CreateAnalysisRunPayload): Promise<AnalysisRun> {
  return request<AnalysisRun>('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisRun(runId: number | string): Promise<AnalysisRun> {
  return request<AnalysisRun>(`/api/runs/${runId}`);
}

export async function listAnalysisRuns(): Promise<AnalysisRun[]> {
  return request<AnalysisRun[]>('/api/runs');
}