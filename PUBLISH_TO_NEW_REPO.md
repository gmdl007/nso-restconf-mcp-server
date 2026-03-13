# Publish This Code to a **New** GitHub Repo (Do Not Overwrite Existing NSO MCP Repo)

Use these steps to push **this** folder to a **different** GitHub repository. Your existing NSO server MCP repo is not modified.

## 1. Create a new repository on GitHub

- Go to [GitHub](https://github.com/new).
- Create a **new** repo (e.g. `nso-restconf-mcp-server` or `nso-mcp-server-restconf`).
- Do **not** initialize with README (this folder already has one).
- Copy the new repo URL (e.g. `https://github.com/YOUR_USERNAME/nso-restconf-mcp-server.git`).

## 2. Push this folder to the new repo

From **this** directory (`nso-mcp-server-publish`):

```bash
# Ensure you're in the publish folder (inside MCP_Server repo)
cd /path/to/MCP_Server/nso-mcp-server-publish

# Initialize git (only if not already a git repo)
git init

# Add everything (respects .gitignore; __pycache__ and .env are ignored)
git add .
git commit -m "Initial: NSO RESTCONF MCP server (routing policy, RPL, Juniper/Cisco)"

# Add the NEW repo as origin (use your new repo URL)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_NEW_REPO_NAME.git

# Push to main (creates main branch on the new repo)
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_NEW_REPO_NAME` with your new GitHub repo.

## 3. Confirm

- Your **existing** NSO server MCP repo is untouched (this folder has its own `git init` and points to the **new** remote).
- The new repo contains only the RESTCONF MCP server code from this folder.

## Updating the new repo later

After changing code in the **main** project (`MCP_Server`), run from the main project:

```bash
cd /path/to/MCP_Server
./prepare_publish.sh
```

Then from the publish folder:

```bash
cd nso-mcp-server-publish
git add .
git commit -m "Update: describe your changes"
git push origin main
```

The publish folder’s `origin` is the **new** repo; the main `MCP_Server` directory is not pushed to that repo.
