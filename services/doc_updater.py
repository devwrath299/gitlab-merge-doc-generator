"""
Documentation Updater Service
==============================
Incrementally updates existing documentation based on merge request diffs.
Uses the docs-update-skill to identify affected doc sections and update them.
"""

import os
import json
import logging

from config import DOCS_UPDATE_SKILL
from services.llm_client import call_llm, load_skill
from services.git_ops import read_file_content

logger = logging.getLogger(__name__)


def update_docs_from_diff(
    repo_path: str,
    diff_text: str,
    mr_details: dict,
) -> list[str]:
    """
    Update existing documentation based on an MR diff.
    Only modifies doc files that are affected by the code changes.

    Returns a list of updated/created doc file paths (relative to repo root).
    """
    logger.info("🔄 Starting incremental documentation update...")

    # 1. Load the docs-update skill
    system_prompt = load_skill(DOCS_UPDATE_SKILL)

    # 2. Read the existing docs structure
    docs_dir = os.path.join(repo_path, "docs")
    existing_docs = _read_existing_docs(docs_dir)

    # 3. Build the user prompt
    mr_title = mr_details.get("title", "N/A")
    mr_description = mr_details.get("description", "No description")
    source_branch = mr_details.get("source_branch", "N/A")
    target_branch = mr_details.get("target_branch", "N/A")

    user_prompt = f"""A merge request has been merged. Update the existing documentation based on the changes.

## Merge Request Info
- **Title:** {mr_title}
- **Source Branch:** {source_branch} → **Target Branch:** {target_branch}
- **Description:** {mr_description}

## Existing Documentation Structure

{existing_docs}

## Code Changes (Diff)

{diff_text}

---

Analyze the diff, identify which documentation files are affected, and return
a JSON array of updates. Each update must have:
- "file_path": relative path from repo root (e.g., "docs/05_api_documentation/api_index.md")
- "action": "update", "create", or "delete"
- "reason": brief explanation of why this doc file needs updating
- "content": the complete updated file content (for "update" and "create" actions)

Return ONLY the JSON array, no other text. If no documentation updates are needed,
return an empty array: []
"""

    # 4. Call LLM
    llm_response = call_llm(system_prompt, user_prompt, max_tokens=16000)

    # 5. Parse and apply updates
    updated_files = _apply_doc_updates(repo_path, llm_response)

    logger.info(
        "✅ Incremental update complete. %d files modified.",
        len(updated_files),
    )
    return updated_files


def _read_existing_docs(docs_dir: str) -> str:
    """
    Read the existing docs/ folder and build a summary of its structure
    and content snippets for the LLM.
    """
    if not os.path.isdir(docs_dir):
        return "(No existing docs/ directory found)"

    parts = []
    parts.append("### Documentation File Tree\n```")

    for root, dirs, files in sorted(os.walk(docs_dir)):
        dirs.sort()
        level = root.replace(docs_dir, "").count(os.sep)
        indent = "  " * level
        folder_name = os.path.basename(root)
        parts.append(f"{indent}{folder_name}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            parts.append(f"{sub_indent}{f}")

    parts.append("```\n")

    # Include content of each doc file (truncated)
    parts.append("### Existing Documentation Content\n")
    file_count = 0
    max_files = 30  # Limit to avoid token overflow

    for root, _, files in sorted(os.walk(docs_dir)):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            if file_count >= max_files:
                parts.append(f"\n... ({file_count}+ doc files — remaining omitted)\n")
                return "\n".join(parts)

            file_path = os.path.join(root, fname)
            rel_path = os.path.relpath(file_path, os.path.dirname(docs_dir))
            content = read_file_content(file_path, max_chars=3000)

            parts.append(f"#### `{rel_path}`\n```markdown\n{content}\n```\n")
            file_count += 1

    return "\n".join(parts)


def _apply_doc_updates(repo_path: str, llm_response: str) -> list[str]:
    """
    Parse the LLM's JSON response and apply documentation updates.
    """
    updated_files = []

    # Extract JSON from the response (handle markdown code blocks)
    json_str = llm_response.strip()
    if json_str.startswith("```"):
        # Remove markdown code block wrapper
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        json_str = json_str.strip()

    try:
        updates = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        logger.error("Response was: %s", llm_response[:500])
        # Attempt to find JSON array in the response
        updates = _extract_json_from_text(llm_response)
        if updates is None:
            return []

    if not isinstance(updates, list):
        logger.error("Expected JSON array, got: %s", type(updates))
        return []

    for update in updates:
        file_path = update.get("file_path", "")
        action = update.get("action", "")
        reason = update.get("reason", "")
        content = update.get("content", "")

        if not file_path:
            continue

        full_path = os.path.join(repo_path, file_path)

        if action == "delete":
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info("  🗑️  Deleted: %s (reason: %s)", file_path, reason)
                updated_files.append(file_path)

        elif action in ("update", "create"):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            symbol = "📝" if action == "update" else "📄"
            logger.info("  %s %s: %s (reason: %s)", symbol, action.title(), file_path, reason)
            updated_files.append(file_path)

        else:
            logger.warning("  ⚠️ Unknown action '%s' for %s", action, file_path)

    return updated_files


def _extract_json_from_text(text: str) -> list | None:
    """Attempt to extract a JSON array from arbitrary text."""
    # Try to find [ ... ] in the text
    start = text.find("[")
    if start == -1:
        return None

    # Find the matching closing bracket
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None
