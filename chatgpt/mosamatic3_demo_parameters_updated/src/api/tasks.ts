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

export type TaskParametersResponse = {
  task_key: string;
  parameters: Record<string, unknown>;
  is_valid: boolean;
  error_message?: string | null;
  exists: boolean;
  updated_at?: string | null;
};

export type SaveTaskParametersPayload = {
  task_key: string;
  parameters: Record<string, unknown>;
};

export async function startDemoTask(seconds = 5): Promise<StartTaskResponse> {
  return request<StartTaskResponse>(`/api/tasks/demo?seconds=${seconds}`, {
    method: 'POST',
  });
}

export async function startTask(taskKey: string): Promise<StartTaskResponse> {
  return request<StartTaskResponse>(`/api/tasks/${taskKey}/run`, {
    method: 'POST',
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(`/api/tasks/${taskId}`);
}

export async function getTaskParameters(taskKey: string): Promise<TaskParametersResponse> {
  return request<TaskParametersResponse>(`/api/tasks/${taskKey}/parameters`);
}

export async function saveTaskParameters(
  taskKey: string,
  payload: SaveTaskParametersPayload,
): Promise<TaskParametersResponse> {
  return request<TaskParametersResponse>(`/api/tasks/${taskKey}/parameters`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

// import { request } from './client';

// export type StartTaskResponse = {
//   task_id: string;
//   status: string;
// };

// export type TaskStatusResponse = {
//   task_id: string;
//   state: string;
//   message?: string;
//   current?: number;
//   total?: number;
//   result?: unknown;
// };

// export async function startDemoTask(seconds = 5): Promise<StartTaskResponse> {
//   return request<StartTaskResponse>(`/api/tasks/demo?seconds=${seconds}`, {
//     method: 'POST',
//   });
// }

// export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
//   return request<TaskStatusResponse>(`/api/tasks/${taskId}`);
// }