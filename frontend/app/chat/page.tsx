"use client";

// Phase 8 minimal chat UI. No business logic here — this only renders
// state and calls the backend API (CONSTITUTION.md: Frontend layer must
// never own business logic). The backend URL is hardcoded to localhost for
// this local-dev-only phase; real deployment configuration is a later
// phase's concern, not retrofitted here.

import { useState } from "react";

const API_BASE_URL = "http://localhost:8000";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const response = await fetch(`${API_BASE_URL}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: "local-dev-user" }),
    });
    const data = await response.json();
    setSessionId(data.session_id);
    return data.session_id;
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const activeSessionId = await ensureSession();
      const response = await fetch(
        `${API_BASE_URL}/conversations/${activeSessionId}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        },
      );
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (reader) {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          const delta = decoder.decode(value, { stream: true });
          setMessages((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: "assistant",
              content: next[next.length - 1].content + delta,
            };
            return next;
          });
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 640 }}>
      <h1>Echo — Chat</h1>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
        {messages.map((message, index) => (
          <div key={index}>
            <strong>{message.role === "user" ? "You" : "Echo"}:</strong> {message.content}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && sendMessage()}
          placeholder="Ask something, e.g. what time is it?"
          style={{ flex: 1, padding: "0.5rem" }}
          disabled={busy}
        />
        <button onClick={sendMessage} disabled={busy}>
          Send
        </button>
      </div>
    </main>
  );
}
