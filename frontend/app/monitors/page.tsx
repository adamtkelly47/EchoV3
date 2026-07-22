"use client";

// PROMPT.md Phase 24 frontend coverage. No business logic here — every
// value comes from the real /monitors endpoints (CONSTITUTION.md: Frontend
// layer must never own business logic). Monitors can only ever notify
// (acknowledge/suppress an alert), never execute a consequential action —
// there is no "run automatically" toggle beyond enabled/disabled, matching
// the backend's own structural guarantee (PROMPT.md Phase 24 verification
// 1: "Monitors may notify but cannot execute consequential actions").

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

const MONITOR_TYPES = [
  "calendar_conflict",
  "stale_schwab_sync",
  "ips_concentration_breach",
  "material_portfolio_news",
  "integration_failure",
];

type Monitor = {
  monitor_id: string;
  monitor_type: string;
  enabled: boolean;
};

type Alert = {
  alert_id: string;
  monitor_type: string;
  severity: "low" | "medium" | "high" | string;
  message: string;
  reason: string;
  status: string;
  triggered_at: string;
  acknowledged_at: string | null;
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

const severityClass: Record<string, string> = {
  low: "status-neutral",
  medium: "status-warn",
  high: "status-danger",
};

export default function MonitorsPage() {
  const [monitors, setMonitors] = useState<Monitor[] | null>(null);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newType, setNewType] = useState(MONITOR_TYPES[0]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([
        api<Monitor[]>(`/monitors?user_id=${encodeURIComponent(USER_ID)}`),
        api<Alert[]>(`/monitors/alerts?user_id=${encodeURIComponent(USER_ID)}`),
      ]);
      setMonitors(m);
      setAlerts(a);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load monitors");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createMonitor() {
    setBusy(true);
    try {
      await api("/monitors", {
        method: "POST",
        body: JSON.stringify({ user_id: USER_ID, monitor_type: newType }),
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled(monitor: Monitor) {
    setBusy(true);
    try {
      await api(`/monitors/${monitor.monitor_id}/enabled`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !monitor.enabled }),
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function evaluateNow() {
    setBusy(true);
    try {
      await api("/monitors/evaluate", { method: "POST" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function acknowledge(alertId: string) {
    setBusy(true);
    try {
      await api(`/monitors/alerts/${alertId}/acknowledge`, { method: "POST" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function suppress(alertId: string) {
    setBusy(true);
    try {
      await api(`/monitors/alerts/${alertId}/suppress`, { method: "POST" });
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Monitoring</h1>
      <p className="freshness">
        Background alerts — the scheduler runs a real sweep every 300 seconds; &ldquo;Evaluate
        now&rdquo; is the same manual path used for testing.
      </p>

      {error && <p role="alert">{error}</p>}

      <section className="card" aria-labelledby="monitors-heading">
        <h2 id="monitors-heading">Monitors</h2>
        {!monitors ? (
          <p aria-live="polite">Loading…</p>
        ) : monitors.length === 0 ? (
          <p className="empty-note">No monitors registered yet.</p>
        ) : (
          <div className="section-list">
            {monitors.map((m) => (
              <div className="item-row" key={m.monitor_id}>
                <p>
                  {m.monitor_type}{" "}
                  <span className={`status-badge ${m.enabled ? "status-ok" : "status-neutral"}`}>
                    {m.enabled ? "enabled" : "disabled"}
                  </span>
                </p>
                <div className="item-actions">
                  <button type="button" className="btn btn-subtle" disabled={busy} onClick={() => toggleEnabled(m)}>
                    {m.enabled ? "Disable" : "Enable"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="inline-form">
          <label>
            Monitor type
            <select value={newType} onChange={(e) => setNewType(e.target.value)}>
              {MONITOR_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn" disabled={busy} onClick={createMonitor}>
            Add monitor
          </button>
          <button type="button" className="btn btn-subtle" disabled={busy} onClick={evaluateNow}>
            Evaluate now
          </button>
        </div>
      </section>

      <section className="card" aria-labelledby="alerts-heading">
        <h2 id="alerts-heading">Alerts</h2>
        {!alerts ? (
          <p aria-live="polite">Loading…</p>
        ) : alerts.length === 0 ? (
          <p className="empty-note">No alerts.</p>
        ) : (
          <div className="section-list">
            {alerts.map((a) => (
              <div className="item-row" key={a.alert_id}>
                <p>
                  <span className={`status-badge ${severityClass[a.severity] ?? "status-neutral"}`}>
                    {a.severity}
                  </span>{" "}
                  {a.message}
                  {" — "}
                  <span className="status-badge status-neutral">{a.status}</span>
                </p>
                <p className="empty-note">{a.reason}</p>
                {a.status === "active" && (
                  <div className="item-actions">
                    <button
                      type="button"
                      className="btn btn-subtle"
                      disabled={busy}
                      onClick={() => acknowledge(a.alert_id)}
                    >
                      Acknowledge
                    </button>
                    <button
                      type="button"
                      className="btn btn-subtle"
                      disabled={busy}
                      onClick={() => suppress(a.alert_id)}
                    >
                      Suppress
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
