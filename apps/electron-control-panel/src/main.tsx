import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Ban,
  CheckCircle2,
  CircleDot,
  Database,
  FileText,
  ListChecks,
  Loader2,
  Mic,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Square,
  Volume2,
  Wrench,
  XCircle
} from "lucide-react";
import {
  Command,
  Diagnostic,
  Health,
  StorageStats,
  Tool,
  Workflow,
  cancelCommand,
  confirmCommand,
  listenOnce,
  loadCommand,
  loadSnapshot,
  sendTextCommand
} from "./api";
import "./styles.css";

type ActivityState =
  | "idle"
  | "sending"
  | "listening"
  | "thinking"
  | "executing"
  | "awaiting_confirmation"
  | "speaking"
  | "failed";

const DEMO_COMMANDS = [
  "who are you",
  "what project is this",
  "summarize this project",
  "what is running on port 3000",
  "run tests"
];

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [commands, setCommands] = useState<Command[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [storage, setStorage] = useState<StorageStats | null>(null);
  const [selectedCommand, setSelectedCommand] = useState<Command | null>(null);
  const [commandText, setCommandText] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<ActivityState>("idle");

  async function refresh(selectedId = selectedCommand?.id) {
    setLoading(true);
    try {
      const snapshot = await loadSnapshot();
      setHealth(snapshot.health);
      setCommands(snapshot.commands);
      setDiagnostics(snapshot.diagnostics);
      setTools(snapshot.tools);
      setWorkflows(snapshot.workflows);
      setStorage(snapshot.storage);
      setErrors(snapshot.errors);
      if (selectedId) {
        const detail = await loadCommand(selectedId);
        setSelectedCommand(detail);
      }
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Unexpected control panel error"]);
    } finally {
      setLoading(false);
    }
  }

  async function selectCommand(command: Command) {
    setSelectedCommand(command);
    try {
      setSelectedCommand(await loadCommand(command.id));
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Failed to load command detail"]);
    }
  }

  async function runTextCommand(text: string) {
    const normalized = text.trim();
    if (!normalized || busy) return;
    setBusy(true);
    setActivity("sending");
    setErrors([]);
    try {
      const record = await sendTextCommand(normalized);
      setCommandText("");
      setSelectedCommand(record);
      setActivity(activityFromCommand(record));
      await refresh(record.id);
    } catch (error) {
      setActivity("failed");
      setErrors([error instanceof Error ? error.message : "Text command failed"]);
    } finally {
      setBusy(false);
    }
  }

  async function submitCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runTextCommand(commandText);
  }

  async function runListenOnce() {
    if (busy) return;
    setBusy(true);
    setActivity("listening");
    setErrors([]);
    try {
      const record = await listenOnce();
      setSelectedCommand(record);
      setActivity(activityFromCommand(record));
      await refresh(record.id);
    } catch (error) {
      setActivity("failed");
      setErrors([error instanceof Error ? error.message : "Voice command failed"]);
    } finally {
      setBusy(false);
    }
  }

  async function confirmSelected() {
    const phrase = selectedCommand?.safety_decision?.confirmation_phrase;
    if (!selectedCommand || !phrase || busy) return;
    setBusy(true);
    setActivity("executing");
    setErrors([]);
    try {
      const record = await confirmCommand(selectedCommand.id, phrase);
      setSelectedCommand(record);
      setActivity(activityFromCommand(record));
      await refresh(record.id);
    } catch (error) {
      setActivity("failed");
      setErrors([error instanceof Error ? error.message : "Confirmation failed"]);
    } finally {
      setBusy(false);
    }
  }

  async function cancelSelected() {
    if (!selectedCommand || busy) return;
    setBusy(true);
    setErrors([]);
    try {
      const record = await cancelCommand(selectedCommand.id);
      setSelectedCommand(record);
      setActivity(activityFromCommand(record));
      await refresh(record.id);
    } catch (error) {
      setActivity("failed");
      setErrors([error instanceof Error ? error.message : "Cancellation failed"]);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const okDiagnostics = diagnostics.filter((item) => item.ok).length;
  const successRate = useMemo(() => {
    if (commands.length === 0) return "0%";
    const good = commands.filter((command) =>
      ["completed", "planned", "confirmed", "awaiting_confirmation"].includes(command.status)
    ).length;
    return `${Math.round((good / commands.length) * 100)}%`;
  }, [commands]);

  const activeCommand = selectedCommand ?? commands[0] ?? null;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="mark">
          <div className="markGlyph">S</div>
          <div>
            <strong>SAGE</strong>
            <span>local command layer</span>
          </div>
        </div>
        <nav>
          <a className="active"><Activity size={18} /> Dashboard</a>
          <a><ListChecks size={18} /> Commands</a>
          <a><Wrench size={18} /> Tools</a>
          <a><ShieldCheck size={18} /> Safety</a>
          <a><Database size={18} /> Memory</a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Control Panel</h1>
            <p>{health ? `${health.service} ${health.version}` : "Daemon status unknown"}</p>
          </div>
          <button className="iconButton" onClick={() => refresh()} disabled={loading || busy}>
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

        <section className="commandDeck">
          <form className="commandForm" onSubmit={submitCommand}>
            <div className="commandInputWrap">
              <Send size={18} />
              <input
                value={commandText}
                onChange={(event) => setCommandText(event.target.value)}
                placeholder="Send a command"
                disabled={busy}
              />
            </div>
            <button type="submit" disabled={busy || !commandText.trim()}>
              <Send size={17} />
              Send
            </button>
            <button type="button" className="secondaryButton" onClick={runListenOnce} disabled={busy}>
              <Mic size={17} />
              Listen
            </button>
          </form>
          <div className={`activityStrip ${activity}`}>
            <ActivityIcon activity={activity} />
            <strong>{activityLabel(activity)}</strong>
            <span>{activeCommand ? activeCommand.status : "no command selected"}</span>
          </div>
        </section>

        <section className="demoRail">
          {DEMO_COMMANDS.map((command) => (
            <button
              className="demoButton"
              key={command}
              onClick={() => runTextCommand(command)}
              disabled={busy}
              type="button"
            >
              <Play size={14} />
              {command}
            </button>
          ))}
        </section>

        {errors.length > 0 && (
          <div className="error">
            <strong>Partial daemon data</strong>
            {errors.slice(0, 3).map((message) => (
              <span key={message}>{message}</span>
            ))}
          </div>
        )}

        <section className="metrics">
          <Metric label="Daemon" value={health?.status ?? "offline"} tone={health ? "good" : "bad"} />
          <Metric label="Diagnostics" value={`${okDiagnostics}/${diagnostics.length || 0}`} />
          <Metric label="Commands" value={String(commands.length)} />
          <Metric label="Success" value={successRate} />
          <Metric label="Storage" value={storage ? formatBytes(storage.size_bytes) : "n/a"} />
        </section>

        <section className="mainGrid">
          <Panel title="Recent Commands" icon={<Mic size={18} />}>
            <div className="commandList">
              {commands.length === 0 && <Empty text="No commands recorded." />}
              {commands.map((command) => (
                <button
                  className={`commandRow ${selectedCommand?.id === command.id ? "selected" : ""}`}
                  key={command.id}
                  onClick={() => selectCommand(command)}
                  type="button"
                >
                  <span className={`status ${command.status}`}>{command.status}</span>
                  <div>
                    <strong>{command.transcript}</strong>
                    <small>{commandSummary(command)}</small>
                  </div>
                </button>
              ))}
            </div>
          </Panel>

          <CommandDetail
            command={activeCommand}
            busy={busy}
            onConfirm={confirmSelected}
            onCancel={cancelSelected}
          />

          <Panel title="Diagnostics" icon={<ShieldCheck size={18} />}>
            <div className="diagnostics">
              {diagnostics.map((item) => (
                <div className="diag" key={item.name}>
                  <span className={item.ok ? "dot ok" : "dot fail"} />
                  <div>
                    <strong>{item.name}</strong>
                    <small>{item.detail}</small>
                    {!item.ok && item.fix_hint && <small>{item.fix_hint}</small>}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Registered Tools" icon={<Wrench size={18} />}>
            <div className="toolGrid">
              {tools.map((tool) => (
                <div className="tool" key={tool.name}>
                  <strong>{tool.name}</strong>
                  <small>{tool.description}</small>
                  <span>{tool.risk}</span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Workflows" icon={<Database size={18} />}>
            {workflows.length === 0 ? (
              <Empty text="No saved workflows yet." />
            ) : (
              workflows.map((workflow) => (
                <div className="workflow" key={workflow.id}>
                  <strong>{workflow.name}</strong>
                  <small>{workflow.description || `${workflow.steps.length} steps`}</small>
                </div>
              ))
            )}
          </Panel>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <div className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>{icon}{title}</h2>
      {children}
    </section>
  );
}

function CommandDetail({
  command,
  busy,
  onConfirm,
  onCancel
}: {
  command: Command | null;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const pending = command?.status === "awaiting_confirmation";
  const phrase = command?.safety_decision?.confirmation_phrase;

  return (
    <Panel title="Command Detail" icon={<FileText size={18} />}>
      {!command && <Empty text="No command selected." />}
      {command && (
        <div className="detailStack">
          <div className="detailHeader">
            <span className={`status ${command.status}`}>{command.status}</span>
            <strong>{command.transcript}</strong>
            <small>{command.id}</small>
          </div>

          {pending && (
            <div className="confirmationBox">
              <div>
                <strong>{phrase ?? "confirm action"}</strong>
                <small>{command.safety_decision?.reason}</small>
              </div>
              <div className="confirmActions">
                <button type="button" onClick={onConfirm} disabled={busy || !phrase}>
                  <CheckCircle2 size={16} />
                  Confirm
                </button>
                <button type="button" className="dangerButton" onClick={onCancel} disabled={busy}>
                  <Ban size={16} />
                  Cancel
                </button>
              </div>
            </div>
          )}

          <DetailGrid
            items={[
              ["source", command.source],
              ["cwd", command.cwd ?? "not recorded"],
              ["created", formatDate(command.created_at)],
              ["risk", command.intent_plan?.risk ?? command.safety_decision?.risk ?? "n/a"]
            ]}
          />

          {command.intent_plan && (
            <section className="detailSection">
              <h3>Plan</h3>
              <DetailGrid
                items={[
                  ["intent", command.intent_plan.intent],
                  ["confidence", formatNumber(command.intent_plan.confidence)],
                  ["summary", command.intent_plan.summary],
                  ["actions", String(command.intent_plan.actions?.length ?? 0)]
                ]}
              />
            </section>
          )}

          {command.execution_result && (
            <section className="detailSection">
              <h3>Execution</h3>
              <DetailGrid
                items={[
                  ["success", command.execution_result.success ? "true" : "false"],
                  ["latency", formatDuration(command.execution_result.latency_ms)],
                  ["summary", command.execution_result.spoken_summary]
                ]}
              />
              <div className="resultList">
                {command.execution_result.tool_results?.map((result) => (
                  <div className="resultRow" key={`${result.tool_name}-${result.duration_ms}`}>
                    <span className={`dot ${result.success ? "ok" : "fail"}`} />
                    <div>
                      <strong>{result.tool_name}</strong>
                      <small>{result.summary}</small>
                    </div>
                    <span>{formatDuration(result.duration_ms)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {command.speech_result && (
            <section className="detailSection">
              <h3>Speech</h3>
              <DetailGrid
                items={[
                  ["provider", command.speech_result.provider],
                  ["success", command.speech_result.success ? "true" : "false"],
                  ["text", command.speech_result.text],
                  ["error", command.speech_result.error ?? "none"]
                ]}
              />
            </section>
          )}

          {command.error && (
            <section className="detailSection errorText">
              <h3>Error</h3>
              <small>{command.error}</small>
            </section>
          )}
        </div>
      )}
    </Panel>
  );
}

function DetailGrid({ items }: { items: [string, string][] }) {
  return (
    <dl className="detailGrid">
      {items.map(([label, value]) => (
        <React.Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function ActivityIcon({ activity }: { activity: ActivityState }) {
  if (activity === "listening") return <Mic size={18} />;
  if (activity === "sending" || activity === "thinking" || activity === "executing") {
    return <Loader2 className="spin" size={18} />;
  }
  if (activity === "awaiting_confirmation") return <CircleDot size={18} />;
  if (activity === "speaking") return <Volume2 size={18} />;
  if (activity === "failed") return <XCircle size={18} />;
  return <Square size={18} />;
}

function Empty({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

function commandSummary(command: Command): string {
  if (command.execution_result) return command.execution_result.spoken_summary;
  if (command.safety_decision?.confirmation_phrase) {
    return `${command.safety_decision.reason} Phrase: ${command.safety_decision.confirmation_phrase}`;
  }
  return command.intent_plan?.summary ?? command.error ?? command.id;
}

function activityFromCommand(command: Command): ActivityState {
  if (command.status === "awaiting_confirmation") return "awaiting_confirmation";
  if (command.status === "failed" || command.status === "blocked") return "failed";
  if (command.speech_result?.success) return "speaking";
  if (command.execution_result) return "idle";
  if (command.intent_plan) return "thinking";
  return "idle";
}

function activityLabel(activity: ActivityState): string {
  const labels: Record<ActivityState, string> = {
    idle: "Idle",
    sending: "Sending",
    listening: "Listening",
    thinking: "Thinking",
    executing: "Executing",
    awaiting_confirmation: "Awaiting confirmation",
    speaking: "Speaking",
    failed: "Failed"
  };
  return labels[activity];
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function formatDuration(value?: number): string {
  if (value === undefined) return "n/a";
  return `${value} ms`;
}

function formatNumber(value?: number): string {
  if (value === undefined) return "n/a";
  return value.toFixed(2);
}

createRoot(document.getElementById("root")!).render(<App />);
