"""
GitLab API Client
=================
Wrapper around GitLab REST API for fetching MR data, project info,
and creating merge requests.
"""

import re
import logging
from urllib.parse import quote

import requests

from config import GITLAB_BASE, GITLAB_TOKEN, GITLAB_HEADERS

logger = logging.getLogger(__name__)

# Disable SSL warnings for internal GitLab instances
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


# ──────────────────────────────────────────────
# Project helpers
# ──────────────────────────────────────────────
def get_project_id(project_path: str) -> int | None:
    """Get GitLab project ID from its path (e.g. 'indiamart/soa/pdp_go')."""
    encoded_path = quote(project_path, safe="")
    url = f"{GITLAB_BASE}/api/v4/projects/{encoded_path}"
    resp = requests.get(url, headers=GITLAB_HEADERS, timeout=30, verify=False)
    if resp.status_code == 200:
        return resp.json().get("id")
    logger.error(
        "Failed to get project ID for %s: %s %s",
        project_path, resp.status_code, resp.text,
    )
    return None


def get_project_clone_url(project_path: str) -> str:
    """Build an HTTPS clone URL with embedded token for auth."""
    host = GITLAB_BASE.replace("https://", "").replace("http://", "")
    return f"https://oauth2:{GITLAB_TOKEN}@{host}/{project_path}.git"


def get_project_default_branch(project_id: int) -> str | None:
    """Fetch the default branch name for a project."""
    url = f"{GITLAB_BASE}/api/v4/projects/{project_id}"
    resp = requests.get(url, headers=GITLAB_HEADERS, timeout=30, verify=False)
    if resp.status_code == 200:
        return resp.json().get("default_branch", "main")
    return None


# ──────────────────────────────────────────────
# Merge Request helpers
# ──────────────────────────────────────────────
def extract_mr_info_from_commit_message(commit_message: str):
    """
    Extract project path and MR IID from a merge commit message.
    Example: "See merge request indiamart/soa/pdp_go!249"
    Returns (project_path, mr_iid) or (None, None).
    """
    pattern = r"See merge request (.+?)!(\d+)"
    match = re.search(pattern, commit_message)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def get_mr_details(project_id: int, mr_iid: int) -> dict | None:
    """Fetch the merge request metadata."""
    url = f"{GITLAB_BASE}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    resp = requests.get(url, headers=GITLAB_HEADERS, timeout=30, verify=False)
    if resp.status_code == 200:
        return resp.json()
    logger.error(
        "Failed to get MR details for project=%s MR=!%s: %s %s",
        project_id, mr_iid, resp.status_code, resp.text,
    )
    return None


def get_mr_changes(project_id: int, mr_iid: int) -> dict | None:
    """Fetch the merge request details + changes (diff) from GitLab API."""
    url = f"{GITLAB_BASE}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
    resp = requests.get(url, headers=GITLAB_HEADERS, timeout=60, verify=False)
    if resp.status_code == 200:
        return resp.json()
    logger.error(
        "Failed to get MR changes for project=%s MR=!%s: %s %s",
        project_id, mr_iid, resp.status_code, resp.text,
    )
    return None


def format_diff_for_llm(changes: list[dict]) -> str:
    """
    Convert GitLab's changes array into a human-readable diff string
    that the LLM can understand.
    """
    diff_parts = []
    for change in changes:
        file_path = change.get("new_path", change.get("old_path", "unknown"))
        status = "modified"
        if change.get("new_file"):
            status = "added"
        elif change.get("deleted_file"):
            status = "deleted"
        elif change.get("renamed_file"):
            old = change.get("old_path", "")
            status = f"renamed from {old}"

        diff_content = change.get("diff", "")

        diff_parts.append(
            f"### File: `{file_path}` ({status})\n"
            f"```diff\n{diff_content}\n```\n"
        )

    return "\n".join(diff_parts)


# ──────────────────────────────────────────────
# MR Creation
# ──────────────────────────────────────────────
def create_merge_request(
    project_id: int,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str,
) -> dict | None:
    """
    Create a new merge request via GitLab API.
    Returns the MR data dict on success, None on failure.
    """
    url = f"{GITLAB_BASE}/api/v4/projects/{project_id}/merge_requests"
    payload = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
        "labels": "documentation,automated",
        "remove_source_branch": True,
    }
    resp = requests.post(
        url, headers=GITLAB_HEADERS, json=payload, timeout=30, verify=False
    )

    if resp.status_code == 201:
        mr_data = resp.json()
        logger.info("✅ MR created: %s", mr_data.get("web_url"))
        return mr_data

    # If branch already has an open MR, try to find and return it
    if resp.status_code == 409:
        logger.warning("MR already exists for branch %s, fetching existing...", source_branch)
        return _find_existing_mr(project_id, source_branch)

    logger.error(
        "Failed to create MR: %s %s", resp.status_code, resp.text
    )
    return None


def _find_existing_mr(project_id: int, source_branch: str) -> dict | None:
    """Find an existing open MR for a given source branch."""
    url = (
        f"{GITLAB_BASE}/api/v4/projects/{project_id}/merge_requests"
        f"?source_branch={source_branch}&state=opened"
    )
    resp = requests.get(url, headers=GITLAB_HEADERS, timeout=30, verify=False)
    if resp.status_code == 200:
        mrs = resp.json()
        if mrs:
            return mrs[0]
    return None
