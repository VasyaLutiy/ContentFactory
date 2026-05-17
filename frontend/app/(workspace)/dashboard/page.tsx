import { AppShell } from "@/app/_components/app-shell";

const activeJobs = [
  {
    id: "job-2026-0516-01",
    campaign: "Neon Relic",
    episode: "Manual Drive Activation",
    status: "Queued",
    stage: "Prompt validation",
    eta: "06m",
  },
  {
    id: "job-2026-0516-02",
    campaign: "Clockmaker",
    episode: "Hook Variant B",
    status: "Running",
    stage: "LTX pass 1",
    eta: "11m",
  },
  {
    id: "job-2026-0516-03",
    campaign: "Arc Forge",
    episode: "CTA Outro",
    status: "Needs review",
    stage: "Policy gate",
    eta: "manual",
  },
];

const policyChecks = [
  {
    rule: "First hook text <= 0.3s",
    state: "Required",
  },
  {
    rule: "No-text variants",
    state: "Experiment only",
  },
  {
    rule: "Burn-in overlay for TikTok",
    state: "Required",
  },
  {
    rule: "Safe area margin",
    state: "7.5% min",
  },
];

export default function DashboardPage() {
  return (
    <AppShell
      title="Factory Dashboard"
      description="Operational snapshot for campaigns, policy gates, and active render flow."
      status={["API contract ready", "Worker pending", "Comfy external"]}
    >
      <div className="grid two-col">
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
            <div className="table dashboard-grid" key={job.id}>
              <code>{job.id}</code>
              <div>
                <strong>{job.campaign}</strong>
                <small>{job.episode}</small>
              </div>
              <span>{job.status}</span>
              <span>{job.stage}</span>
              <span>{job.eta}</span>
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
                <strong>{item.state}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
