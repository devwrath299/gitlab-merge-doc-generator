"""
GitLab Merge-Triggered Documentation Automation
=================================================
Receives GitLab webhook events on merge to development branch, clones/pulls
the target repo, generates or updates documentation using skills, then
creates a merge request with the changes.

Flow:
  Webhook → Extract MR info → Clone/Pull repo → Checkout development →
  Create feature branch → Generate/Update docs → Commit & Push → Create MR
"""

import logging
from datetime import datetime

from flask import Flask, request, jsonify

from config import WEBHOOK_PORT, GITLAB_BASE, LLM_MODEL
from services.gitlab_client import (
    extract_mr_info_from_commit_message,
    get_project_id,
    get_project_clone_url,
    get_mr_details,
    get_mr_changes,
    format_diff_for_llm,
)
from services.git_ops import (
    get_local_repo_path,
    clone_or_pull,
    checkout_development_branch,
    create_feature_branch,
    has_docs_folder,
)
from services.doc_generator import generate_full_docs
from services.doc_updater import update_docs_from_diff
from services.mr_creator import create_docs_mr

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Flask App
# ──────────────────────────────────────────────
app = Flask(__name__)


# ──────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────
def run_docs_pipeline(
    project_path: str,
    project_id: int,
    mr_iid: int,
    mr_details: dict,
    changes: list[dict],
) -> dict:
    """
    Execute the full documentation automation pipeline:
    1. Clone or pull the repo
    2. Checkout development branch
    3. Create a feature branch
    4. Generate or update docs
    5. Commit, push, and create MR

    Returns a result dict with status and MR URL.
    """
    logger.info("=" * 60)
    logger.info(
        "🚀 Starting docs pipeline for %s MR !%s",
        project_path, mr_iid,
    )
    logger.info("=" * 60)

    # ── Step 1: Clone or Pull ──
    clone_url = get_project_clone_url(project_path)
    local_path = get_local_repo_path(project_path)

    try:
        repo = clone_or_pull(clone_url, local_path)
    except Exception as e:
        logger.error("❌ Clone/pull failed: %s", e)
        return {"status": "error", "reason": f"Clone/pull failed: {e}"}

    # ── Step 2: Checkout development branch ──
    try:
        dev_branch = checkout_development_branch(repo)
    except Exception as e:
        logger.error("❌ Branch checkout failed: %s", e)
        return {"status": "error", "reason": f"Branch checkout failed: {e}"}

    # ── Step 3: Create feature branch ──
    try:
        feature_branch = create_feature_branch(repo, mr_iid)
    except Exception as e:
        logger.error("❌ Feature branch creation failed: %s", e)
        return {"status": "error", "reason": f"Feature branch failed: {e}"}

    # ── Step 4: Generate or update docs ──
    try:
        if has_docs_folder(local_path):
            # Docs exist → incremental update based on MR diff
            logger.info("📝 Docs exist — running incremental update...")
            diff_text = format_diff_for_llm(changes)

            # Truncate if too large
            max_chars = 50000
            if len(diff_text) > max_chars:
                diff_text = diff_text[:max_chars] + "\n\n... (diff truncated)"
                logger.warning("Diff truncated to %d chars", max_chars)

            changed_files = update_docs_from_diff(local_path, diff_text, mr_details)
        else:
            # No docs → full generation from scratch
            logger.info("📚 No docs/ folder — generating full documentation...")
            changed_files = generate_full_docs(local_path)
    except Exception as e:
        logger.error("❌ Documentation generation/update failed: %s", e)
        return {"status": "error", "reason": f"Doc generation failed: {e}"}

    if not changed_files:
        logger.info("📭 No documentation changes needed.")
        return {
            "status": "skipped",
            "reason": "No documentation changes needed for this MR",
        }

    # ── Step 5: Commit, push, and create MR ──
    try:
        mr_author = mr_details.get("author", {}).get("name", "Unknown")
        mr_title = mr_details.get("title", "N/A")

        mr_data = create_docs_mr(
            repo=repo,
            project_id=project_id,
            branch_name=feature_branch,
            target_branch=dev_branch,
            mr_iid=mr_iid,
            mr_title=mr_title,
            mr_author=mr_author,
            changed_files=changed_files,
        )

        if mr_data:
            mr_url = mr_data.get("web_url", "unknown")
            logger.info("🎉 Pipeline complete! MR: %s", mr_url)
            return {
                "status": "success",
                "mr_url": mr_url,
                "mr_iid": mr_data.get("iid"),
                "files_changed": changed_files,
                "docs_mode": "update" if has_docs_folder(local_path) else "generate",
            }
        else:
            return {
                "status": "error",
                "reason": "Failed to create documentation MR",
                "files_changed": changed_files,
            }

    except Exception as e:
        logger.error("❌ MR creation failed: %s", e)
        return {"status": "error", "reason": f"MR creation failed: {e}"}


# ──────────────────────────────────────────────
# Webhook Handlers
# ──────────────────────────────────────────────
@app.route("/", methods=["POST"])
def webhook():
    """Handle incoming GitLab webhook events."""
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "No JSON payload received"}), 400

    object_kind = payload.get("object_kind", "")

    if object_kind == "push":
        return handle_push_event(payload)
    elif object_kind == "merge_request":
        return handle_merge_request_event(payload)
    else:
        commits = payload.get("commits", [])
        if commits:
            return handle_push_event(payload)
        logger.info("Ignoring event of kind: %s", object_kind)
        return jsonify({"status": "ignored", "reason": f"Unhandled event: {object_kind}"}), 200


def handle_push_event(payload: dict):
    """Process a push event — look for merge commits and run pipeline."""
    branch = payload.get("ref", "").replace("refs/heads/", "")
    commits = payload.get("commits", [])
    project_id_from_payload = payload.get("project", {}).get("id")

    results = []

    for commit in commits:
        commit_message = commit.get("message", "")
        author_name = commit.get("author", {}).get("name", "Unknown")

        logger.info(
            "POST / | branch=%s author=%s commit_message=\"%s\"",
            branch, author_name, commit_message.strip()[:100],
        )

        project_path, mr_iid = extract_mr_info_from_commit_message(commit_message)
        if not project_path or not mr_iid:
            logger.info("Not a merge commit, skipping.")
            continue

        logger.info("🔀 Detected merge: %s!%s", project_path, mr_iid)

        project_id = project_id_from_payload or get_project_id(project_path)
        if not project_id:
            results.append({"mr": f"!{mr_iid}", "status": "error", "reason": "Could not resolve project ID"})
            continue

        mr_details = get_mr_details(project_id, mr_iid)
        mr_changes = get_mr_changes(project_id, mr_iid)

        if not mr_changes:
            results.append({"mr": f"!{mr_iid}", "status": "error", "reason": "Could not fetch MR changes"})
            continue

        changes = mr_changes.get("changes", [])
        if not changes:
            results.append({"mr": f"!{mr_iid}", "status": "skipped", "reason": "No file changes"})
            continue

        logger.info("📝 Found %d changed files in MR !%s", len(changes), mr_iid)

        # Run the full pipeline
        result = run_docs_pipeline(
            project_path=project_path,
            project_id=project_id,
            mr_iid=mr_iid,
            mr_details=mr_details or mr_changes,
            changes=changes,
        )
        result["mr"] = f"!{mr_iid}"
        result["project"] = project_path
        results.append(result)

    if not results:
        return jsonify({"status": "ok", "message": "No merge commits found in push event"}), 200

    return jsonify({"status": "ok", "results": results}), 200


def handle_merge_request_event(payload: dict):
    """Process a merge_request event — only act on 'merge' action."""
    attrs = payload.get("object_attributes", {})
    action = attrs.get("action", "")
    state = attrs.get("state", "")

    if action != "merge" and state != "merged":
        logger.info("MR event action=%s, state=%s — skipping", action, state)
        return jsonify({"status": "ignored", "reason": f"MR action={action}, not merged"}), 200

    mr_iid = attrs.get("iid")
    project_id = payload.get("project", {}).get("id")
    project_path = payload.get("project", {}).get("path_with_namespace", "unknown")

    if not mr_iid or not project_id:
        return jsonify({"error": "Missing MR IID or project ID"}), 400

    logger.info("🔀 MR event: %s!%s merged", project_path, mr_iid)

    mr_details = get_mr_details(project_id, mr_iid)
    mr_changes = get_mr_changes(project_id, mr_iid)

    if not mr_changes:
        return jsonify({"error": "Could not fetch MR changes"}), 500

    changes = mr_changes.get("changes", [])
    if not changes:
        return jsonify({"status": "skipped", "reason": "No file changes"}), 200

    logger.info("📝 Found %d changed files in MR !%s", len(changes), mr_iid)

    # Run the full pipeline
    result = run_docs_pipeline(
        project_path=project_path,
        project_id=project_id,
        mr_iid=mr_iid,
        mr_details=mr_details or mr_changes,
        changes=changes,
    )
    result["mr"] = f"!{mr_iid}"
    result["project"] = project_path

    status_code = 200 if result["status"] in ("success", "skipped") else 500
    return jsonify(result), status_code


# ──────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("GitLab Documentation Automation Pipeline")
    logger.info("  GitLab:     %s", GITLAB_BASE)
    logger.info("  LLM Model:  %s", LLM_MODEL)
    logger.info("  Port:       %s", WEBHOOK_PORT)
    logger.info("=" * 60)

    app.run(host="0.0.0.0", port=WEBHOOK_PORT, debug=False)
