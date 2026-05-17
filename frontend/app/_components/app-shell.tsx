import { AppShellNav } from "./app-shell-nav";
import { CopilotPanel } from "./copilot-panel";

export function AppShell({
  title,
  description,
  status,
  children,
}: {
  title: string;
  description: string;
  status?: string[];
  children: React.ReactNode;
}) {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">ContentFactory</div>
        <AppShellNav />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>{title}</h1>
            <p>{description}</p>
          </div>

          {status && status.length > 0 ? (
            <div className="status-row" aria-label="Status">
              {status.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          ) : null}
        </header>

        {children}
      </section>

      <CopilotPanel />
    </main>
  );
}
