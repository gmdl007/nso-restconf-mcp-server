# Setup Instructions (RESTCONF-only server)

## Prerequisites

1. Cisco NSO installed and running with RESTCONF enabled (default port 8080)
2. Python 3.8+
3. Dependencies: `pip install -r requirements.txt` (includes fastmcp, requests, python-dotenv)

## Installation

1. Clone or extract this repository
2. Install: `pip install -r requirements.txt`
3. Set NSO connection (optional; defaults: localhost:8080, admin/admin):
   export NSO_ADDRESS=localhost
   export NSO_PORT=8080
   export NSO_USERNAME=admin
   export NSO_PASSWORD=admin
4. Run: python src/mcp_server/working/llama_index_mcp/fastmcp_nso_server_restconf.py
   Or: ./src/mcp_server/working/llama_index_mcp/start_fastmcp_nso_server_restconf.sh

## Configuration

Copy `.env.example` to `.env` and set NSO_ADDRESS, NSO_PORT, NSO_USERNAME, NSO_PASSWORD.
