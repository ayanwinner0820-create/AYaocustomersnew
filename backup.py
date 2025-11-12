# backup.py
import base64
import requests
from datetime import datetime
from db_ops import DB_FILE, log_action
import os

def load_secrets(st_secrets):
    token = None
    repo = None
    user = None
    if st_secrets:
        token = st_secrets.get("GITHUB_TOKEN")
        repo = st_secrets.get("GITHUB_REPO")  # format: username/repo
        user = st_secrets.get("GITHUB_USERNAME")
    # also fallback to env vars
    token = token or os.environ.get("GITHUB_TOKEN")
    repo = repo or os.environ.get("GITHUB_REPO")
    user = user or os.environ.get("GITHUB_USERNAME")
    return token, repo, user

def upload_file(token, repo, path_in_repo, local_path, message="backup"):
    url = f"https://api.github.com/repos/{repo}/contents/{path_in_repo}"
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")
    payload = {
        "message": message,
        "content": content,
        "branch": "main"
    }
    headers = {"Authorization": f"token {token}"}
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code, r.text

def backup_db_to_github(st_secrets=None, actor="system"):
    token, repo, user = load_secrets(st_secrets)
    if not token or not repo:
        return False, "Missing GITHUB_TOKEN or GITHUB_REPO in secrets"
    # local DB path
    local = str(DB_FILE)
    if not os.path.exists(local):
        return False, "DB file not exists"
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path_in_repo = f"backups/crm_data_{ts}.sqlite"
    code, resp = upload_file(token, repo, path_in_repo, local, f"Auto backup {ts}")
    if code in (200,201):
        log_action(actor, "backup", "db", path_in_repo, "")
        return True, resp
    else:
        return False, resp
