import Link from "next/link";
import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer: ReactNode;
};

export default function AuthShell({ title, subtitle, children, footer }: Props) {
  return (
    <div className="auth-page">
      <header className="auth-header">
        <Link href="/" className="home-logo">
          <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden="true">
            <path d="M6 26C6 13 14 5 27 5c0 13-8 21-21 21Z" fill="currentColor" />
            <path d="M6 26 20 12" stroke="#EEF4E8" strokeWidth="2" strokeLinecap="round" fill="none" />
          </svg>
          FloraGuide
        </Link>
      </header>

      <main className="auth-main">
        <div className="auth-card">
          <h1 className="auth-title">{title}</h1>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
          {children}
          <p className="auth-footer">{footer}</p>
        </div>
      </main>
    </div>
  );
}
