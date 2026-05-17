import { AppShell } from "@/app/_components/app-shell";

const queueRows = [
  {
    jobId: "job-2026-0516-02",
    campaign: "Clockmaker",
    episode: "Hook Variant B",
    priority: "P1",
    status: "Rendering",
    worker: "gpu-worker-03",
    updated: "14:02 UTC",
  },
  {
    jobId: "job-2026-0516-01",
    campaign: "Neon Relic",
    episode: "Manual Drive Activation",
    priority: "P1",
    status: "Queued",
    worker: "pending",
    updated: "13:58 UTC",
  },
  {
    jobId: "job-2026-0516-03",
    campaign: "Arc Forge",
    episode: "CTA Outro",
    priority: "P2",
    status: "Policy Review",
    worker: "review-bot",
    updated: "13:54 UTC",
  },
];

export default function QueuePage() {
  return (
    <AppShell
      title="Render Queue"
      description="Static operations view for queue ordering, workers, and failure triage."
      status={["Queue depth: 3", "Avg wait: 09m", "Failed: 0"]}
    >
      <section className="panel">
        <div className="panel-head">
          <h2>Queue Jobs</h2>
          <span className="badge">Refresh every 30s (mock)</span>
        </div>

        <div className="table header-grid queue-grid">
          <div>Job</div>
          <div>Campaign / Episode</div>
          <div>Priority</div>
          <div>Status</div>
          <div>Worker</div>
          <div>Updated</div>
        </div>

        {queueRows.map((job) => (
          <div className="table queue-grid" key={job.jobId}>
            <code>{job.jobId}</code>
            <div>
              <strong>{job.campaign}</strong>
              <small>{job.episode}</small>
            </div>
            <span>{job.priority}</span>
            <span>{job.status}</span>
            <span>{job.worker}</span>
            <span>{job.updated}</span>
          </div>
        ))}
      </section>
    </AppShell>
  );
}
