#!/bin/bash
# Push this folder to a NEW GitHub repo (does not touch your existing NSO MCP repo).
# Usage: ./push_to_new_github.sh https://github.com/YOUR_USERNAME/YOUR_NEW_REPO.git

set -e
NEW_REPO_URL="${1:?Usage: $0 <new-repo-url>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d .git ]; then
  git init
  git add .
  git commit -m "Initial: NSO RESTCONF MCP server (routing policy, RPL, Juniper/Cisco)"
fi

if git remote get-url origin 2>/dev/null; then
  echo "Remote 'origin' already set. To use a new repo, run: git remote set-url origin $NEW_REPO_URL"
else
  git remote add origin "$NEW_REPO_URL"
fi

git branch -M main
echo "Pushing to $NEW_REPO_URL ..."
git push -u origin main
echo "Done. New repo updated; your existing NSO server MCP repo was not touched."
