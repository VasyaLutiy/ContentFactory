const activeJobs = [
  { id: "job-demo-1", episode: "Manual Drive Activation", status: "queued", step: "validate" },
  { id: "job-demo-2", episode: "Clockmaker Hook A", status: "running", step: "ltx video" },
];

const policyChecks = [
  { label: "First hook text <= 0.3s", value: "Required" },
  { label: "No-text variants", value: "Explicit experiment only" },
  { label: "Burn-in overlay", value: "Required for TikTok export" },
];

export default function DashboardPage() {
  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">ContentFactory</div>
        <nav>
          <a className="active" href="/">Dashboard</a>
          <a href="/campaigns">Campaign Lab</a>
          <a href="/queue">Render Queue</a>
          <a href="/analytics">Analytics</a>
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>Factory Dashboard</h1>
            <p>Render jobs, export policy, and retention-focused production state.</p>
          </div>
          <div className="status-row">
            <span>API contract ready</span>
            <span>Worker pending</span>
            <span>Comfy external</span>
          </div>
        </header>

        <div className="grid">
          <section className="panel">
            <h2>Active Jobs</h2>
            <div className="table">
              {activeJobs.map((job) => (
                <div className="row" key={job.id}>
                  <div>
                    <strong>{job.episode}</strong>
                    <small>{job.id}</small>
                  </div>
                  <span>{job.status}</span>
                  <span>{job.step}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>TikTok Text Policy</h2>
            <div className="policy-list">
              {policyChecks.map((item) => (
                <div className="policy" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
