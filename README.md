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

## License

See [LICENSE](LICENSE).
