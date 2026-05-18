import { AppShell } from "@/app/_components/app-shell";

export const dynamic = "force-dynamic";

type RecommendationCardData = {
  export_id: number;
  export_ids: number[];
  variant_label: string | null;
  confidence: "low" | "medium" | "high" | string;
  reason: string;
  evidence: string[];
  suggested_next_hook: string;
  suggested_next_edit: string;
  avg_watch_seconds: number | null;
  full_watch_percent: number | null;
  retention_note: string | null;
  no_text_experiment: boolean;
  text_metadata_source: string | null;
  warnings: string[];
};

type RecommendationResult = {
  cards: RecommendationCardData[];
  error: string | null;
};

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

const dashboardCampaignId = process.env.CONTENT_FACTORY_DASHBOARD_CAMPAIGN_ID?.trim() || "1";

function recommendationCardsUrl() {
  const apiBase = (
    process.env.CONTENT_FACTORY_API_BASE_URL ||
    process.env.NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
  const url = new URL("/api/v1/analytics/recommendation-cards", apiBase);
  url.searchParams.set("campaign_id", dashboardCampaignId);
  return url.toString();
}

async function fetchRecommendationCards(): Promise<RecommendationResult> {
  try {
    const response = await fetch(recommendationCardsUrl(), { cache: "no-store" });
    if (!response.ok) {
      return { cards: [], error: `Backend returned ${response.status} for campaign ${dashboardCampaignId}.` };
    }
    const payload: unknown = await response.json();
    if (!Array.isArray(payload)) {
      return { cards: [], error: "Backend returned an invalid recommendation payload." };
    }
    return { cards: payload as RecommendationCardData[], error: null };
  } catch {
    return { cards: [], error: "Recommendation service is unavailable." };
  }
}

function confidenceLabel(value: RecommendationCardData["confidence"]) {
  if (value === "high") {
    return "High confidence";
  }
  if (value === "low") {
    return "Low confidence";
  }
  return "Medium confidence";
}

export default async function DashboardPage() {
  const recommendationResult = await fetchRecommendationCards();
  const recommendations = recommendationResult.cards;

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
            <h2>Recommendations</h2>
            <span className="badge muted">
              Campaign {dashboardCampaignId}: {recommendations.length} ready
            </span>
          </div>
          {recommendationResult.error ? (
            <div className="recommendation-state" role="status">
              <strong>Recommendations unavailable</strong>
              <p>{recommendationResult.error}</p>
            </div>
          ) : recommendations.length === 0 ? (
            <div className="recommendation-state" role="status">
              <strong>No recommendations yet</strong>
              <p>Campaign {dashboardCampaignId} has no export analytics snapshots ready for scoring.</p>
            </div>
          ) : (
            <div className="recommendation-grid" aria-label="Recommendation cards">
              {recommendations.map((item) => (
                <article className="recommendation-card" key={item.export_id}>
                  <div className="recommendation-head">
                    <code>export_id={item.export_id}</code>
                    <span className={`confidence-chip ${item.confidence}`}>{confidenceLabel(item.confidence)}</span>
                  </div>
                  <div className="recommendation-block">
                    <span>Reason</span>
                    <p>{item.reason}</p>
                  </div>
                  <div className="recommendation-block">
                    <span>Evidence</span>
                    <ul>
                      {item.evidence.map((evidence) => (
                        <li key={evidence}>{evidence}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="recommendation-block">
                    <span>Suggested next hook</span>
                    <p>{item.suggested_next_hook}</p>
                  </div>
                  <div className="recommendation-block">
                    <span>Suggested edit</span>
                    <p>{item.suggested_next_edit}</p>
                  </div>
                  <div className="recommendation-meta-row">
                    <div>
                      <span>Export IDs</span>
                      <p>{item.export_ids.join(", ") || item.export_id}</p>
                    </div>
                    <div>
                      <span>Variant label</span>
                      <p>{item.variant_label || "Unlabeled variant"}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

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
