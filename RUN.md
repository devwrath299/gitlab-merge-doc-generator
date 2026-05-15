# Commands to Run This Project

## First Time Setup

```bash
# Step 1: Go to the project folder
cd /home/indiamart/.gemini/antigravity/scratch/gitlab-merge-doc-generator

# Step 2: Create virtual environment
python3 -m venv venv

# Step 3: Activate virtual environment
source venv/bin/activate

# Step 4: Install dependencies
pip install -r requirements.txt
```

## Run the Server

```bash
# Activate venv (if not already active)
source venv/bin/activate

# Start the server
python app.py
```

Server starts at: `http://0.0.0.0:5000`

## Test Commands (run in a separate terminal)

### Health Check

```bash
curl http://localhost:5000/health
```

### Get Your Real GitLab Project ID

```bash
curl -k -H "PRIVATE-TOKEN: BDyzugQPDhtwhHaKsaQZ" \
  "https://scm.intermesh.net/api/v4/projects/indiamart%2Fsoa%2Fpdp_go" \
  | python3 -m json.tool | grep '"id"'
```

### Simulate a Merge Event

Replace `<REAL_PROJECT_ID>` with the actual ID from above:

```bash
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "object_kind": "merge_request",
    "project": {
      "id": <REAL_PROJECT_ID>,
      "path_with_namespace": "indiamart/soa/pdp_go"
    },
    "object_attributes": {
      "iid": 249,
      "action": "merge",
      "state": "merged"
    }
  }'
```

## Expose to Internet (for GitLab Webhook)

```bash
# Using ngrok
ngrok http 5000
```

## Stop the Server

Press `Ctrl+C` in the terminal where the server is running.
