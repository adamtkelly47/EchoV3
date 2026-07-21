// No business logic belongs here — the frontend renders only, per
// Docs/CONSTITUTION.md's Frontend layer responsibilities. The unified
// dashboard (Today/Money/Attention/Projects/Conversation) is Phase 22;
// this status page is just a landing point until then.

export default function StatusPage() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "3rem" }}>
      <h1>Echo</h1>
      <p>Frontend container is running.</p>
      <p>
        <a href="/chat">Open chat →</a>
      </p>
    </main>
  );
}
