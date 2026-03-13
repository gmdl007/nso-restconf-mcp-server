#!/bin/bash
# Start FastMCP NSO Server (RESTCONF-only)
# No NSO Python API required. Uses env: NSO_ADDRESS, NSO_PORT, NSO_USERNAME, NSO_PASSWORD.
# Uses project mcp_venv so fastmcp and dependencies are available.

cd "$(dirname "$(dirname "$(dirname "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")")")")"
source mcp_venv/bin/activate
exec python src/mcp_server/working/llama_index_mcp/fastmcp_nso_server_restconf.py 2>/tmp/fastmcp_restconf.log
