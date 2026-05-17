#!/usr/bin/env python3
"""Close completed delivery issues after a pull request is merged.

The script closes only Batch issues referenced by explicit close/fix/resolve
keywords. Epic issues close when every configured Batch dependency is closed.
It is dependency-free so it can run in GitHub Actions without project setup.
"""

from __future__ import annotations

import json
import os
import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "docs" / "issue-closure-map.json"
API_ROOT = "https://api.github.com"
CLOSING_LINE = re.compile(r"\b(close[sd]?|fix(e[sd])?|resolve[sd]?)\b", re.IGNORECASE)
ISSUE_REF = re.compile(r"#(\d+)")
STATUS_LABELS = {"status:needs-review", "status:approved"}


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


def load_config() -> dict:
    path = Path(os.getenv("CLOSURE_MAP_PATH", DEFAULT_MAP))
    return json.loads(path.read_text())


def allowed_base_patterns(default_branch: str | None) -> list[str]:
    configured = os.getenv("CLOSURE_BASE_BRANCHES")
    if configured:
        return [item.strip() for item in configured.split(",") if item.strip()]
    return [default_branch] if default_branch else []


def base_is_allowed(base_ref: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatchcase(base_ref, pattern) for pattern in patterns)


def extract_closing_issue_numbers(*texts: str | None) -> set[int]:
    numbers: set[int] = set()
    for text in texts:
        for line in (text or "").splitlines():
            if not CLOSING_LINE.search(line):
                continue
            numbers.update(int(match) for match in ISSUE_REF.findall(line))
    return numbers


def label_names(issue: dict) -> set[str]:
    return {label["name"] for label in issue.get("labels", [])}


def is_batch(issue: dict) -> bool:
    return "type:batch" in label_names(issue)


def is_epic(issue: dict) -> bool:
    return "type:epic" in label_names(issue)


def ensure_label(repo: str, token: str, label: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"dry-run: ensure label {label['name']}")
        return
    try:
        request("GET", f"/repos/{repo}/labels/{quote(label['name'], safe='')}", token)
    except HTTPError as exc:
        if exc.code != 404:
            raise
        request("POST", f"/repos/{repo}/labels", token, label)


def get_issue(repo: str, token: str, number: int) -> dict:
    return request("GET", f"/repos/{repo}/issues/{number}", token)


def validate_issue_metadata(issue: dict, expected_title: str, expected_label: str) -> None:
    number = issue["number"]
    if issue.get("pull_request"):
        raise SystemExit(f"#{number} is a pull request, expected an issue.")
    if issue.get("title") != expected_title:
        raise SystemExit(
            f"#{number} title mismatch: expected {expected_title!r}, got {issue.get('title')!r}."
        )
    if expected_label not in label_names(issue):
        raise SystemExit(f"#{number} is missing required label {expected_label!r}.")


def validate_closure_map(repo: str, token: str, config: dict) -> None:
    for batch in config.get("batches", []):
        issue = get_issue(repo, token, batch["batch"])
        validate_issue_metadata(issue, batch["title"], "type:batch")

    for epic in config.get("epics", []):
        issue = get_issue(repo, token, epic["epic"])
        validate_issue_metadata(issue, epic["title"], "type:epic")


def close_issue(repo: str, token: str, issue: dict, comment: str, dry_run: bool) -> None:
    number = issue["number"]
    existing_labels = label_names(issue)
    labels = sorted((existing_labels - STATUS_LABELS) | {"status:done"})
    if dry_run:
        print(f"dry-run: close #{number} with labels {', '.join(labels)}")
        return

    request("POST", f"/repos/{repo}/issues/{number}/comments", token, {"body": comment})
    request(
        "PATCH",
        f"/repos/{repo}/issues/{number}",
        token,
        {"state": "closed", "state_reason": "completed", "labels": labels},
    )


def close_batch_issues(repo: str, token: str, pr_number: int, numbers: set[int], dry_run: bool) -> list[int]:
    closed: list[int] = []
    for number in sorted(numbers):
        issue = get_issue(repo, token, number)
        if issue.get("pull_request"):
            print(f"skip #{number}: pull request, not issue")
            continue
        if not is_batch(issue):
            print(f"skip #{number}: not labeled type:batch")
            continue
        if issue["state"] == "closed":
            print(f"skip #{number}: already closed")
            closed.append(number)
            continue
        close_issue(
            repo,
            token,
            issue,
            f"Closed automatically because pull request #{pr_number} was merged.",
            dry_run,
        )
        closed.append(number)
    return closed


def all_batches_closed(repo: str, token: str, batch_numbers: list[int]) -> bool:
    for number in batch_numbers:
        issue = get_issue(repo, token, number)
        if issue.get("state") != "closed":
            return False
    return True


def close_ready_epics(repo: str, token: str, pr_number: int, config: dict, dry_run: bool) -> list[int]:
    closed: list[int] = []
    for item in config.get("epics", []):
        epic_number = item["epic"]
        batches = item["batches"]
        if not all_batches_closed(repo, token, batches):
            print(f"skip epic #{epic_number}: open batches remain")
            continue

        issue = get_issue(repo, token, epic_number)
        if not is_epic(issue):
            print(f"skip epic #{epic_number}: not labeled type:epic")
            continue
        if issue["state"] == "closed":
            print(f"skip epic #{epic_number}: already closed")
            closed.append(epic_number)
            continue

        batch_refs = ", ".join(f"#{number}" for number in batches)
        close_issue(
            repo,
            token,
            issue,
            (
                f"Closed automatically after pull request #{pr_number} was merged. "
                f"All configured batches are closed: {batch_refs}."
            ),
            dry_run,
        )
        closed.append(epic_number)
    return closed


def main() -> None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    pr_number_raw = os.getenv("PR_NUMBER")
    dry_run = os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}
    config = load_config()

    if not repo:
        repo = config["repository"]
    if not token and not dry_run:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN.")
    if not pr_number_raw:
        raise SystemExit("Set PR_NUMBER.")

    token = token or "dry-run"
    pr_number = int(pr_number_raw)
    ensure_label(repo, token, config["status_done_label"], dry_run)
    validate_closure_map(repo, token, config)
    pr = request("GET", f"/repos/{repo}/pulls/{pr_number}", token)
    if not pr.get("merged"):
        print(f"skip PR #{pr_number}: not merged")
        return
    default_branch = os.getenv("DEFAULT_BRANCH")
    base_ref = pr.get("base", {}).get("ref", "")
    patterns = allowed_base_patterns(default_branch)
    if not base_is_allowed(base_ref, patterns):
        print(f"skip PR #{pr_number}: base is {base_ref}, allowed bases are {patterns}")
        return

    batch_numbers = extract_closing_issue_numbers(pr.get("title"), pr.get("body"))
    if not batch_numbers:
        print(f"PR #{pr_number} has no explicit closing issue references")
    closed_batches = close_batch_issues(repo, token, pr_number, batch_numbers, dry_run)
    closed_epics = close_ready_epics(repo, token, pr_number, config, dry_run)
    print(
        "closed batches: "
        f"{closed_batches or 'none'}; closed epics: {closed_epics or 'none'}"
    )


if __name__ == "__main__":
    try:
        main()
    except HTTPError as exc:
        sys.stderr.write(f"GitHub API error {exc.code}: {exc.read().decode('utf-8')}\n")
        raise
