from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
DEFAULT_PAGES_PER_REPO = 4

REPOSITORIES = [
    {
        "program": "Developer Experience Modernization",
        "repo": "microsoft/vscode",
        "portfolio_domain": "Developer Tools",
    },
    {
        "program": "Cloud Native Platform Reliability",
        "repo": "kubernetes/kubernetes",
        "portfolio_domain": "Cloud Platform",
    },
    {
        "program": "Data Platform Orchestration",
        "repo": "apache/airflow",
        "portfolio_domain": "Data Engineering",
    },
    {
        "program": "Runtime Platform Stabilization",
        "repo": "nodejs/node",
        "portfolio_domain": "Runtime Engineering",
    },
    {
        "program": "Language Ecosystem Delivery",
        "repo": "rust-lang/rust",
        "portfolio_domain": "Language Platform",
    },
]


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-PMO-Control-Tower",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request_json(url: str) -> object:
    request = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API Request Failed: {exc.code} {url}\n{body}") from exc


def build_url(path: str, params: dict[str, object] | None = None) -> str:
    url = f"{GITHUB_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def fetch_repository_metadata(repo: str) -> dict[str, object]:
    metadata = request_json(build_url(f"/repos/{repo}"))
    if not isinstance(metadata, dict):
        raise TypeError(f"Unexpected Metadata Payload For {repo}")
    return metadata


def fetch_work_items(repo: str, pages: int) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for page in range(1, pages + 1):
        print(f"Fetching {repo} Work Items Page {page}/{pages}", flush=True)
        payload = request_json(
            build_url(
                f"/repos/{repo}/issues",
                {
                    "state": "all",
                    "sort": "created",
                    "direction": "desc",
                    "per_page": PER_PAGE,
                    "page": page,
                },
            )
        )
        if not isinstance(payload, list):
            raise TypeError(f"Unexpected Issues Payload For {repo}")
        if not payload:
            break
        items.extend(payload)
        time.sleep(0.25)
    return items


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    pages = int(os.getenv("GITHUB_PMO_PAGES_PER_REPO", DEFAULT_PAGES_PER_REPO))
    all_items: list[dict[str, object]] = []
    all_metadata: list[dict[str, object]] = []
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for source in REPOSITORIES:
        repo = source["repo"]
        print(f"Fetching Repository Metadata: {repo}", flush=True)
        metadata = fetch_repository_metadata(repo)
        metadata["_program"] = source["program"]
        metadata["_portfolio_domain"] = source["portfolio_domain"]
        metadata["_generated_at"] = generated_at
        all_metadata.append(metadata)

        for item in fetch_work_items(repo, pages):
            item["_program"] = source["program"]
            item["_portfolio_domain"] = source["portfolio_domain"]
            item["_source_repo"] = repo
            item["_generated_at"] = generated_at
            all_items.append(item)

    (RAW_DIR / "repository_metadata.json").write_text(json.dumps(all_metadata, indent=2), encoding="utf-8")
    (RAW_DIR / "github_work_items.json").write_text(json.dumps(all_items, indent=2), encoding="utf-8")

    print(f"Downloaded {len(all_items):,} Real GitHub Work Items Across {len(REPOSITORIES)} Programs.")
    print(f"- {RAW_DIR / 'repository_metadata.json'}")
    print(f"- {RAW_DIR / 'github_work_items.json'}")


if __name__ == "__main__":
    main()
