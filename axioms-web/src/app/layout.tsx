import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/contexts/auth";
import { AppShell } from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "Axioms AI System",
  description: "Human-governed multi-agent workspace for research, teaching, and professional writing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
