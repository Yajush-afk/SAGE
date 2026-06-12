export type Health = { status: string; version: string; service: string };

export type ToolCall = {
  tool_name: string;
  arguments: Record<string, unknown>;
};

export type ToolResult = {
  tool_name: string;
  success: boolean;
  summary: string;
  details: string;
  data: Record<string, unknown>;
  duration_ms: number;
};

export type Command = {
  id: string;
  transcript: string;
  status: string;
  created_at: string;
  source: string;
  cwd?: string | null;
  raw_audio_path?: string | null;
  error?: string | null;
  transcription?: {
    text: string;
    confidence?: number | null;
    duration_ms: number;
    provider: string;
  } | null;
  safety_decision?: {
    action?: string;
    risk?: string;
    reason: string;
    confirmation_phrase?: string | null;
    expires_at?: string | null;
  } | null;
  execution_result?: {
    command_id?: string;
    success: boolean;
    spoken_summary: string;
    details?: string;
    latency_ms?: number;
    tool_results?: ToolResult[];
  } | null;
  speech_result?: {
    success: boolean;
    provider: string;
    text: string;
    audio_path?: string | null;
    error?: string | null;
  } | null;
  intent_plan?: {
    intent: string;
    confidence?: number;
    summary: string;
    actions?: ToolCall[];
    risk: string;
    requires_confirmation?: boolean;
  } | null;
};

export type Diagnostic = {
  name: string;
  ok: boolean;
  detail: string;
  required?: boolean;
  severity?: "ok" | "warning" | "error";
  fix_hint?: string;
  docs_anchor?: string;
};
export type Tool = { name: string; description: string; risk: string };
export type WorkflowStep = {
  tool_name: string;
  arguments: Record<string, unknown>;
};

export type Workflow = {
  id: string;
  name: string;
  description: string;
  project_path?: string | null;
  is_global?: boolean;
  steps: WorkflowStep[];
  created_at?: string;
  updated_at?: string;
};
export type StorageStats = {
  path: string;
  size_bytes: number;
  command_count: number;
  workflow_count: number;
};

export type ApiSnapshot = {
  health: Health | null;
  commands: Command[];
  diagnostics: Diagnostic[];
  tools: Tool[];
  workflows: Workflow[];
  storage: StorageStats | null;
  errors: string[];
};

const API = import.meta.env.VITE_SAGE_API_URL ?? "http://127.0.0.1:8765";

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`${path}: ${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, payload?: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    body: payload === undefined ? undefined : JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`${path}: ${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

export async function loadCommand(commandId: string): Promise<Command> {
  return fetchJson<Command>(`/commands/${commandId}`);
}

export async function sendTextCommand(commandText: string): Promise<Command> {
  return postJson<Command>("/commands/text", {
    command_text: commandText,
    source: "api"
  });
}

export async function listenOnce(): Promise<Command> {
  return postJson<Command>("/commands/listen-once");
}

export async function confirmCommand(commandId: string, phrase: string): Promise<Command> {
  return postJson<Command>(`/commands/${commandId}/confirm`, { phrase });
}

export async function cancelCommand(commandId: string): Promise<Command> {
  return postJson<Command>(`/commands/${commandId}/cancel`);
}

export async function runWorkflow(workflowId: string): Promise<Command> {
  return postJson<Command>(`/workflows/${workflowId}/run`, {});
}

export async function deleteWorkflow(workflowId: string): Promise<{ deleted: boolean }> {
  const response = await fetch(`${API}/workflows/${workflowId}`, {
    method: "DELETE",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) {
    throw new Error(`/workflows/${workflowId}: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<{ deleted: boolean }>;
}

async function safeFetch<T>(path: string, fallback: T): Promise<[T, string | null]> {
  try {
    return [await fetchJson<T>(path), null];
  } catch (error) {
    return [fallback, error instanceof Error ? error.message : `Failed to load ${path}`];
  }
}

export async function loadSnapshot(): Promise<ApiSnapshot> {
  const [health, commands, diagnostics, tools, workflows, storage] = await Promise.all([
    safeFetch<Health | null>("/health", null),
    safeFetch<Command[]>("/commands/recent?limit=12", []),
    safeFetch<Diagnostic[]>("/diagnostics", []),
    safeFetch<Tool[]>("/tools", []),
    safeFetch<Workflow[]>("/workflows", []),
    safeFetch<StorageStats | null>("/storage", null)
  ]);

  return {
    health: health[0],
    commands: commands[0],
    diagnostics: diagnostics[0],
    tools: tools[0],
    workflows: workflows[0],
    storage: storage[0],
    errors: [health[1], commands[1], diagnostics[1], tools[1], workflows[1], storage[1]].filter(
      (message): message is string => message !== null
    )
  };
}
