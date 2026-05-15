---
name: git-ops
description: >
  Handles all local git operations for the documentation automation pipeline.
  Covers cloning repositories, pulling latest changes, checking out branches,
  creating feature branches, staging files, committing, and pushing.
  Use this skill whenever git repository manipulation is needed.
---

# Git Operations Skill

You are responsible for **managing local git repository state** as part of an automated documentation pipeline.

---

## OPERATIONS

### 1. Clone or Pull

**If the local directory does NOT exist:**
```
git clone https://oauth2:<GITLAB_TOKEN>@<GITLAB_HOST>/<project_path>.git <local_path>
```

**If the local directory ALREADY exists (has `.git/`):**
```
cd <local_path>
git fetch --all --prune
git checkout development
git pull origin development
```

### 2. Checkout Development Branch

After clone/pull, always ensure you are on the `development` branch:
```
git checkout development
git pull origin development
```

If `development` does not exist remotely, fall back to `main` or `master`.

### 3. Create Feature Branch

Create a new branch for the documentation update:
```
git checkout -b docs/auto-update-<mr_iid>-<timestamp>
```

Branch naming convention: `docs/auto-update-<MR_IID>-<YYYYMMDD_HHMMSS>`

### 4. Stage, Commit, and Push

After documentation is generated or updated:
```
git add docs/
git commit -m "docs: auto-update documentation for MR !<mr_iid>

Automated documentation update triggered by merge of MR !<mr_iid>.
Updated sections: <list of changed doc sections>"

git push origin docs/auto-update-<mr_iid>-<timestamp>
```

---

## ERROR HANDLING

| Scenario | Action |
|----------|--------|
| Clone fails (auth) | Log error with HTTP status, abort pipeline |
| Branch doesn't exist | Fall back: `development` → `main` → `master` |
| Push fails (conflict) | Force push with `--force-with-lease` (safe force) |
| Empty commit (no doc changes) | Skip push, log "No documentation changes needed" |

---

## RULES

1. **Never operate on `main` or `development` directly** — always create a feature branch.
2. **Always pull latest before branching** — avoid stale base.
3. **Use token-based HTTPS cloning** — no SSH keys required.
4. **Clean working tree before operations** — run `git stash` if needed, restore after.
5. **Verify remote exists** before push — `git ls-remote` check.
