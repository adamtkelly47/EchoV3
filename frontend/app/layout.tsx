import type { ReactNode } from "react";

import "./globals.css";

export const metadata = {
  title: "Echo",
  description: "Echo — personal AI operating system",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
