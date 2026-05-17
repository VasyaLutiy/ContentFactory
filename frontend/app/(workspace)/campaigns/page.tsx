import Link from "next/link";
import { AppShell } from "@/app/_components/app-shell";

const campaigns = [
  {
    id: "neon-relic",
    title: "Neon Relic",
    channel: "TikTok US",
    episodes: 12,
    activeEpisode: "manual-drive-activation",
    owner: "Growth Studio",
  },
  {
    id: "clockmaker",
    title: "Clockmaker",
    channel: "YT Shorts",
    episodes: 8,
    activeEpisode: "hook-variant-b",
    owner: "Retention Ops",
  },
  {
    id: "arc-forge",
    title: "Arc Forge",
    channel: "TikTok LATAM",
    episodes: 5,
    activeEpisode: "cta-outro",
    owner: "UGC Cell",
  },
];

export default function CampaignsPage() {
  return (
    <AppShell
      title="Campaign Lab"
      description="Mock-ready planning surface for campaign and episode setup."
      status={["Static mode", "No API writes", "Editor contract draft"]}
    >
      <section className="panel">
        <div className="panel-head">
          <h2>Campaigns</h2>
          <Link className="action-link" href="/campaigns/neon-relic/episodes/manual-drive-activation">
            Open editor slice
          </Link>
        </div>

        <div className="table header-grid campaigns-grid">
          <div>Campaign</div>
          <div>Channel</div>
          <div>Episodes</div>
          <div>Owner</div>
          <div>Editor</div>
        </div>

        {campaigns.map((campaign) => (
          <div className="table campaigns-grid" key={campaign.id}>
            <div>
              <strong>{campaign.title}</strong>
              <small>{campaign.id}</small>
            </div>
            <span>{campaign.channel}</span>
            <span>{campaign.episodes}</span>
            <span>{campaign.owner}</span>
            <Link
              className="action-link"
              href={`/campaigns/${campaign.id}/episodes/${campaign.activeEpisode}`}
            >
              Episode editor
            </Link>
          </div>
        ))}
      </section>
    </AppShell>
  );
}
