// Phase 1 scaffolding only: proves the frontend container boots and serves.
// No business logic belongs here — the frontend renders only, per
// Docs/CONSTITUTION.md's Frontend layer responsibilities. Real dashboard/chat
// UI begins in Phase 8 (minimal conversation vertical slice) and Phase 22
// (unified dashboard).

export default function StatusPage() {
  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "3rem" }}>
      <h1>Echo</h1>
      <p>Phase 1 — Docker development foundation.</p>
      <p>Frontend container is running. No product UI exists yet.</p>
    </main>
  );
}
