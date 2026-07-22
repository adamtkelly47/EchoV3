"use client";

// PROMPT.md Phase 27 frontend coverage. No business logic here — every
// gain/loss, comparison, and thesis-quality number is computed server-side
// by domains/portfolio/policies.py's pure functions and read verbatim from
// GET /portfolio/hypothetical-trades/{id} (CONSTITUTION.md: Frontend layer
// must never own business logic). There is no order/execute button
// anywhere on this page — matching the backend's own structural guarantee
// that no real or hypothetical trade endpoint ever places an order.

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://localhost:8000";
const USER_ID = "local-dev-user";

type HypotheticalTrade = {
  trade_id: string;
  symbol: string;
  action: "buy" | "sell" | string;
  quantity: number;
  hypothetical_price: number;
  rationale: string;
  expected_outcome: string;
  expected_horizon_days: number;
  status: "open" | "closed" | string;
  review_note: string | null;
  closing_price: number | null;
};

type Evaluation = {
  trade: HypotheticalTrade;
  gain_loss_percent: number | null;
  comparison_vs_no_action_percent: number | null;
  thesis_direction_correct: boolean | null;
  days_to_realize: number | null;
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

function pct(value: number | null): string {
  return value === null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function TradeCard({ tradeId, onChanged }: { tradeId: string; onChanged: () => void }) {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setEvaluation(await api<Evaluation>(`/portfolio/hypothetical-trades/${tradeId}`));
  }, [tradeId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function recordSample() {
    setBusy(true);
    try {
      await api(`/portfolio/hypothetical-trades/${tradeId}/samples`, { method: "POST" });
      await refresh();
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function closeTrade() {
    if (!reviewNote.trim()) return;
    setBusy(true);
    try {
      await api(`/portfolio/hypothetical-trades/${tradeId}/close`, {
        method: "POST",
        body: JSON.stringify({ review_note: reviewNote }),
      });
      setReviewNote("");
      await refresh();
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  if (!evaluation) return <div className="item-row">Loading…</div>;
  const t = evaluation.trade;

  return (
    <div className="item-row">
      <p>
        <strong>
          {t.action.toUpperCase()} {t.quantity} {t.symbol}
        </strong>{" "}
        @ ${t.hypothetical_price.toFixed(2)}{" "}
        <span className={`status-badge ${t.status === "closed" ? "status-neutral" : "status-ok"}`}>
          {t.status}
        </span>
      </p>
      <p className="empty-note">{t.rationale}</p>
      <div className="metric-grid">
        <div className="metric-tile">
          <span className="metric-label">Gain / loss</span>
          <span className="metric-value">{pct(evaluation.gain_loss_percent)}</span>
        </div>
        <div className="metric-tile">
          <span className="metric-label">Vs. no action</span>
          <span className="metric-value">{pct(evaluation.comparison_vs_no_action_percent)}</span>
        </div>
        <div className="metric-tile">
          <span className="metric-label">Thesis direction</span>
          <span className="metric-value">
            {evaluation.thesis_direction_correct === null
              ? "—"
              : evaluation.thesis_direction_correct
                ? "Correct"
                : "Incorrect"}
          </span>
        </div>
      </div>
      {t.status === "open" && (
        <div className="inline-form">
          <button type="button" className="btn btn-subtle" disabled={busy} onClick={recordSample}>
            Record price sample
          </button>
          <label>
            Review note (to close)
            <input value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} />
          </label>
          <button type="button" className="btn" disabled={busy} onClick={closeTrade}>
            Close trade
          </button>
        </div>
      )}
      {t.review_note && <p className="empty-note">Review: {t.review_note}</p>}
    </div>
  );
}

export default function PaperTradingPage() {
  const [tradeIds, setTradeIds] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("");
  const [rationale, setRationale] = useState("");
  const [expectedOutcome, setExpectedOutcome] = useState("");
  const [horizonDays, setHorizonDays] = useState("30");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const trades = await api<HypotheticalTrade[]>(
        `/portfolio/hypothetical-trades?user_id=${encodeURIComponent(USER_ID)}`,
      );
      setTradeIds(trades.map((t) => t.trade_id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed to load hypothetical trades");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function proposeTrade() {
    if (!symbol.trim() || !quantity || !rationale.trim() || !expectedOutcome.trim()) return;
    setBusy(true);
    try {
      await api("/portfolio/hypothetical-trades", {
        method: "POST",
        body: JSON.stringify({
          user_id: USER_ID,
          symbol: symbol.toUpperCase(),
          action,
          quantity: Number(quantity),
          rationale,
          expected_outcome: expectedOutcome,
          expected_horizon_days: Number(horizonDays),
        }),
      });
      setSymbol("");
      setQuantity("");
      setRationale("");
      setExpectedOutcome("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <h1>Paper trading</h1>
      <p className="freshness">
        Evaluate trade reasoning without enabling trading — no order or execute endpoint exists
        anywhere in this codebase, for real trades or hypothetical ones.
      </p>

      {error && <p role="alert">{error}</p>}

      <section className="card">
        <h2>Propose a hypothetical trade</h2>
        <div className="inline-form">
          <label>
            Symbol
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
          </label>
          <label>
            Action
            <select value={action} onChange={(e) => setAction(e.target.value as "buy" | "sell")}>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </label>
          <label>
            Quantity
            <input type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          </label>
          <label>
            Horizon (days)
            <input type="number" value={horizonDays} onChange={(e) => setHorizonDays(e.target.value)} />
          </label>
        </div>
        <div className="inline-form">
          <label>
            Rationale
            <input value={rationale} onChange={(e) => setRationale(e.target.value)} />
          </label>
          <label>
            Expected outcome
            <input value={expectedOutcome} onChange={(e) => setExpectedOutcome(e.target.value)} />
          </label>
          <button type="button" className="btn" disabled={busy} onClick={proposeTrade}>
            Propose (real live quote, no execution)
          </button>
        </div>
      </section>

      {!tradeIds ? (
        <p aria-live="polite">Loading trades…</p>
      ) : tradeIds.length === 0 ? (
        <p className="empty-note">No hypothetical trades yet.</p>
      ) : (
        <div className="section-list">
          {tradeIds.map((id) => (
            <TradeCard key={id} tradeId={id} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  );
}
