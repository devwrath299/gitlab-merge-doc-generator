"""
Centralized Configuration
=========================
All environment variables and settings used by the application.
"""

import os

# ──────────────────────────────────────────────
# GitLab Configuration
# ──────────────────────────────────────────────
GITLAB_BASE = os.getenv("GITLAB_BASE", "https://scm.intermesh.net")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "gfUmpHVxY1vsDPWirM2X")

# ──────────────────────────────────────────────
# LLM Configuration
# ──────────────────────────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-DGjyNestL3pldh_BTzqC7Q")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://imllm.intermesh.net/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-6")

# ──────────────────────────────────────────────
# Application Configuration
# ──────────────────────────────────────────────
REPOS_DIR = os.getenv("REPOS_DIR", "repos")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))

# ──────────────────────────────────────────────
# Skills Paths (relative to project root)
# ──────────────────────────────────────────────
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
CODEBASE_DOCS_SKILL = os.path.join(SKILLS_DIR, "codebase-docs-skill", "SKILL.md")
DOCS_UPDATE_SKILL = os.path.join(SKILLS_DIR, "docs-update-skill", "SKILL.md")
GIT_OPS_SKILL = os.path.join(SKILLS_DIR, "git-ops-skill", "SKILL.md")
MR_CREATION_SKILL = os.path.join(SKILLS_DIR, "mr-creation-skill", "SKILL.md")

# ──────────────────────────────────────────────
# Derived Settings
# ──────────────────────────────────────────────
GITLAB_HEADERS = {
    "PRIVATE-TOKEN": GITLAB_TOKEN,
    "Content-Type": "application/json",
}
