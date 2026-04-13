# NSO RESTCONF MCP Server

A **RESTCONF-only** MCP (Model Context Protocol) server that exposes Cisco NSO automation via RESTCONF. No NSO Python API (maapi/maagic) or `NCS_DIR` required. Use with Cursor, Claude, or any MCP client.

## Features

- **Device operations:** list devices, sync to/from device, check sync status, get config section
- **Interfaces:** configure router interface (Cisco IOS XR and Juniper Junos; NED auto-detected)
- **Routing policy (RPL / policy-statement):**
  - **get_routing_policies**(router_name) — show RPL route-policy (Cisco) or policy-options (Juniper)
  - **configure_routing_policy**(router_name, policy_name, policy_body) — create/update policy (device-agnostic)
  - **apply_routing_policy_to_bgp**(router_name, policy_name, direction, bgp_group) — apply to BGP export/import (Juniper)
- **OSPF / iBGP services:** setup_ospf_base_service, setup_ospf_neighbor_service, setup_ibgp_service (NSO service layer)
- **Rollback, execute device command, commit** (as exposed by the server)

## Prerequisites

- Cisco NSO with RESTCONF enabled (default port 8080)
- Python 3.10+
- `pip install -r requirements.txt` (fastmcp, requests, python-dotenv)

## Setup

1. Clone this repository.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set `NSO_ADDRESS`, `NSO_PORT`, `NSO_USERNAME`, `NSO_PASSWORD` (defaults: localhost, 8080, admin, admin).
4. Run:
   ```bash
   python src/mcp_server/working/llama_index_mcp/fastmcp_nso_server_restconf.py
   ```
   Or use the startup script:
   ```bash
   ./src/mcp_server/working/llama_index_mcp/start_fastmcp_nso_server_restconf.sh
   ```

## Cursor MCP

Add to `~/.cursor/mcp.json` (or your MCP config). Use the path to this repo and the start script so the server runs with the correct Python and dependencies.

## Routing policy (Cisco RPL / Juniper policy-statement)

- **Cisco IOS XR:** RPL (Routing Policy Language); config is `route-policy` (name + CLI text).
- **Juniper:** `policy-options policy-statement` with terms; NSO uses `junos:configuration` and PATCH body wrapped in `config`.

Device type is auto-detected; the same tools work on both.

## Unix CLI Interface (nso-cli)

In addition to the MCP server, this project includes a **Unix CLI tool** (`nso-cli`) that exposes the same 30+ tools as composable shell commands. This follows the emerging trend of CLI-first AI agent tooling for better token efficiency and Unix composability.

### Why CLI?

| | MCP | CLI |
|---|---|---|
| Schema overhead | ~15,000-30,000 tokens | 0 tokens |
| Per-call overhead | ~50-100 tokens | ~20-50 tokens |
| 10-call session | ~16,000+ tokens | ~300-500 tokens |
| Piping/chaining | Not supported | Native Unix pipes |
| Agent familiarity | Learns schema at runtime | Already trained on CLI patterns |

### Quick Start

```bash
# Set NSO directory
export NCS_DIR=/path/to/your/ncs/installation

# Run commands directly
python nso_cli.py devices list
python nso_cli.py sync status --device xr9kv-1
python nso_cli.py interfaces show --device xr9kv-1

# Or use the wrapper script
./nso-cli devices list
./nso-cli exec cmd --device xr9kv-1 --command "show version"
```

### JSON Output for Piping

```bash
# List devices as JSON and pipe to jq
nso-cli devices list --format json | jq '.[].name'

# Check all out-of-sync devices and sync them
nso-cli sync status --format json | \
  jq -r '.[] | select(.status=="out-of-sync") | .device' | \
  xargs -I{} nso-cli sync from --device {}

# Run a command on all devices
nso-cli devices list -f json | \
  jq -r '.[].name' | \
  xargs -I{} nso-cli exec cmd --device {} --command "show version"
```

### Available Command Groups

```
nso-cli devices      Device inventory and info
nso-cli sync         Device synchronization
nso-cli interfaces   Interface configuration
nso-cli config       Configuration management
nso-cli commit       Commit and rollback operations
nso-cli rollback     Rollback management
nso-cli exec         Execute commands on devices
nso-cli services     Service discovery and management
nso-cli ospf         OSPF service management (requires custom package)
nso-cli ibgp         iBGP service management (requires custom package)
nso-cli connect      Device connection management
nso-cli monitor      Device health and monitoring
nso-cli routing      Routing table and neighbors
nso-cli backup       Configuration backup and restore
nso-cli transactions Transaction and lock management
nso-cli packages     NSO package management
nso-cli groups       Device group management
nso-cli health       NSO health check
```

Use `nso-cli <group> --help` for subcommand details.

### MCP + CLI: Hybrid Architecture

Both interfaces call the **same underlying Python functions**:

```
Your NSO Tools (shared Python functions)
    ├── MCP Interface (fastmcp_nso_server.py)  ← for Cursor/IDE AI agents
    └── CLI Interface (nso_cli.py)             ← for terminal, pipes, scripts
```

Use MCP for rich AI agent sessions. Use CLI for quick lookups, pipelines, and automation scripts.

## License

See [LICENSE](LICENSE).
