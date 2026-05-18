from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.artifacts.storage import ArtifactStorage
from app.db.repos.asset import AssetRepository
from app.integrations.scripts.execution import (
    ExpectedArtifact,
    LegacyScriptResult,
    run_legacy_command,
)
from app.integrations.scripts.legacy_paths import legacy_script_path
from app.schemas.common import AssetKind


@dataclass(frozen=True)
class TikTokAnalyticsRequest:
    video_ids: tuple[str, ...]
    cdp_endpoint: str | None = None
    cookies_path: Path | None = None
    show: bool = False


def build_tiktok_analytics_command(request: TikTokAnalyticsRequest) -> list[str]:
    cmd = ["python", str(legacy_script_path("tt_analytics.py"))]
    if request.cdp_endpoint:
        cmd.extend(["--cdp", request.cdp_endpoint])
    if request.cookies_path:
        cmd.extend(["--cookies", str(request.cookies_path)])
    if request.show:
        cmd.append("--show")
    cmd.extend(request.video_ids)
    return cmd


def expected_tiktok_analytics_artifacts(
    request: TikTokAnalyticsRequest,
) -> tuple[ExpectedArtifact, ...]:
    out_dir = legacy_script_path("tt_analytics.py").parent / "tt_data"
    artifacts: list[ExpectedArtifact] = []
    for video_id_or_url in request.video_ids:
        video_id = extract_tiktok_video_id(video_id_or_url)
        artifacts.append(ExpectedArtifact(out_dir / f"{video_id}.json", AssetKind.JSON))
        artifacts.append(ExpectedArtifact(out_dir / f"{video_id}.png", AssetKind.SCREENSHOT))
    return tuple(artifacts)


def run_tiktok_analytics(
    request: TikTokAnalyticsRequest,
    *,
    storage: ArtifactStorage | None = None,
    namespace: str | None = None,
    asset_repository: AssetRepository | None = None,
    metadata: dict[str, Any] | None = None,
    render_job_id: str | None = None,
    render_step_kind: str | None = None,
    parent_asset_ids: tuple[int, ...] = (),
) -> LegacyScriptResult:
    return run_legacy_command(
        build_tiktok_analytics_command(request),
        expected_artifacts=expected_tiktok_analytics_artifacts(request),
        storage=storage,
        namespace=namespace,
        asset_repository=asset_repository,
        metadata=metadata,
        render_job_id=render_job_id,
        render_step_kind=render_step_kind,
        parent_asset_ids=parent_asset_ids,
    )


def extract_tiktok_video_id(value: str) -> str:
    if value.isdigit():
        return value
    match = re.search(r"/(?:analytics|video)/(\d+)", value)
    if match is None:
        raise ValueError(f"Can't extract TikTok video ID from: {value}")
    return match.group(1)
