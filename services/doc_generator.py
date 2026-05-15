"""
Documentation Generator Service
================================
Generates full codebase documentation from scratch using the
codebase-docs-skill. Used when a repo's docs/ folder doesn't exist yet.
"""

import os
import logging

from config import CODEBASE_DOCS_SKILL
from services.llm_client import call_llm, load_skill
from services.git_ops import get_repo_file_tree, read_file_content

logger = logging.getLogger(__name__)

PRIORITY_PATTERNS = [
    "main.go", "app.py", "index.js", "index.ts", "server.go", "server.ts",
    "cmd/main.go", "cmd/server.go",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitlab-ci.yml", "go.mod", "package.json", "requirements.txt",
    "config.yaml", "config.yml", ".env.example",
    "README.md", "Makefile",
]

SOURCE_DIRS = [
    "internal", "pkg", "src", "lib", "app", "api",
    "cmd", "handlers", "routes", "services", "models",
    "middleware", "repository", "controllers", "utils",
]

MAX_CONTEXT_CHARS = 80000


def generate_full_docs(repo_path: str) -> list[str]:
    """
    Generate complete documentation for a repository from scratch.
    Returns a list of created doc file paths (relative to repo root).
    """
    logger.info("📚 Starting full documentation generation for %s", repo_path)

    system_prompt = load_skill(CODEBASE_DOCS_SKILL)
    repo_context = _build_repo_context(repo_path)

    user_prompt = f"""Analyze the following repository and generate comprehensive documentation.

## Repository File Tree
```
{get_repo_file_tree(repo_path)}
```

## Key Source Files

{repo_context}

---

Generate the complete documentation following the structure defined in your instructions.
For each documentation file, output it in this exact format:

=== FILE: docs/<path>/<filename>.md ===
<file content>
=== END FILE ===

Generate ALL documentation files as specified in the folder structure.
"""

    llm_response = call_llm(system_prompt, user_prompt, max_tokens=16000)
    created_files = _parse_and_write_docs(repo_path, llm_response)

    # Check for missing sections and generate them
    expected_sections = [
        "01_overview", "02_architecture", "03_repository_guide",
        "04_configuration", "05_api_documentation", "06_data_layer",
        "07_business_logic", "08_infrastructure", "09_observability",
        "10_developer_guide", "11_learning_path",
    ]

    created_dirs = set()
    for f in created_files:
        parts = f.split("/")
        if len(parts) >= 2:
            created_dirs.add(parts[1])

    missing = [s for s in expected_sections if s not in created_dirs]

    if missing:
        logger.info("📝 Generating additional sections: %s", ", ".join(missing))
        additional = _generate_missing_sections(repo_path, system_prompt, repo_context, missing)
        created_files.extend(additional)

    logger.info("✅ Full doc generation complete. %d files created.", len(created_files))
    return created_files


def _build_repo_context(repo_path: str) -> str:
    """Read priority files and key source files to build LLM context."""
    context_parts = []
    total_chars = 0

    for pattern in PRIORITY_PATTERNS:
        file_path = os.path.join(repo_path, pattern)
        if os.path.isfile(file_path):
            content = read_file_content(file_path, max_chars=8000)
            entry = f"### `{pattern}`\n```\n{content}\n```\n"
            if total_chars + len(entry) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(entry)
            total_chars += len(entry)

    for src_dir in SOURCE_DIRS:
        dir_path = os.path.join(repo_path, src_dir)
        if not os.path.isdir(dir_path):
            continue
        for root, _, files in os.walk(dir_path):
            for fname in sorted(files):
                if any(skip in fname for skip in ["_test.", ".test.", ".spec.", ".min."]):
                    continue
                if not any(fname.endswith(ext) for ext in [
                    ".go", ".py", ".js", ".ts", ".java", ".rs", ".yaml", ".yml", ".json",
                ]):
                    continue
                file_path = os.path.join(root, fname)
                rel_path = os.path.relpath(file_path, repo_path)
                content = read_file_content(file_path, max_chars=5000)
                entry = f"### `{rel_path}`\n```\n{content}\n```\n"
                if total_chars + len(entry) > MAX_CONTEXT_CHARS:
                    return "\n".join(context_parts)
                context_parts.append(entry)
                total_chars += len(entry)

    return "\n".join(context_parts)


def _parse_and_write_docs(repo_path: str, llm_response: str) -> list[str]:
    """Parse LLM response and write documentation files."""
    created_files = []
    parts = llm_response.split("=== FILE: ")

    for part in parts[1:]:
        if "=== END FILE ===" not in part:
            continue
        header, rest = part.split("\n", 1)
        file_path = header.strip().rstrip(" =")
        content = rest.split("=== END FILE ===")[0].strip()

        if not file_path.startswith("docs/"):
            file_path = f"docs/{file_path}"

        full_path = os.path.join(repo_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")

        created_files.append(file_path)
        logger.info("  📄 Created: %s", file_path)

    return created_files


def _generate_missing_sections(
    repo_path: str, system_prompt: str, repo_context: str, missing_sections: list[str],
) -> list[str]:
    """Generate documentation for sections missed in the first pass."""
    section_desc = {
        "01_overview": "introduction, business context, system capabilities",
        "02_architecture": "architecture, components, request lifecycle, dependencies",
        "03_repository_guide": "folder structure, key files, module overview",
        "04_configuration": "environment variables, config files, feature flags",
        "05_api_documentation": "API overview, endpoint index, endpoint details",
        "06_data_layer": "database overview, schema reference, data access patterns",
        "07_business_logic": "core workflows and business processes",
        "08_infrastructure": "Docker setup, deployment config, CI/CD",
        "09_observability": "logging, error handling, monitoring",
        "10_developer_guide": "local setup, running tests, debugging guide",
        "11_learning_path": "onboarding sequence for new engineers",
    }

    all_created = []
    for section in missing_sections:
        desc = section_desc.get(section, section)
        user_prompt = (
            f"Generate documentation for the **{section}** section covering: {desc}.\n\n"
            f"## Repository Context\n\n{repo_context[:30000]}\n\n---\n\n"
            f"Output each file in this format:\n\n"
            f"=== FILE: docs/{section}/<filename>.md ===\n<content>\n=== END FILE ===\n"
        )
        try:
            response = call_llm(system_prompt, user_prompt, max_tokens=8000)
            created = _parse_and_write_docs(repo_path, response)
            all_created.extend(created)
        except Exception as e:
            logger.error("Failed to generate section %s: %s", section, e)

    return all_created
