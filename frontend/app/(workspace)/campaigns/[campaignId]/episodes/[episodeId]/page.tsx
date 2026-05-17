import Link from "next/link";
import { AppShell } from "@/app/_components/app-shell";

const assetRows = [
  { slot: "Hook clip", source: "s3://mock/hook-v04.mp4", duration: "00:03.2", state: "Approved" },
  { slot: "Bridge visual", source: "s3://mock/bridge-v02.mp4", duration: "00:05.4", state: "Draft" },
  { slot: "CTA frame", source: "s3://mock/cta-v01.png", duration: "00:01.4", state: "Approved" },
];

const timelineBeats = [
  { time: "00:00.0", beat: "Hook", text: "Manual drive engaged in 3...2...1", camera: "Crash zoom" },
  { time: "00:00.8", beat: "Setup", text: "If your edits stall at frame 12...", camera: "Left pan" },
  { time: "00:03.0", beat: "Tension", text: "Switch to relic mode and keep momentum", camera: "Center lock" },
  { time: "00:06.0", beat: "Payoff", text: "Result in one take, export instantly", camera: "Wide reveal" },
  { time: "00:08.2", beat: "CTA", text: "Comment RELOAD for template", camera: "Static close" },
];

export default async function EpisodeEditorPage({
  params,
}: {
  params: Promise<{ campaignId: string; episodeId: string }>;
}) {
  const { campaignId, episodeId } = await params;

  return (
    <AppShell
      title="Episode Editor"
      description={`Campaign ${campaignId} / Episode ${episodeId} mock vertical slice.`}
      status={["Autosave: off", "Static timeline", "Render handoff mock"]}
    >
      <div className="grid editor-grid">
        <section className="panel">
          <div className="panel-head">
            <h2>Episode Details</h2>
            <Link className="action-link" href="/campaigns">
              Back to campaigns
            </Link>
          </div>

          <form className="form-grid" action="#">
            <label>
              Episode title
              <input defaultValue="Manual Drive Activation" name="title" />
            </label>
            <label>
              Format
              <select defaultValue="tiktok-9x16" name="format">
                <option value="tiktok-9x16">TikTok 9:16</option>
                <option value="shorts-9x16">YouTube Shorts 9:16</option>
              </select>
            </label>
            <label>
              Voice preset
              <select defaultValue="energetic-female" name="voice">
                <option value="energetic-female">Energetic Female</option>
                <option value="calm-male">Calm Male</option>
              </select>
            </label>
            <label>
              Hook objective
              <input defaultValue="Stop-scroll in first 0.3s" name="objective" />
            </label>
            <label className="full-width">
              Prompt block
              <textarea
                defaultValue="Fast tempo cut. Keep captions max 7 words each beat. Preserve safe area and punch in at 0.8s."
                name="prompt"
                rows={4}
              />
            </label>
          </form>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Asset Map</h2>
            <span className="badge">3 slots</span>
          </div>
          <div className="table header-grid assets-grid">
            <div>Slot</div>
            <div>Source</div>
            <div>Duration</div>
            <div>State</div>
          </div>
          {assetRows.map((asset) => (
            <div className="table assets-grid" key={asset.slot}>
              <strong>{asset.slot}</strong>
              <code>{asset.source}</code>
              <span>{asset.duration}</span>
              <span>{asset.state}</span>
            </div>
          ))}
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <h2>Text Beats Timeline</h2>
          <span className="badge muted">00:00.0 - 00:09.0</span>
        </div>
        <div className="timeline">
          {timelineBeats.map((beat) => (
            <article className="beat-row" key={`${beat.time}-${beat.beat}`}>
              <div className="beat-time">{beat.time}</div>
              <div className="beat-content">
                <strong>{beat.beat}</strong>
                <p>{beat.text}</p>
              </div>
              <div className="beat-camera">{beat.camera}</div>
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
