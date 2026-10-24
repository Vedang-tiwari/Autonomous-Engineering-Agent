import './globals.css';
import React from 'react';

export const metadata = {
  title: 'Autonomous Engineering Agent | AI Software Engineer',
  description: 'An agentic AI software-engineering system that autonomously analyzes repositories, diagnoses issues, modifies code, executes tests in isolated sandboxes, reviews changes, and prepares GitHub Pull Requests.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="navbar">
          <div className="logo-group">
            <div className="logo-badge">🤖</div>
            <div className="title-text">
              Autonomous <span>Engineering Agent</span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span className="status-badge status-live">Agent Core Operational</span>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              API Docs
            </a>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
