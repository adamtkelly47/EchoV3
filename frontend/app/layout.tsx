import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "Echo",
  description: "Echo — personal AI operating system",
};

// A real nav bar, added now that there are seven pages that need to reach
// each other (dashboard, chat, projects, monitors, trust, paper trading,
// email) — not premature scaffolding for a single link, the way
// app/page.tsx's own "Open chat →" link was enough when only two pages
// existed.
const NAV_LINKS: Array<{ href: string; label: string }> = [
  { href: "/", label: "Dashboard" },
  { href: "/chat", label: "Chat" },
  { href: "/email", label: "Email" },
  { href: "/projects", label: "Projects" },
  { href: "/monitors", label: "Monitors" },
  { href: "/trust", label: "Trust" },
  { href: "/paper-trading", label: "Paper trading" },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="site-nav" aria-label="Main">
          <ul>
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <a href={link.href}>{link.label}</a>
              </li>
            ))}
          </ul>
        </nav>
        {children}
      </body>
    </html>
  );
}
