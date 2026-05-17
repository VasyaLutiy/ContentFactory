#!/usr/bin/env python3
"""Create ContentFactory labels, milestones, and issues from docs/github-issues.json.

Usage:
    GITHUB_TOKEN=... python scripts/sync_github_issues.py --dry-run
    GITHUB_TOKEN=... python scripts/sync_github_issues.py

The script is intentionally dependency-free so it can run before project tooling
is fully installed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "github-issues.json"
API_ROOT = "https://api.github.com"


def request(method: str, path: str, token: str, payload: dict | None = None) -> dict | list:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_ROOT}{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def upsert_label(repo: str, token: str, label: dict, dry_run: bool) -> None:
    print(f"label: {label['name']}")
    if dry_run:
        return
    try:
        request("POST", f"/repos/{repo}/labels", token, label)
    except HTTPError as exc:
        if exc.code != 422:
            raise
        request(
            "PATCH",
            f"/repos/{repo}/labels/{quote(label['name'], safe='')}",
            token,
            {"color": label["color"], "description": label["description"]},
        )


def get_milestones(repo: str, token: str) -> dict[str, int]:
    data = request("GET", f"/repos/{repo}/milestones?state=all&per_page=100", token)
    return {item["title"]: item["number"] for item in data}


def create_missing_milestones(repo: str, token: str, milestones: list[dict], dry_run: bool) -> dict[str, int]:
    existing = {} if dry_run else get_milestones(repo, token)
    for milestone in milestones:
        print(f"milestone: {milestone['title']}")
        if dry_run or milestone["title"] in existing:
            continue
        created = request("POST", f"/repos/{repo}/milestones", token, milestone)
        existing[created["title"]] = created["number"]
    return existing


def get_issues(repo: str, token: str) -> dict[str, dict]:
    data = request("GET", f"/repos/{repo}/issues?state=all&per_page=100", token)
    return {item["title"]: item for item in data if "pull_request" not in item}


def create_issues(repo: str, token: str, issues: list[dict], milestone_numbers: dict[str, int], dry_run: bool) -> None:
    existing = {} if dry_run else get_issues(repo, token)
    for issue in issues:
        existing_issue = existing.get(issue["title"])
        if existing_issue:
            print(f"issue: {issue['title']} -> existing #{existing_issue['number']}")
            continue

        print(f"issue: {issue['title']}")
        if dry_run:
            continue
        payload = {
            "title": issue["title"],
            "body": issue["body"],
            "labels": issue["labels"],
            "milestone": milestone_numbers.get(issue["milestone"]),
        }
        created = request("POST", f"/repos/{repo}/issues", token, payload)
        print(f"created: #{created['number']} {created['html_url']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token and not args.dry_run:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN, or run with --dry-run.")

    repo = manifest["repository"]
    token = token or "dry-run"
    for label in manifest["labels"]:
        upsert_label(repo, token, label, args.dry_run)
    milestone_numbers = create_missing_milestones(repo, token, manifest["milestones"], args.dry_run)
    create_issues(repo, token, manifest["issues"], milestone_numbers, args.dry_run)


if __name__ == "__main__":
    main()
