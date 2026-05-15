# How to Use & Run This Repo

Step-by-step guide to set up, configure, and run the GitLab Documentation Automation Pipeline.

---

## Prerequisites

Before you begin, make sure you have:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.10+ | `python3 --version` |
| Git | 2.x+ | `git --version` |
| pip | latest | `pip --version` |

You also need:
- A **GitLab Personal Access Token** with `api` + `write_repository` scopes
- Access to an **LLM API** (OpenAI-compatible endpoint)

---

## Step 1 — Clone This Repo

```bash
git clone <this-repo-url>
cd gitlab-merge-doc-generator
```

---

## Step 2 — Create Virtual Environment & Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate    # Linux/Mac
# OR
venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

This installs:
- `flask` — Webhook server
- `requests` — HTTP client for GitLab API
- `openai` — LLM client (OpenAI-compatible)
- `gitpython` — Git operations from Python

---

## Step 3 — Configure Environment Variables

You can either **edit `config.py` directly** or **set environment variables** (recommended for production).

### Option A — Environment Variables (Recommended)

```bash
export GITLAB_BASE="https://scm.intermesh.net"
export GITLAB_TOKEN="your-gitlab-token-here"
export LLM_API_KEY="your-llm-api-key-here"
export LLM_BASE_URL="https://imllm.intermesh.net/v1"
export LLM_MODEL="anthropic/claude-sonnet-4-6"
export REPOS_DIR="repos"
export WEBHOOK_PORT="5000"
```

### Option B — Create a `.env` file

Create a `.env` file in the project root (it's already in `.gitignore`):

```env
GITLAB_BASE=https://scm.intermesh.net
GITLAB_TOKEN=your-gitlab-token-here
LLM_API_KEY=your-llm-api-key-here
LLM_BASE_URL=https://imllm.intermesh.net/v1
LLM_MODEL=anthropic/claude-sonnet-4-6
REPOS_DIR=repos
WEBHOOK_PORT=5000
```

Then load it before running:
```bash
export $(cat .env | xargs)
```

### Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_BASE` | ✅ | `https://scm.intermesh.net` | Your GitLab instance URL |
| `GITLAB_TOKEN` | ✅ | — | Personal access token (needs `api` + `write_repository` scopes) |
| `LLM_API_KEY` | ✅ | — | API key for the LLM service |
| `LLM_BASE_URL` | ✅ | `https://imllm.intermesh.net/v1` | LLM API endpoint (OpenAI-compatible) |
| `LLM_MODEL` | ❌ | `anthropic/claude-sonnet-4-6` | Which model to use |
| `REPOS_DIR` | ❌ | `repos` | Where target repos are cloned to |
| `WEBHOOK_PORT` | ❌ | `5000` | Port for the webhook server |

---

## Step 4 — Run the Server

```bash
# Make sure your venv is activated
source venv/bin/activate

# Start the server
python app.py
```

You should see:
```
[2026-05-16 00:40:30] INFO ============================================================
[2026-05-16 00:40:30] INFO GitLab Documentation Automation Pipeline
[2026-05-16 00:40:30] INFO   GitLab:     https://scm.intermesh.net
[2026-05-16 00:40:30] INFO   LLM Model:  anthropic/claude-sonnet-4-6
[2026-05-16 00:40:30] INFO   Port:       5000
[2026-05-16 00:40:30] INFO ============================================================
 * Running on http://0.0.0.0:5000
```

### Verify it's running

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{"status": "healthy", "timestamp": "2026-05-16T00:40:30.123456"}
```

---

## Step 5 — Expose to the Internet (for GitLab webhooks)

GitLab needs to reach your server. Choose one:

### Option A — ngrok (for development/testing)

```bash
ngrok http 5000
```

Copy the `https://xxxx.ngrok.io` URL — you'll use this in GitLab.

### Option B — Deploy to a server (for production)

Deploy the app on a server accessible by your GitLab instance. Use a process manager:

```bash
# Using gunicorn (production WSGI server)
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

---

## Step 6 — Set Up GitLab Webhook

1. Go to your GitLab project → **Settings** → **Webhooks**
2. Fill in:
   - **URL:** `http://<your-server>:5000/` (or your ngrok URL)
   - **Secret token:** *(leave blank or set one)*
   - **Trigger:**
     - ✅ Push events
     - ✅ Merge request events
   - **SSL verification:** Enable if using HTTPS
3. Click **Add webhook**
4. Click **Test** → **Push events** to verify connectivity

---

## Step 7 — Test It

### Automatic (via GitLab merge)

1. Create a feature branch in your target repo
2. Make code changes
3. Create a Merge Request targeting `development`
4. Merge the MR
5. The webhook fires → the pipeline runs → a new MR with doc updates is created

### Manual (via curl)

Send a simulated merge request event:

```bash
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "object_kind": "merge_request",
    "project": {
      "id": 123,
      "path_with_namespace": "indiamart/soa/pdp_go"
    },
    "object_attributes": {
      "iid": 250,
      "action": "merge",
      "state": "merged"
    }
  }'
```

---

## What Happens When It Runs

```
1. Webhook received (merge to development)
2. Fetches MR diff from GitLab API
3. Clones target repo to repos/ (or pulls if already cloned)
4. Checks out development branch
5. Creates feature branch: docs/auto-update-<MR_IID>-<timestamp>
6. Checks if docs/ folder exists:
   ├── NO  → Generates full documentation using codebase-docs-skill
   └── YES → Updates only affected sections using docs-update-skill
7. Commits documentation changes
8. Pushes the feature branch
9. Creates a new MR targeting development
10. Returns the MR URL in the webhook response
```

---

## Troubleshooting

### "Clone/pull failed"
- Verify `GITLAB_TOKEN` has `write_repository` scope
- Check `GITLAB_BASE` URL is correct
- Ensure the server has network access to GitLab

### "LLM API error"
- Verify `LLM_API_KEY` is valid
- Check `LLM_BASE_URL` is reachable from the server
- Try a different `LLM_MODEL` if the current one is unavailable

### "Failed to create MR"
- Token needs `api` scope
- Check if a branch with the same name already exists (the system handles this with 409 conflict)

### "No documentation changes needed"
- The diff might not affect any documented components
- Check logs for the file-to-doc mapping decisions

### Check Logs

All operations are logged. Look for emoji indicators:
- 📥 Cloning repo
- 📂 Repo exists, pulling
- 🌿 Creating feature branch
- 📚 Full doc generation
- 🔄 Incremental update
- 📝 File changes found
- 🚀 Pushing branch
- ✅ MR created
- ❌ Error occurred

---

## Project Structure Reference

```
gitlab-merge-doc-generator/
│
├── app.py                          ← Webhook server + pipeline orchestrator
├── config.py                       ← All configuration in one place
├── requirements.txt                ← Python dependencies
├── .gitignore                      ← Git ignore rules
├── README.md                       ← Project overview
├── USAGE.md                        ← This file
│
├── skills/                         ← LLM skill definitions
│   ├── codebase-docs-skill/        ← Full documentation generation
│   │   └── SKILL.md
│   ├── docs-update-skill/          ← Incremental doc updates
│   │   └── SKILL.md
│   ├── git-ops-skill/              ← Git operation specs
│   │   └── SKILL.md
│   └── mr-creation-skill/          ← MR creation specs
│       └── SKILL.md
│
├── services/                       ← Business logic modules
│   ├── __init__.py
│   ├── gitlab_client.py            ← GitLab API calls
│   ├── git_ops.py                  ← Git clone/pull/branch/push
│   ├── llm_client.py               ← LLM API client
│   ├── doc_generator.py            ← Full docs generation
│   ├── doc_updater.py              ← Incremental docs update
│   └── mr_creator.py               ← Commit + push + create MR
│
└── repos/                          ← Target repos are cloned here
    └── .gitkeep
```
