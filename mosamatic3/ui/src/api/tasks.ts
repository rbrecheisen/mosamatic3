import { request } from './client';

export type AvailableTask = {
  id: string;
  name: string;
  description?: string | null;
};

export type StartTaskResponse = {
  task_id: string;
  status: string;
};

// export type TaskStatusResponse = {
//   task_id: string;
//   state: string;
//   message?: string;
//   current?: number;
//   total?: number;
//   result?: unknown;
// };

export type TaskStatusResponse = {
  task_id: string;
  state: string;
  message?: string;
  current?: number;
  total?: number;
  cancel_requested?: boolean;
  result?: unknown;
};

export type CancelTaskResponse = {
  task_id: string;
  status: string;
  message?: string;
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

export type TaskParameterJsonSchemaProperty = {
  title?: string;
  description?: string;
  type?: string;
  format?: string;
  default?: unknown;
  enum?: unknown[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  multipleOf?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
  items?: TaskParameterJsonSchemaProperty;
  ui_widget?: string;
};

export type TaskParameterJsonSchema = {
  title?: string;
  type?: string;
  properties?: Record<string, TaskParameterJsonSchemaProperty>;
  required?: string[];
};

export type TaskSchemaResponse = {
  id: string;
  name: string;
  description?: string | null;
  schema: TaskParameterJsonSchema;
};

export async function listTasks(): Promise<AvailableTask[]> {
  return request<AvailableTask[]>('/api/tasks');
}

export async function getTaskSchema(taskKey: string): Promise<TaskSchemaResponse> {
  return request<TaskSchemaResponse>(`/api/tasks/${taskKey}/schema`);
}

export async function startTask(taskKey: string): Promise<StartTaskResponse> {
  return request<StartTaskResponse>(`/api/tasks/${taskKey}/run`, {
    method: 'POST',
  });
}

export async function getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(`/api/tasks/${taskId}`);
}

export async function cancelTask(taskId: string): Promise<CancelTaskResponse> {
  return request<CancelTaskResponse>(`/api/tasks/${taskId}/cancel`, {
    method: 'POST',
  });
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