export type Health = { status: string; version: string; service: string };

export type Command = {
  id: string;
  transcript: string;
  status: string;
  created_at: string;
  error?: string | null;
  safety_decision?: {
    reason: string;
    confirmation_phrase?: string | null;
  } | null;
  execution_result?: {
    success: boolean;
    spoken_summary: string;
  } | null;
  intent_plan?: { intent: string; summary: string; risk: string } | null;
};

export type Diagnostic = { name: string; ok: boolean; detail: string };
export type Tool = { name: string; description: string; risk: string };
export type Workflow = { id: string; name: string; description: string; steps: unknown[] };
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
