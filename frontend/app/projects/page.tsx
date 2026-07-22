"use client";

// PROMPT.md Phase 23 frontend coverage. No business logic here — every
// value rendered comes from the real /projects endpoints (CONSTITUTION.md:
// Frontend layer must never own business logic), matching app/page.tsx's
// own documented convention. Task/blocker state transitions are enforced
// server-side (domains/projects/service.py's real state machine) — this
// page only ever shows the buttons valid for a task/blocker's current
// status, it never re-implements the transition rules.

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

type Project = {
  project_id: string;
  name: string;
  description: string | null;
  status: string;
};

type Task = {
  task_id: string;
  project_id: string;
  description: string;
  status: "proposed" | "committed" | "in_progress" | "done" | "cancelled" | string;
};

type Blocker = {
  blocker_id: string;
  project_id: string;
  description: string;
  status: string;
  resolved_at: string | null;
};

type StatusSummary = {
  total_tasks: number;
  proposed_tasks: number;
  committed_tasks: number;
  in_progress_tasks: number;
  done_tasks: number;
  open_blockers: number;
  next_milestone: { name: string; due_date: string | null } | null;
  overdue_milestones: unknown[];
  latest_status_update: { summary: string; created_at: string } | null;
  latest_decision: { description: string; decided_at: string } | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${path} failed (${response.status}): ${body}`);
  }
  return response.json();
}

function TaskRow({ task, onAction }: { task: Task; onAction: (taskId: string, action: string) => void }) {
  const nextActions: Record<string, { action: string; label: string }[]> = {
    proposed: [{ action: "commit", label: "Commit" }],
    committed: [{ action: "start", label: "Start" }],
    in_progress: [
      { action: "complete", label: "Complete" },
      { action: "cancel", label: "Cancel" },
    ],
  };
  const actions = nextActions[task.status] ?? [];
  return (
    <div className="item-row">
      <p>
        {task.description} <span className="status-badge status-neutral">{task.status}</span>
      </p>
      {actions.length > 0 && (
        <div className="item-actions">
          {actions.map((a) => (
            <button
              key={a.action}
              type="button"
              className="btn btn-subtle"
              onClick={() => onAction(task.task_id, a.action)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function BlockerRow({ blocker, onResolve }: { blocker: Blocker; onResolve: (id: string) => void }) {
  return (
    <div className="item-row">
      <p>
        {blocker.description}{" "}
        <span className={`status-badge ${blocker.resolved_at ? "status-ok" : "status-danger"}`}>
          {blocker.resolved_at ? "resolved" : "open"}
        </span>
      </p>
      {!blocker.resolved_at && (
        <div className="item-actions">
          <button type="button" className="btn btn-subtle" onClick={() => onResolve(blocker.blocker_id)}>
            Resolve
          </button>
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project, onChanged }: { project: Project; onChanged: () => void }) {
  const [summary, setSummary] = useState<StatusSummary | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [blockers, setBlockers] = useState<Blocker[]>([]);
  const [taskDescription, setTaskDescription] = useState("");
  const [blockerDescription, setBlockerDescription] = useState("");
  const [statusUpdate, setStatusUpdate] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [s, t, b] = await Promise.all([
      api<StatusSummary>(`/projects/${project.project_id}/status-summary`),
      api<Task[]>(`/projects/${project.project_id}/tasks`),
      api<Blocker[]>(`/projects/${project.project_id}/blockers`),
    ]);
    setSummary(s);
    setTasks(t);
    setBlockers(b);
  }, [project.project_id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function runAction(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await refresh();
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function proposeTask() {
    if (!taskDescription.trim()) return;
    await runAction(() =>
      api(`/projects/${project.project_id}/tasks`, {
        method: "POST",
        body: JSON.stringify({ description: taskDescription }),
      }),
    );
    setTaskDescription("");
  }

  async function taskAction(taskId: string, action: string) {
    await runAction(() => api(`/projects/tasks/${taskId}/${action}`, { method: "POST" }));
  }

  async function raiseBlocker() {
    if (!blockerDescription.trim()) return;
    await runAction(() =>
      api(`/projects/${project.project_id}/blockers`, {
        method: "POST",
        body: JSON.stringify({ description: blockerDescription }),
      }),
    );
    setBlockerDescription("");
  }

  async function resolveBlocker(blockerId: string) {
    await runAction(() => api(`/projects/blockers/${blockerId}/resolve`, { method: "POST" }));
  }

  async function postStatusUpdate() {
    if (!statusUpdate.trim()) return;
    await runAction(() =>
      api(`/projects/${project.project_id}/status-updates`, {
        method: "POST",
        body: JSON.stringify({ summary: statusUpdate }),
      }),
    );
    setStatusUpdate("");
  }

  return (
    <section className="card" aria-labelledby={`project-${project.project_id}-heading`}>
      <h2 id={`project-${project.project_id}-heading`}>
        {project.name} <span className="status-badge status-neutral">{project.status}</span>
      </h2>
      {project.description && <p className="empty-note">{project.description}</p>}

      {summary && (
        <div className="metric-grid">
          <div className="metric-tile">
            <span className="metric-label">Tasks</span>
            <span className="metric-value">
              {summary.done_tasks}/{summary.total_tasks} done
            </span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Open blockers</span>
            <span className="metric-value">{summary.open_blockers}</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Next milestone</span>
            <span className="metric-value">{summary.next_milestone?.name ?? "None"}</span>
          </div>
        </div>
      )}
      {summary?.latest_status_update && (
        <p className="freshness">Latest update: {summary.latest_status_update.summary}</p>
      )}

      <h3>Tasks</h3>
      <div className="section-list">
        {tasks.length === 0 ? (
          <p className="empty-note">No tasks yet.</p>
        ) : (
          tasks.map((t) => <TaskRow key={t.task_id} task={t} onAction={taskAction} />)
        )}
      </div>
      <div className="inline-form">
        <label>
          New task
          <input value={taskDescription} onChange={(e) => setTaskDescription(e.target.value)} />
        </label>
        <button type="button" className="btn" disabled={busy} onClick={proposeTask}>
          Propose task
        </button>
      </div>

      <h3>Blockers</h3>
      <div className="section-list">
        {blockers.length === 0 ? (
          <p className="empty-note">No blockers.</p>
        ) : (
          blockers.map((b) => <BlockerRow key={b.blocker_id} blocker={b} onResolve={resolveBlocker} />)
        )}
      </div>
      <div className="inline-form">
        <label>
          Raise blocker
          <input value={blockerDescription} onChange={(e) => setBlockerDescription(e.target.value)} />
        </label>
        <button type="button" className="btn" disabled={busy} onClick={raiseBlocker}>
          Raise
        </button>
      </div>

      <h3>Status update</h3>
      <div className="inline-form">
        <label>
          Post an update
          <input value={statusUpdate} onChange={(e) => setStatusUpdate(e.target.value)} />
        </label>
        <button type="button" className="btn" disabled={busy} onClick={postStatusUpdate}>
          Post
        </button>
      </div>
    </section>
  );
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const load = useCallback(async () => {
    try {
      const list = await api<Project[]>(`/projects?user_id=${encodeURIComponent(USER_ID)}`);
      setProjects(list);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load projects");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createProject() {
    if (!newName.trim()) return;
    await api("/projects", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, name: newName, description: newDescription || null }),
    });
    setNewName("");
    setNewDescription("");
    await load();
  }

  return (
    <main className="page">
      <h1>Projects</h1>
      <p className="freshness">Goals, tasks, blockers, and decisions — backed by /projects.</p>

      {error && <p role="alert">{error}</p>}

      <div className="inline-form">
        <label>
          Project name
          <input value={newName} onChange={(e) => setNewName(e.target.value)} />
        </label>
        <label>
          Description
          <input value={newDescription} onChange={(e) => setNewDescription(e.target.value)} />
        </label>
        <button type="button" className="btn" onClick={createProject}>
          Create project
        </button>
      </div>

      {!projects ? (
        <p aria-live="polite">Loading projects…</p>
      ) : projects.length === 0 ? (
        <p className="empty-note">No projects yet — create one above.</p>
      ) : (
        <div className="section-list">
          {projects.map((p) => (
            <ProjectCard key={p.project_id} project={p} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  );
}
