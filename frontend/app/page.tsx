"use client";

// PROMPT.md Phase 22: the unified dashboard. No business logic here — every
// value rendered comes directly from GET /dashboard (CONSTITUTION.md:
// Frontend layer must never own business logic; PROMPT.md Phase 22
// verification 1/4). The backend URL is hardcoded to localhost, matching
// app/chat/page.tsx's own documented convention for this phase; real
// deployment configuration and authentication are later concerns.

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

type CardStatus = "ok" | "not_connected" | "no_data" | "not_available";

type CardMeta = {
  status: CardStatus;
  as_of: string | null;
  detail: string | null;
};

type CalendarEvent = {
  event_id: string;
  summary: string;
  start: string;
  end: string;
  all_day: boolean;
};

type PositionWeight = {
  symbol: string;
  account_id: string;
  market_value: number;
  weight_percent: number;
};

type ConcentrationWarning = {
  symbol: string;
  weight_percent: number;
  threshold_percent: number;
};

type MoneyDashboard = {
  total_market_value: number;
  is_stale: boolean;
  position_weights: PositionWeight[];
  concentration_warnings: ConcentrationWarning[];
  warnings: string[];
};

type AttentionItem = {
  description: string;
  severity: "low" | "medium" | "high";
};

type RecentSession = {
  session_id: string;
  started_at: string;
  status: string;
};

type IntegrationEntry = {
  name: string;
  connected: boolean;
  detail: string | null;
};

type Proposal = {
  proposal_id: string;
  summary: string;
  risk_level: string;
  status: string;
  created_at: string;
  expires_at: string;
};

type ProjectSummary = {
  project_id: string;
  name: string;
  status: string;
  committed_tasks: number;
  done_tasks: number;
  total_tasks: number;
  open_blockers: number;
};

type DashboardData = {
  user_id: string;
  generated_at: string;
  today: { meta: CardMeta; events: CalendarEvent[] };
  money: { meta: CardMeta; dashboard: MoneyDashboard | null };
  attention: { meta: CardMeta; items: AttentionItem[] };
  projects: { meta: CardMeta; projects: ProjectSummary[] };
  conversation: { meta: CardMeta; recent_sessions: RecentSession[] };
  integration_status: { meta: CardMeta; integrations: IntegrationEntry[] };
  approval_inbox: { meta: CardMeta; pending: Proposal[] };
};

function formatTimestamp(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function StatusBadge({ meta }: { meta: CardMeta }) {
  const labels: Record<CardStatus, string> = {
    ok: "Live",
    not_connected: "Not connected",
    no_data: "No data yet",
    not_available: "Not available",
  };
  const classes: Record<CardStatus, string> = {
    ok: "status-ok",
    not_connected: "status-neutral",
    no_data: "status-neutral",
    not_available: "status-neutral",
  };
  return (
    <span className={`status-badge ${classes[meta.status]}`}>{labels[meta.status]}</span>
  );
}

// PROMPT.md Phase 22 implement item 8 / verification 2: every card renders
// this same freshness/status line, so no card can silently omit it.
function CardMetaLine({ meta }: { meta: CardMeta }) {
  return (
    <span className="freshness" aria-live="polite">
      <StatusBadge meta={meta} />{" "}
      {meta.as_of ? `as of ${formatTimestamp(meta.as_of)}` : meta.detail || ""}
    </span>
  );
}

function TodayCard({ card }: { card: DashboardData["today"] }) {
  return (
    <section className="card" aria-labelledby="today-heading">
      <h2 id="today-heading">Today</h2>
      <CardMetaLine meta={card.meta} />
      {card.events.length === 0 ? (
        <p className="empty-note">No events today.</p>
      ) : (
        <ul>
          {card.events.map((event) => (
            <li key={event.event_id}>
              <strong>{event.summary}</strong>
              {!event.all_day && (
                <> — {new Date(event.start).toLocaleTimeString()}</>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MoneyCard({ card }: { card: DashboardData["money"] }) {
  const d = card.dashboard;
  return (
    <section className="card" aria-labelledby="money-heading">
      <h2 id="money-heading">Money</h2>
      <CardMetaLine meta={card.meta} />
      {!d ? (
        <p className="empty-note">{card.meta.detail || "No portfolio data available."}</p>
      ) : (
        <>
          <p>
            <strong>${d.total_market_value.toLocaleString()}</strong> total market value
            {d.is_stale && <span className="status-badge status-warn"> stale</span>}
          </p>
          {d.concentration_warnings.length > 0 && (
            <ul>
              {d.concentration_warnings.map((w) => (
                <li key={w.symbol}>
                  {w.symbol}: {w.weight_percent}% (threshold {w.threshold_percent}%)
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function AttentionCard({ card }: { card: DashboardData["attention"] }) {
  const severityClass: Record<AttentionItem["severity"], string> = {
    low: "status-neutral",
    medium: "status-warn",
    high: "status-danger",
  };
  return (
    <section className="card" aria-labelledby="attention-heading">
      <h2 id="attention-heading">Attention</h2>
      <CardMetaLine meta={card.meta} />
      {card.items.length === 0 ? (
        <p className="empty-note">Nothing needs your attention.</p>
      ) : (
        <ul>
          {card.items.map((item, index) => (
            <li key={index}>
              <span className={`status-badge ${severityClass[item.severity]}`}>
                {item.severity}
              </span>{" "}
              {item.description}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ProjectsCard({ card }: { card: DashboardData["projects"] }) {
  return (
    <section className="card" aria-labelledby="projects-heading">
      <h2 id="projects-heading">Projects</h2>
      <CardMetaLine meta={card.meta} />
      {card.projects.length === 0 ? (
        <p className="empty-note">{card.meta.detail || "No active projects yet."}</p>
      ) : (
        <ul>
          {card.projects.map((project) => (
            <li key={project.project_id}>
              <strong>{project.name}</strong> — {project.done_tasks}/{project.total_tasks} tasks done
              {project.open_blockers > 0 && (
                <span className="status-badge status-warn">
                  {" "}
                  {project.open_blockers} blocker{project.open_blockers === 1 ? "" : "s"}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      <p>
        <a href="/projects">View all projects →</a>
      </p>
    </section>
  );
}

function ConversationCard({ card }: { card: DashboardData["conversation"] }) {
  return (
    <section className="card" aria-labelledby="conversation-heading">
      <h2 id="conversation-heading">Conversation</h2>
      <CardMetaLine meta={card.meta} />
      {card.recent_sessions.length === 0 ? (
        <p className="empty-note">No conversations yet.</p>
      ) : (
        <ul>
          {card.recent_sessions.map((s) => (
            <li key={s.session_id}>{formatTimestamp(s.started_at)}</li>
          ))}
        </ul>
      )}
      <p>
        <a href="/chat">Open chat →</a>
      </p>
    </section>
  );
}

function IntegrationStatusCard({ card }: { card: DashboardData["integration_status"] }) {
  return (
    <section className="card" aria-labelledby="integrations-heading">
      <h2 id="integrations-heading">Integration status</h2>
      <CardMetaLine meta={card.meta} />
      <ul className="integration-list">
        {card.integrations.map((integration) => (
          <li key={integration.name}>
            <span
              className={`integration-dot ${
                integration.connected ? "integration-dot-connected" : "integration-dot-disconnected"
              }`}
              aria-hidden="true"
            />
            <span>
              {integration.name} — {integration.connected ? "connected" : "not connected"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ApprovalInboxCard({
  card,
  onDecide,
  busyProposalId,
}: {
  card: DashboardData["approval_inbox"];
  onDecide: (proposalId: string, decision: "approve" | "reject", summary: string) => void;
  busyProposalId: string | null;
}) {
  return (
    <section className="card" aria-labelledby="approvals-heading">
      <h2 id="approvals-heading">Approval inbox</h2>
      <CardMetaLine meta={card.meta} />
      {card.pending.length === 0 ? (
        <p className="empty-note">No actions awaiting approval.</p>
      ) : (
        <div role="group" aria-label="Actions requiring your approval">
          {card.pending.map((proposal) => (
            <div className="approval-item" key={proposal.proposal_id}>
              <p>
                {proposal.summary}{" "}
                <span className="status-badge status-warn">{proposal.risk_level} risk</span>
              </p>
              <div className="approval-actions">
                <button
                  type="button"
                  className="approval-button approval-button-approve"
                  aria-label={`Approve: ${proposal.summary}`}
                  disabled={busyProposalId === proposal.proposal_id}
                  onClick={() => onDecide(proposal.proposal_id, "approve", proposal.summary)}
                >
                  ✓ Approve
                </button>
                <button
                  type="button"
                  className="approval-button approval-button-reject"
                  aria-label={`Reject: ${proposal.summary}`}
                  disabled={busyProposalId === proposal.proposal_id}
                  onClick={() => onDecide(proposal.proposal_id, "reject", proposal.summary)}
                >
                  ✗ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyProposalId, setBusyProposalId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/dashboard?user_id=${encodeURIComponent(USER_ID)}`,
      );
      if (!response.ok) throw new Error(`dashboard request failed (${response.status})`);
      setData(await response.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load dashboard");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(proposalId: string, decision: "approve" | "reject", summary: string) {
    // A distinct, explicit confirmation step — approval actions must never
    // be mistaken for an ordinary button (PROMPT.md Phase 22 verification 3).
    const verb = decision === "approve" ? "Approve" : "Reject";
    if (!window.confirm(`${verb} this action?\n\n${summary}`)) return;

    setBusyProposalId(proposalId);
    try {
      if (decision === "approve") {
        await fetch(`${API_BASE_URL}/approvals/${proposalId}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approving_user_id: USER_ID }),
        });
      } else {
        await fetch(`${API_BASE_URL}/approvals/${proposalId}/reject`, { method: "POST" });
      }
      await load();
    } finally {
      setBusyProposalId(null);
    }
  }

  if (error) {
    return (
      <main className="dashboard">
        <h1>Echo</h1>
        <p role="alert">Could not load the dashboard: {error}</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="dashboard">
        <h1>Echo</h1>
        <p aria-live="polite">Loading dashboard…</p>
      </main>
    );
  }

  return (
    <main className="dashboard">
      <div className="dashboard-header">
        <h1>Echo</h1>
        <span className="freshness">Generated {formatTimestamp(data.generated_at)}</span>
      </div>
      <div className="dashboard-grid">
        <TodayCard card={data.today} />
        <MoneyCard card={data.money} />
        <AttentionCard card={data.attention} />
        <ApprovalInboxCard
          card={data.approval_inbox}
          onDecide={decide}
          busyProposalId={busyProposalId}
        />
        <ProjectsCard card={data.projects} />
        <ConversationCard card={data.conversation} />
        <IntegrationStatusCard card={data.integration_status} />
      </div>
    </main>
  );
}
