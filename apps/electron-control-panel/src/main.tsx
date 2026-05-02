import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Database,
  ListChecks,
  Mic,
  RefreshCw,
  ShieldCheck,
  Wrench
} from "lucide-react";
import { Command, Diagnostic, Health, StorageStats, Tool, Workflow, loadSnapshot } from "./api";
import "./styles.css";

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [commands, setCommands] = useState<Command[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [storage, setStorage] = useState<StorageStats | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  async function refresh() {
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
    } catch (error) {
      setErrors([error instanceof Error ? error.message : "Unexpected control panel error"]);
    } finally {
      setLoading(false);
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
          <button onClick={refresh} disabled={loading}>
            <RefreshCw size={17} />
            Refresh
          </button>
        </header>

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

        <section className="grid">
          <Panel title="Recent Commands" icon={<Mic size={18} />}>
            <div className="commandList">
              {commands.length === 0 && <Empty text="No commands recorded." />}
              {commands.map((command) => (
                <div className="commandRow" key={command.id}>
                  <span className={`status ${command.status}`}>{command.status}</span>
                  <div>
                    <strong>{command.transcript}</strong>
                    <small>{commandSummary(command)}</small>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Diagnostics" icon={<ShieldCheck size={18} />}>
            <div className="diagnostics">
              {diagnostics.map((item) => (
                <div className="diag" key={item.name}>
                  <span className={item.ok ? "dot ok" : "dot fail"} />
                  <div>
                    <strong>{item.name}</strong>
                    <small>{item.detail}</small>
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

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

createRoot(document.getElementById("root")!).render(<App />);
