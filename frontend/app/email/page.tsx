"use client";

// PROMPT.md Phase 20-21 frontend coverage. No business logic here — every
// value comes from the real /email endpoints (CONSTITUTION.md: Frontend
// layer must never own business logic). Every write (reply, archive, label,
// trash, send, draft) is a proposal that must go through the same shared
// Approval Engine every other domain's writes do — there is no button on
// this page that sends, deletes, or modifies anything directly. Approving
// and executing are two separate, explicit clicks, never merged into one,
// matching the deliberate human-review discipline PROMPT.md Phase 26 built
// for voice (spoken summary vs. full readable review) applied here too.

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

type EmailMessage = {
  provider_message_id: string;
  thread_id: string;
  subject: string;
  snippet: string;
  from_address: string;
  to_addresses: string[];
  date: string;
  label_ids: string[];
  is_unread: boolean;
  classification: {
    category: string;
    needs_response: boolean;
    action_items: string[];
  } | null;
};

type Proposal = {
  proposal_id: string;
  summary: string;
  payload: Record<string, unknown>;
  risk_level: string;
  status: string;
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

function ProposalPanel({ proposal, onChanged }: { proposal: Proposal; onChanged: (p: Proposal) => void }) {
  const [busy, setBusy] = useState(false);

  async function approve() {
    setBusy(true);
    try {
      await api(`/approvals/${proposal.proposal_id}/approve`, {
        method: "POST",
        body: JSON.stringify({ approving_user_id: USER_ID, confirmation_method: "readable" }),
      });
      const refreshed = await api<Proposal>(`/approvals/${proposal.proposal_id}`);
      onChanged(refreshed);
    } finally {
      setBusy(false);
    }
  }

  async function execute() {
    setBusy(true);
    try {
      const executed = await api<Proposal>(
        `/email/proposals/${proposal.proposal_id}/execute?user_id=${encodeURIComponent(USER_ID)}`,
        { method: "POST" },
      );
      onChanged(executed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="item-row">
      <p>
        {proposal.summary}{" "}
        <span className="status-badge status-neutral">{proposal.risk_level}</span>{" "}
        <span className="status-badge status-neutral">{proposal.status}</span>
      </p>
      {proposal.status === "awaiting_approval" && (
        <div className="item-actions">
          <button type="button" className="btn btn-subtle" disabled={busy} onClick={approve}>
            Approve (readable confirmation)
          </button>
        </div>
      )}
      {proposal.status === "approved" && (
        <div className="item-actions">
          <button type="button" className="btn" disabled={busy} onClick={execute}>
            Execute
          </button>
        </div>
      )}
    </div>
  );
}

function MessageRow({ message, onProposal }: { message: EmailMessage; onProposal: (p: Proposal) => void }) {
  const [classification, setClassification] = useState(message.classification);
  const [replyBody, setReplyBody] = useState("");
  const [showReply, setShowReply] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function classify() {
    setBusy(true);
    try {
      const result = await api<EmailMessage["classification"]>(
        `/email/messages/${message.provider_message_id}/classify?user_id=${encodeURIComponent(USER_ID)}`,
        { method: "POST" },
      );
      setClassification(result);
    } finally {
      setBusy(false);
    }
  }

  async function summarizeThread() {
    setBusy(true);
    try {
      const result = await api<{ summary: string }>(
        `/email/threads/${message.thread_id}/summary?user_id=${encodeURIComponent(USER_ID)}`,
      );
      setSummary(result.summary);
    } finally {
      setBusy(false);
    }
  }

  async function proposeReply() {
    if (!replyBody.trim()) return;
    setBusy(true);
    try {
      const proposal = await api<Proposal>(`/email/messages/${message.provider_message_id}/reply`, {
        method: "POST",
        body: JSON.stringify({ user_id: USER_ID, body: replyBody }),
      });
      onProposal(proposal);
      setReplyBody("");
      setShowReply(false);
    } finally {
      setBusy(false);
    }
  }

  async function proposeArchive() {
    setBusy(true);
    try {
      const proposal = await api<Proposal>(
        `/email/messages/${message.provider_message_id}/archive?user_id=${encodeURIComponent(USER_ID)}`,
        { method: "POST" },
      );
      onProposal(proposal);
    } finally {
      setBusy(false);
    }
  }

  async function proposeTrash() {
    setBusy(true);
    try {
      const proposal = await api<Proposal>(
        `/email/messages/${message.provider_message_id}/trash?user_id=${encodeURIComponent(USER_ID)}`,
        { method: "POST" },
      );
      onProposal(proposal);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="item-row">
      <p>
        <strong>{message.subject || "(no subject)"}</strong>{" "}
        {message.is_unread && <span className="status-badge status-warn">unread</span>}
      </p>
      <p className="empty-note">
        {message.from_address} — {message.snippet}
      </p>
      {classification && (
        <p className="empty-note">
          {classification.category}
          {classification.needs_response ? " — needs a response" : ""}
          {classification.action_items.length > 0 && ` — ${classification.action_items.join("; ")}`}
        </p>
      )}
      {summary && <p className="empty-note">Thread summary: {summary}</p>}
      <div className="item-actions">
        <button type="button" className="btn btn-subtle" disabled={busy} onClick={classify}>
          Classify
        </button>
        <button type="button" className="btn btn-subtle" disabled={busy} onClick={summarizeThread}>
          Summarize thread
        </button>
        <button type="button" className="btn btn-subtle" disabled={busy} onClick={() => setShowReply((v) => !v)}>
          Reply
        </button>
        <button type="button" className="btn btn-subtle" disabled={busy} onClick={proposeArchive}>
          Archive
        </button>
        <button type="button" className="btn btn-subtle" disabled={busy} onClick={proposeTrash}>
          Trash
        </button>
      </div>
      {showReply && (
        <div className="inline-form">
          <label>
            Reply body
            <input value={replyBody} onChange={(e) => setReplyBody(e.target.value)} />
          </label>
          <button type="button" className="btn" disabled={busy} onClick={proposeReply}>
            Propose reply
          </button>
        </div>
      )}
    </div>
  );
}

export default function EmailPage() {
  const [messages, setMessages] = useState<EmailMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [proposals, setProposals] = useState<Record<string, Proposal>>({});

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({ user_id: USER_ID });
      if (query.trim()) params.set("query", query);
      const result = await api<{ messages: EmailMessage[] }>(`/email/messages?${params.toString()}`);
      setMessages(result.messages);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load messages");
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  function recordProposal(proposal: Proposal) {
    setProposals((prev) => ({ ...prev, [proposal.proposal_id]: proposal }));
  }

  return (
    <main className="page">
      <h1>Email</h1>
      <p className="freshness">
        Gmail read/write — every write is a proposal gated by the same Approval Engine every other
        domain uses. No message is ever sent, deleted, or modified without an explicit approve and a
        separate explicit execute.
      </p>

      {error && <p role="alert">{error}</p>}

      <section className="card">
        <h2>Connection</h2>
        <p className="empty-note">
          Not connected yet?{" "}
          <a href={`${API_BASE_URL}/email/oauth/authorize?user_id=${encodeURIComponent(USER_ID)}`}>
            Connect Gmail →
          </a>
        </p>
      </section>

      <section className="card">
        <h2>Messages</h2>
        <div className="inline-form">
          <label>
            Search
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="is:unread" />
          </label>
          <button type="button" className="btn btn-subtle" onClick={load}>
            Search
          </button>
        </div>
        {!messages ? (
          <p aria-live="polite">Loading…</p>
        ) : messages.length === 0 ? (
          <p className="empty-note">No messages — connect Gmail and sync first.</p>
        ) : (
          <div className="section-list">
            {messages.map((m) => (
              <MessageRow key={m.provider_message_id} message={m} onProposal={recordProposal} />
            ))}
          </div>
        )}
      </section>

      {Object.keys(proposals).length > 0 && (
        <section className="card">
          <h2>Proposed actions</h2>
          <div className="section-list">
            {Object.values(proposals).map((p) => (
              <ProposalPanel key={p.proposal_id} proposal={p} onChanged={recordProposal} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
