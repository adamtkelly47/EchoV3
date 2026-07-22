"use client";

// PROMPT.md Phase 25 frontend coverage. No business logic here — every
// metric is computed server-side by TrustDashboardQueryService and read
// verbatim from GET /trust/dashboard (CONSTITUTION.md: Frontend layer must
// never own business logic). Hallucination reporting stays human-triggered
// on this page too — there is no "detect automatically" control, matching
// the backend's own structural guarantee that no code judges its own
// output as false.

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

type RateMetric = { successes: number; total: number; rate: number | null };
type CostMetric = { total_usd: number; call_count: number };
type LatencyMetric = { avg_ms: number | null; p95_ms: number | null; sample_count: number };
type FreshnessStatus = { status: string; as_of: string | null };
type ReconciliationStatus = { status: string; reconciliation_diff: number | null; as_of: string | null };
type IntegrationUptime = { name: string; successes: number; failures: number; uptime_rate: number | null };

type TrustDashboard = {
  generated_at: string;
  window_start: string;
  tool_accuracy: RateMetric;
  calculation_reconciliation: ReconciliationStatus;
  data_freshness: FreshnessStatus;
  local_model_schema_success: RateMetric;
  local_model_classification_quality: RateMetric;
  claude_escalation_rate: RateMetric;
  hallucination_incidents_open: number;
  hallucination_incidents_resolved: number;
  approval_bypass_attempts_blocked: number;
  execution_verification_rate: RateMetric;
  integration_uptime: IntegrationUptime[];
  user_corrections: number;
  regression_case_count: number;
  cost: CostMetric;
  latency: LatencyMetric;
};

type HallucinationIncident = {
  incident_id: string;
  description: string;
  status: string;
  reported_at: string;
  resolution_note: string | null;
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

function pct(rate: number | null): string {
  return rate === null ? "—" : `${(rate * 100).toFixed(0)}%`;
}

function RateTile({ label, metric }: { label: string; metric: RateMetric }) {
  return (
    <div className="metric-tile">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{pct(metric.rate)}</span>
      <span className="empty-note">
        {metric.successes}/{metric.total}
      </span>
    </div>
  );
}

export default function TrustPage() {
  const [dashboard, setDashboard] = useState<TrustDashboard | null>(null);
  const [incidents, setIncidents] = useState<HallucinationIncident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [d, i] = await Promise.all([
        api<TrustDashboard>(`/trust/dashboard?user_id=${encodeURIComponent(USER_ID)}`),
        api<HallucinationIncident[]>(`/trust/hallucination-incidents?user_id=${encodeURIComponent(USER_ID)}`),
      ]);
      setDashboard(d);
      setIncidents(i);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load trust dashboard");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function reportIncident() {
    if (!description.trim()) return;
    setBusy(true);
    try {
      await api("/trust/hallucination-incidents", {
        method: "POST",
        body: JSON.stringify({ user_id: USER_ID, description }),
      });
      setDescription("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function resolveIncident(incidentId: string) {
    const note = resolutionNotes[incidentId];
    if (!note?.trim()) return;
    setBusy(true);
    try {
      await api(`/trust/hallucination-incidents/${incidentId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ resolution_note: note }),
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (error) return <p role="alert">{error}</p>;
  if (!dashboard) return <p aria-live="polite">Loading trust dashboard…</p>;

  return (
    <main className="page">
      <h1>Trust dashboard</h1>
      <p className="freshness">
        13 metrics over a 7-day window, computed from real, already-recorded signals — not a
        general benchmark.
      </p>

      <section className="card">
        <h2>Reliability</h2>
        <div className="metric-grid">
          <RateTile label="Tool accuracy" metric={dashboard.tool_accuracy} />
          <RateTile label="Local model schema success" metric={dashboard.local_model_schema_success} />
          <RateTile
            label="Local model classification quality"
            metric={dashboard.local_model_classification_quality}
          />
          <RateTile label="Claude escalation rate" metric={dashboard.claude_escalation_rate} />
          <RateTile label="Execution verification rate" metric={dashboard.execution_verification_rate} />
          <div className="metric-tile">
            <span className="metric-label">Calculation reconciliation</span>
            <span className="metric-value">{dashboard.calculation_reconciliation.status}</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Data freshness</span>
            <span className="metric-value">{dashboard.data_freshness.status}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Safety and corrections</h2>
        <div className="metric-grid">
          <div className="metric-tile">
            <span className="metric-label">Hallucinations open / resolved</span>
            <span className="metric-value">
              {dashboard.hallucination_incidents_open} / {dashboard.hallucination_incidents_resolved}
            </span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Approval bypass attempts blocked</span>
            <span className="metric-value">{dashboard.approval_bypass_attempts_blocked}</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">User corrections</span>
            <span className="metric-value">{dashboard.user_corrections}</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Regression cases</span>
            <span className="metric-value">{dashboard.regression_case_count}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Cost, latency, integrations</h2>
        <div className="metric-grid">
          <div className="metric-tile">
            <span className="metric-label">Cost</span>
            <span className="metric-value">${dashboard.cost.total_usd.toFixed(4)}</span>
            <span className="empty-note">{dashboard.cost.call_count} calls</span>
          </div>
          <div className="metric-tile">
            <span className="metric-label">Latency (avg / p95)</span>
            <span className="metric-value">
              {dashboard.latency.avg_ms?.toFixed(0) ?? "—"} / {dashboard.latency.p95_ms?.toFixed(0) ?? "—"} ms
            </span>
          </div>
        </div>
        {dashboard.integration_uptime.length > 0 && (
          <ul>
            {dashboard.integration_uptime.map((i) => (
              <li key={i.name}>
                {i.name}: {pct(i.uptime_rate)} ({i.successes} ok / {i.failures} failed)
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card">
        <h2>Hallucination incidents</h2>
        <div className="inline-form">
          <label>
            Report a hallucination
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <button type="button" className="btn" disabled={busy} onClick={reportIncident}>
            Report
          </button>
        </div>
        <div className="section-list">
          {(incidents ?? []).map((incident) => (
            <div className="item-row" key={incident.incident_id}>
              <p>
                {incident.description}{" "}
                <span
                  className={`status-badge ${incident.status === "resolved" ? "status-ok" : "status-danger"}`}
                >
                  {incident.status}
                </span>
              </p>
              {incident.resolution_note && <p className="empty-note">{incident.resolution_note}</p>}
              {incident.status !== "resolved" && (
                <div className="inline-form">
                  <label>
                    Resolution note
                    <input
                      value={resolutionNotes[incident.incident_id] ?? ""}
                      onChange={(e) =>
                        setResolutionNotes((prev) => ({ ...prev, [incident.incident_id]: e.target.value }))
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className="btn btn-subtle"
                    disabled={busy}
                    onClick={() => resolveIncident(incident.incident_id)}
                  >
                    Resolve
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
