# GitLab Documentation Automation Pipeline

Automated system that keeps codebase documentation in sync with code changes. Triggered by GitLab webhooks on merge events to the `development` branch.

## How It Works

```
GitLab Webhook (merge to development)
        │
        ▼
  ┌─────────────┐
  │  Clone/Pull  │  ← Clones repo or pulls latest
  │   Target     │
  │   Repo       │
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  Checkout    │  ← Switches to development branch
  │  development │
  │  + feature   │  ← Creates docs/auto-update-<MR> branch
  └──────┬──────┘
         │
         ▼
  ┌─────────────────┐
  │  docs/ exists?   │
  │                  │
  │  NO → Full Gen   │  ← Uses codebase-docs-skill
  │  YES → Update    │  ← Uses docs-update-skill (diff-based)
  └──────┬──────────┘
         │
         ▼
  ┌─────────────┐
  │  Commit +    │
  │  Push + MR   │  ← Creates MR back to development
  └─────────────┘
```

## Project Structure

```
├── app.py                     ← Flask webhook server (orchestrator)
├── config.py                  ← Centralized configuration
├── requirements.txt
├── .gitignore
│
├── skills/                    ← Skill definitions (LLM system prompts)
│   ├── codebase-docs-skill/   ← Full documentation generation
│   ├── docs-update-skill/     ← Incremental doc updates from diffs
│   ├── git-ops-skill/         ← Git operation specifications
│   └── mr-creation-skill/     ← MR creation specifications
│
├── services/                  ← Business logic modules
│   ├── gitlab_client.py       ← GitLab API wrapper
│   ├── git_ops.py             ← Git clone/pull/branch/push
│   ├── llm_client.py          ← LLM interaction layer
│   ├── doc_generator.py       ← Full docs generation
│   ├── doc_updater.py         ← Incremental docs update
│   └── mr_creator.py          ← Push + create MR
│
└── repos/                     ← Cloned target repositories
```

## Setup

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_BASE` | `https://scm.intermesh.net` | GitLab instance URL |
| `GITLAB_TOKEN` | — | GitLab personal access token (needs `api` + `write_repository`) |
| `LLM_API_KEY` | — | API key for the LLM service |
| `LLM_BASE_URL` | `https://imllm.intermesh.net/v1` | LLM API base URL |
| `LLM_MODEL` | `anthropic/claude-sonnet-4-6` | LLM model to use |
| `REPOS_DIR` | `repos` | Directory for cloned repos |
| `WEBHOOK_PORT` | `5000` | Port for the webhook server |

### 3. Run the Server

```bash
python app.py
```

### 4. Configure GitLab Webhook

In your GitLab project settings → Webhooks:
- **URL:** `http://<your-server>:5000/`
- **Trigger:** Push events, Merge request events
- **SSL verification:** As needed

## Skills

| Skill | Purpose |
|-------|---------|
| `codebase-docs-skill` | Generates full documentation structure for a repo from scratch |
| `docs-update-skill` | Incrementally updates only affected doc sections based on MR diffs |
| `git-ops-skill` | Defines git workflows (clone, branch, push) |
| `mr-creation-skill` | Defines MR creation format and rules |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/` | Webhook receiver for GitLab events |
| `GET` | `/health` | Health check |
