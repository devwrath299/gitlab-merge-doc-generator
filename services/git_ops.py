"""
Git Operations Service
======================
Handles local git operations: clone, pull, branch management,
commit, and push using GitPython.
"""

import os
import subprocess
import logging
from datetime import datetime

from git import Repo, GitCommandError

from config import REPOS_DIR

logger = logging.getLogger(__name__)

# Ensure repos directory exists
os.makedirs(REPOS_DIR, exist_ok=True)


def get_local_repo_path(project_path: str) -> str:
    """
    Derive a local filesystem path for a given GitLab project path.
    e.g. 'indiamart/soa/pdp_go' → 'repos/indiamart_soa_pdp_go'
    """
    safe_name = project_path.replace("/", "_")
    return os.path.join(REPOS_DIR, safe_name)


def clone_or_pull(clone_url: str, local_path: str) -> Repo:
    """
    Clone the repository if it doesn't exist locally.
    If it already exists, fetch and pull latest changes.
    Returns the Repo object.
    """
    if os.path.isdir(os.path.join(local_path, ".git")):
        logger.info("📂 Repo already exists at %s — pulling latest...", local_path)
        repo = Repo(local_path)
        repo.git.update_environment(GIT_SSL_NO_VERIFY="1")
        repo.git.fetch("--all", "--prune")
        return repo
    else:
        logger.info("📥 Cloning repo to %s ...", local_path)
        env = os.environ.copy()
        env["GIT_SSL_NO_VERIFY"] = "1"
        result = subprocess.run(
            ["git", "clone", clone_url, local_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed: {result.stderr}")
        logger.info("✅ Clone complete.")
        repo = Repo(local_path)
        repo.git.update_environment(GIT_SSL_NO_VERIFY="1")
        return repo


def checkout_development_branch(repo: Repo) -> str:
    """
    Checkout the development branch. Falls back to main → master if
    development doesn't exist.
    Returns the name of the branch checked out.
    """
    # Stash any local changes first
    try:
        repo.git.stash()
    except GitCommandError:
        pass  # Nothing to stash

    for branch_name in ["development", "main", "master"]:
        try:
            # Check if branch exists remotely
            remote_refs = [ref.name for ref in repo.remotes.origin.refs]
            remote_branch = f"origin/{branch_name}"

            if remote_branch in remote_refs:
                # Checkout and track remote branch
                try:
                    repo.git.checkout(branch_name)
                except GitCommandError:
                    # Branch doesn't exist locally yet — create tracking branch
                    repo.git.checkout("-b", branch_name, f"origin/{branch_name}")

                repo.git.pull("origin", branch_name)
                logger.info("✅ Checked out branch: %s", branch_name)
                return branch_name

        except GitCommandError as e:
            logger.warning("Could not checkout %s: %s", branch_name, e)
            continue

    raise RuntimeError("Could not find development, main, or master branch")


def create_feature_branch(repo: Repo, mr_iid: int) -> str:
    """
    Create a new feature branch for documentation updates.
    Returns the branch name.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    branch_name = f"docs/auto-update-{mr_iid}-{timestamp}"

    try:
        repo.git.checkout("-b", branch_name)
        logger.info("🌿 Created feature branch: %s", branch_name)
        return branch_name
    except GitCommandError as e:
        logger.error("Failed to create branch %s: %s", branch_name, e)
        raise


def has_docs_folder(repo_path: str) -> bool:
    """Check if a docs/ folder exists in the repository."""
    docs_path = os.path.join(repo_path, "docs")
    exists = os.path.isdir(docs_path)
    logger.info(
        "📁 docs/ folder %s at %s",
        "EXISTS" if exists else "DOES NOT EXIST",
        repo_path,
    )
    return exists


def commit_and_push(repo: Repo, branch_name: str, mr_iid: int, changed_sections: list[str]) -> bool:
    """
    Stage docs/ changes, commit with a descriptive message, and push.
    Returns True if push succeeded, False if there was nothing to commit.
    """
    docs_path = os.path.join(repo.working_dir, "docs")

    # Stage all changes in docs/
    repo.git.add(docs_path, "--all")

    # Check if there are staged changes
    if not repo.index.diff("HEAD") and not repo.untracked_files:
        logger.info("📭 No documentation changes to commit.")
        return False

    # Build commit message
    sections_list = ", ".join(changed_sections) if changed_sections else "full documentation"
    commit_msg = (
        f"docs: auto-update documentation for MR !{mr_iid}\n\n"
        f"Automated documentation update triggered by merge of MR !{mr_iid}.\n"
        f"Updated sections: {sections_list}"
    )

    repo.index.commit(commit_msg)
    logger.info("💾 Committed documentation changes.")

    # Push to remote
    try:
        repo.git.push("origin", branch_name, "--force-with-lease")
        logger.info("🚀 Pushed branch %s to remote.", branch_name)
        return True
    except GitCommandError as e:
        # If force-with-lease fails, try regular push
        logger.warning("Force-with-lease failed, trying regular push: %s", e)
        try:
            repo.git.push("origin", branch_name)
            logger.info("🚀 Pushed branch %s to remote (regular push).", branch_name)
            return True
        except GitCommandError as e2:
            logger.error("Failed to push branch %s: %s", branch_name, e2)
            raise


def get_repo_file_tree(repo_path: str, max_depth: int = 4) -> str:
    """
    Get a text representation of the repository file tree.
    Used to give the LLM context about the repo structure.
    Skips common non-essential directories.
    """
    skip_dirs = {
        ".git", "node_modules", "vendor", "venv", ".venv",
        "__pycache__", ".idea", ".vscode", "dist", "build",
        ".terraform", ".next",
    }
    skip_extensions = {".pyc", ".pyo", ".so", ".o", ".a", ".dylib"}

    lines = []

    def _walk(path: str, prefix: str, depth: int):
        if depth > max_depth:
            lines.append(f"{prefix}... (depth limit)")
            return

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return

        dirs = []
        files = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                if entry not in skip_dirs:
                    dirs.append(entry)
            else:
                _, ext = os.path.splitext(entry)
                if ext not in skip_extensions:
                    files.append(entry)

        for f in files:
            lines.append(f"{prefix}{f}")
        for d in dirs:
            lines.append(f"{prefix}{d}/")
            _walk(os.path.join(path, d), prefix + "  ", depth + 1)

    _walk(repo_path, "", 0)
    return "\n".join(lines)


def read_file_content(file_path: str, max_chars: int = 10000) -> str:
    """Read file content, truncating if too large."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
            if len(content) == max_chars:
                content += "\n\n... (file truncated due to size)"
            return content
    except (OSError, UnicodeDecodeError) as e:
        return f"(Could not read file: {e})"
