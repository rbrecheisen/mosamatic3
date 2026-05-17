import { request } from './client';

export type StartTaskResponse = {
  task_id: string;
  status: string;
};

export type TaskStatusResponse = {
  task_id: string;
  state: string;
  message?: string;
  current?: number;
  total?: number;
  result?: unknown;
};

export async function startDemoTask(seconds = 5): Promise<StartTaskResponse> {
  return request<StartTaskResponse>(`/api/tasks/demo?seconds=${seconds}`, {
    method: 'POST',
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(`/api/tasks/${taskId}`);
}
