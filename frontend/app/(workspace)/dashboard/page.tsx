import { AppShell } from "@/app/_components/app-shell";

const activeJobs = [
  {
    id: "job-2026-0516-01",
    campaign: "Neon Relic",
    episode: "Manual Drive Activation",
    status: "Queued",
    statusTone: "queued",
    stage: "Prompt validation",
    eta: "06m",
  },
  {
    id: "job-2026-0516-02",
    campaign: "Clockmaker",
    episode: "Hook Variant B",
    status: "Running",
    statusTone: "running",
    stage: "LTX pass 1",
    eta: "11m",
  },
  {
    id: "job-2026-0516-03",
    campaign: "Arc Forge",
    episode: "CTA Outro",
    status: "Needs review",
    statusTone: "review",
    stage: "Policy gate",
    eta: "manual",
  },
];

const policyChecks = [
  {
    rule: "First hook text <= 0.3s",
    state: "Required",
    tone: "required",
  },
  {
    rule: "No-text variants",
    state: "Experiment only",
    tone: "experiment",
  },
  {
    rule: "Burn-in overlay for TikTok",
    state: "Required",
    tone: "required",
  },
  {
    rule: "Safe area margin",
    state: "7.5% min",
    tone: "ok",
  },
];

const dashboardStats = [
  { label: "Pipeline", value: "3 jobs", meta: "2 automated, 1 manual gate" },
  { label: "Review load", value: "1 hold", meta: "Policy gate before render" },
  { label: "Worker", value: "Pending", meta: "External Comfy queue" },
];

export default function DashboardPage() {
  return (
    <AppShell
      title="Factory Dashboard"
      description="Operational snapshot for campaigns, policy gates, and active render flow."
      status={["API contract ready", "Worker pending", "Comfy external"]}
    >
      <div className="dashboard-summary" aria-label="Dashboard summary">
        {dashboardStats.map((item) => (
          <div className="stat-tile" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.meta}</small>
          </div>
        ))}
      </div>

      <div className="dashboard-layout">
        <section className="panel">
          <div className="panel-head">
            <h2>Active Jobs</h2>
            <span className="badge">{activeJobs.length} in pipeline</span>
          </div>
          <div className="table header-grid dashboard-grid">
            <div>ID</div>
            <div>Campaign / Episode</div>
            <div>Status</div>
            <div>Stage</div>
            <div>ETA</div>
          </div>
          {activeJobs.map((job) => (
            <div className="table dashboard-grid job-row" key={job.id}>
              <code data-label="ID">{job.id}</code>
              <div className="job-title" data-label="Campaign / Episode">
                <strong>{job.campaign}</strong>
                <small>{job.episode}</small>
              </div>
              <span className="job-cell" data-label="Status">
                <span className={`status-chip ${job.statusTone}`}>{job.status}</span>
              </span>
              <span className="job-cell" data-label="Stage">
                <span className="stage-text">{job.stage}</span>
              </span>
              <span className="job-cell" data-label="ETA">
                <span className="eta-text">{job.eta}</span>
              </span>
            </div>
          ))}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Policy Snapshot</h2>
            <span className="badge muted">Batch #16/#17</span>
          </div>
          <div className="policy-list">
            {policyChecks.map((item) => (
              <div className="policy" key={item.rule}>
                <span>{item.rule}</span>
                <strong className={`policy-state ${item.tone}`}>{item.state}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
