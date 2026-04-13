#!/usr/bin/env python3
"""
nso-cli: Unix CLI interface for NSO automation tools.

Provides the same 30+ NSO tools as the MCP server, but as composable
Unix CLI commands. Supports piping, --format json|text, and one-liners.

Architecture:
    nso-cli <group> <command> [options]
        -> Same Python functions as fastmcp_nso_server_auto_generated.py
        -> NSO Python API (MAAPI/Maagic)
        -> Cisco NSO/NCS

Examples:
    nso-cli devices list
    nso-cli devices list --format json | jq '.[].name'
    nso-cli sync status --device xr9kv-1
    nso-cli sync from --device xr9kv-1
    nso-cli interfaces show --device xr9kv-1 --format json | jq '.[]'
    nso-cli exec cmd --device xr9kv-1 --command "show version"
    nso-cli devices list --format json | jq -r '.[].name' | xargs -I{} nso-cli sync status --device {}
"""

import os
import sys
import json
import argparse
import logging
import textwrap

# ---------------------------------------------------------------------------
# NSO environment bootstrap (same as MCP server)
# ---------------------------------------------------------------------------
NSO_DIR = os.environ.get('NCS_DIR', os.environ.get('NSO_DIR', '/opt/ncs/current'))
os.environ.setdefault('NCS_DIR', NSO_DIR)
os.environ.setdefault('DYLD_LIBRARY_PATH', f'{NSO_DIR}/lib')
os.environ.setdefault('PYTHONPATH', f'{NSO_DIR}/src/ncs/pyapi')

nso_pyapi_path = f'{NSO_DIR}/src/ncs/pyapi'
if nso_pyapi_path not in sys.path:
    sys.path.insert(0, nso_pyapi_path)

try:
    import ncs
    import ncs.maapi as maapi
    import ncs.maagic as maagic
except ImportError:
    print(f"Error: Cannot import NSO Python API. Set NCS_DIR (current: {NSO_DIR})", file=sys.stderr)
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger('nso-cli')

# ---------------------------------------------------------------------------
# Import tool functions from the MCP server module
# ---------------------------------------------------------------------------
_server_dir = os.path.dirname(os.path.abspath(__file__))
if _server_dir not in sys.path:
    sys.path.insert(0, _server_dir)

# Suppress INFO logs during import
logging.getLogger().setLevel(logging.WARNING)

# The MCP server file imports FastMCP at module level.  When running in CLI
# mode we don't need FastMCP, so we provide a lightweight stub so the import
# succeeds without requiring the fastmcp package.
import types as _types
_fake_fastmcp = _types.ModuleType('fastmcp')

class _StubMCP:
    """Minimal stand-in for FastMCP so the server module can be imported."""
    def __init__(self, *a, **kw): pass
    def tool(self, fn): return fn
    def run(self): pass

_fake_fastmcp.FastMCP = _StubMCP
sys.modules.setdefault('fastmcp', _fake_fastmcp)

import importlib
_mod = importlib.import_module('fastmcp_nso_server_auto_generated')

# Restore logging after import
logging.getLogger().setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Output formatting helpers
# ---------------------------------------------------------------------------

def _to_json(text: str) -> str:
    """Best-effort conversion of tool output text to JSON."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    # If it already looks like JSON, pass through
    if text.strip().startswith('{') or text.strip().startswith('['):
        try:
            obj = json.loads(text)
            return json.dumps(obj, indent=2)
        except json.JSONDecodeError:
            pass

    # "Available devices: a, b, c" → list
    if lines and lines[0].startswith('Available devices:'):
        names = [n.strip() for n in lines[0].split(':', 1)[1].split(',')]
        return json.dumps([{"name": n} for n in names if n], indent=2)

    # Key: Value lines → dict
    result = {}
    for line in lines:
        if ':' in line and not line.startswith('#'):
            k, v = line.split(':', 1)
            result[k.strip()] = v.strip()
    if result:
        return json.dumps(result, indent=2)

    # Fallback: array of lines
    return json.dumps(lines, indent=2)


def _output(text: str, fmt: str):
    """Print tool output in the requested format."""
    if fmt == 'json':
        print(_to_json(text))
    else:
        print(text)


def _call(func_name: str, fmt: str = 'text', **kwargs):
    """Call an MCP tool function by name, removing None-valued kwargs."""
    fn = getattr(_mod, func_name, None)
    if fn is None:
        print(f"Error: tool '{func_name}' not found", file=sys.stderr)
        sys.exit(1)
    clean = {k: v for k, v in kwargs.items() if v is not None}
    # Suppress logger output so only clean stdout is produced (pipeable)
    _prev = logging.getLogger().level
    logging.getLogger().setLevel(logging.CRITICAL)
    try:
        result = fn(**clean)
    finally:
        logging.getLogger().setLevel(_prev)
    _output(result, fmt)

# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog='nso-cli',
        description='Unix CLI for Cisco NSO automation (same tools as MCP server)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            examples:
              nso-cli devices list
              nso-cli devices list --format json | jq '.[].name'
              nso-cli sync status --device xr9kv-1
              nso-cli sync from --device xr9kv-1
              nso-cli interfaces show --device xr9kv-1
              nso-cli exec cmd --device xr9kv-1 --command "show version"
              nso-cli config diff --device xr9kv-1
              nso-cli rollback list --limit 10
              nso-cli services list
              nso-cli health check
        '''))
    p.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                   help='Output format (default: text)')
    p.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    sub = p.add_subparsers(dest='group', help='Command group')

    # === devices ===
    g = sub.add_parser('devices', help='Device inventory and info')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('list', help='List all managed devices')

    c = s.add_parser('capabilities', help='Get device capabilities')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('modules', help='List device YANG modules')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('ned-info', help='Get NED information')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('version', help='Get device version')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('yang-compat', help='Check YANG module compatibility')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--verbose-output', action='store_true')

    # === sync ===
    g = sub.add_parser('sync', help='Device synchronization')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('status', help='Check sync status')
    c.add_argument('--device', '-d', default=None, help='Device name (all if omitted)')

    c = s.add_parser('from', help='Sync config from device to NSO')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('to', help='Sync config from NSO to device')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('diff', help='Show sync differences')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('all', help='Sync all devices')
    c.add_argument('--direction', choices=['to', 'from'], default='to')

    c = s.add_parser('compare-all', help='Compare all devices')

    c = s.add_parser('status-all', help='Get sync status for all devices')

    # === interfaces ===
    g = sub.add_parser('interfaces', help='Interface configuration')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('show', help='Show interface config')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('config', help='Configure an interface')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--interface', '-i', required=True, help='e.g. Loopback/100')
    c.add_argument('--ip', default=None, help='IP address in CIDR, e.g. 1.1.1.1/32')
    c.add_argument('--description', default=None)
    c.add_argument('--shutdown', type=lambda x: x.lower() == 'true', default=None)
    c.add_argument('--delete-ip', action='store_true')

    c = s.add_parser('operational', help='Get interface operational status')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--interface', '-i', default=None)

    c = s.add_parser('delete-subinterfaces', help='Delete router subinterfaces')
    c.add_argument('--device', '-d', default=None)
    c.add_argument('--confirm', action='store_true')

    c = s.add_parser('shutdown-all', help='Shutdown all interfaces on device')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--confirm', action='store_true')

    # === config ===
    g = sub.add_parser('config', help='Configuration management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('diff', help='Compare device config against NSO')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('section', help='Get specific config section')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--section', '-s', required=True)

    c = s.add_parser('sections', help='List available config sections')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('delete-section', help='Delete config section')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--section', '-s', required=True)
    c.add_argument('--confirm', action='store_true')

    c = s.add_parser('validate', help='Validate device configuration')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('syntax', help='Check configuration syntax')
    c.add_argument('--device', '-d', required=True)

    # === commit ===
    g = sub.add_parser('commit', help='Commit and rollback operations')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('apply', help='Commit with description')
    c.add_argument('--description', '-m', required=True)

    c = s.add_parser('dry-run', help='Dry-run commit')
    c.add_argument('--description', '-m', default=None)

    c = s.add_parser('async', help='Async commit')
    c.add_argument('--description', '-m', default=None)

    c = s.add_parser('queue', help='List commit queue')
    c.add_argument('--limit', type=int, default=50)

    c = s.add_parser('status', help='Get commit status by ID')
    c.add_argument('--id', required=True)

    # === rollback ===
    g = sub.add_parser('rollback', help='Rollback management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('list', help='List rollback points')
    c.add_argument('--limit', type=int, default=50)

    c = s.add_parser('apply', help='Apply a rollback')
    c.add_argument('--id', type=int, default=0)
    c.add_argument('--description', '-m', default=None)

    c = s.add_parser('search', help='Find rollback by description')
    c.add_argument('--term', '-q', required=True)
    c.add_argument('--limit', type=int, default=20)

    # === exec ===
    g = sub.add_parser('exec', help='Execute commands on devices')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('cmd', help='Execute a command on a device')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--command', '-c', required=True)

    c = s.add_parser('batch', help='Execute command on multiple devices')
    c.add_argument('--devices', required=True, help='Comma-separated device names')
    c.add_argument('--command', '-c', required=True)

    # === services ===
    g = sub.add_parser('services', help='Service discovery and management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('list', help='List available service models')

    c = s.add_parser('info', help='Get service model details')
    c.add_argument('--name', '-n', required=True)

    c = s.add_parser('instances', help='List instances of a service')
    c.add_argument('--name', '-n', required=True)

    c = s.add_parser('for-device', help='List services for a device')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('status', help='Get service operational status')
    c.add_argument('--type', required=True)
    c.add_argument('--name', '-n', required=True)

    c = s.add_parser('count', help='Count services by type')

    c = s.add_parser('redeploy', help='Redeploy a service')
    c.add_argument('--type', required=True)
    c.add_argument('--name', '-n', required=True)

    c = s.add_parser('redeploy-device', help='Redeploy all services for device')
    c.add_argument('--device', '-d', required=True)

    # === ospf (custom service) ===
    g = sub.add_parser('ospf', help='OSPF service management (requires custom package)')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('show', help='Show OSPF service config')
    c.add_argument('--device', '-d', default=None)

    c = s.add_parser('setup', help='Setup OSPF base service')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--router-id', required=True)
    c.add_argument('--area', default='0')

    c = s.add_parser('delete', help='Delete OSPF service')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--confirm', action='store_true')

    # === ibgp (custom service) ===
    g = sub.add_parser('ibgp', help='iBGP service management (requires custom package)')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('show', help='Show iBGP service config')
    c.add_argument('--name', '-n', default=None)

    c = s.add_parser('delete', help='Delete iBGP service')
    c.add_argument('--name', '-n', required=True)
    c.add_argument('--confirm', action='store_true')

    # === connect ===
    g = sub.add_parser('connect', help='Device connection management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('up', help='Connect device')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('down', help='Disconnect device')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('ssh-keys', help='Fetch SSH host keys')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('ping', help='Ping a device')
    c.add_argument('--device', '-d', required=True)

    # === monitor ===
    g = sub.add_parser('monitor', help='Device health and monitoring')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('cpu', help='Get CPU usage')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('memory', help='Get memory usage')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('alarms', help='Get device alarms')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--severity', default=None)

    c = s.add_parser('performance', help='Get performance metrics')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--metric', default='cpu', choices=['cpu', 'memory', 'all'])

    # === routing ===
    g = sub.add_parser('routing', help='Routing table and neighbors')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('table', help='Get routing table')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--protocol', default=None)
    c.add_argument('--prefix', default=None)

    c = s.add_parser('route', help='Get route details')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--prefix', required=True)

    c = s.add_parser('bgp-neighbors', help='Get BGP neighbor status')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('ospf-neighbors', help='Get OSPF neighbor status')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('cdp', help='Get CDP neighbor info')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('lldp', help='Get LLDP neighbor info')
    c.add_argument('--device', '-d', required=True)

    # === backup ===
    g = sub.add_parser('backup', help='Configuration backup and restore')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('device', help='Backup device config')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--name', '-n', default=None)

    c = s.add_parser('ncs', help='Backup complete NCS config')
    c.add_argument('--name', '-n', default=None)

    c = s.add_parser('list', help='List backups for a device')
    c.add_argument('--device', '-d', required=True)

    c = s.add_parser('load-device', help='Load device config from backup')
    c.add_argument('--device', '-d', required=True)
    c.add_argument('--file', default=None)
    c.add_argument('--mode', choices=['merge', 'replace'], default='merge')
    c.add_argument('--dry-run', action='store_true')

    c = s.add_parser('load-ncs', help='Load complete NCS config from backup')
    c.add_argument('--file', default=None)
    c.add_argument('--mode', choices=['merge', 'replace'], default='merge')
    c.add_argument('--dry-run', action='store_true')

    # === transactions ===
    g = sub.add_parser('transactions', help='Transaction and lock management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('list', help='List recent transactions')
    c.add_argument('--limit', type=int, default=50)

    c = s.add_parser('locks', help='Check active locks')
    c.add_argument('--device', '-d', default=None)

    c = s.add_parser('clear', help='Clear stuck sessions')
    c.add_argument('--auto', action='store_true', default=True)

    # === packages ===
    g = sub.add_parser('packages', help='NSO package management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('redeploy', help='Redeploy a package')
    c.add_argument('--name', '-n', required=True)

    c = s.add_parser('reload', help='Reload all packages')
    c.add_argument('--force', action='store_true')

    # === groups ===
    g = sub.add_parser('groups', help='Device group management')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('list', help='List device groups')

    c = s.add_parser('create', help='Create device group')
    c.add_argument('--name', '-n', required=True)
    c.add_argument('--devices', required=True, help='Comma-separated device names')

    # === health ===
    g = sub.add_parser('health', help='NSO health check')
    s = g.add_subparsers(dest='cmd')

    c = s.add_parser('check', help='Run health check')

    c = s.add_parser('live-status', help='Explore live-status paths')
    c.add_argument('--device', '-d', required=True)

    # === misc ===
    g = sub.add_parser('echo', help='Echo text (health check)')
    g.add_argument('text', nargs='?', default='hello')

    return p


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(args):
    fmt = args.format
    g, c = args.group, getattr(args, 'cmd', None)

    if g is None:
        build_parser().print_help()
        return

    # ---------- devices ----------
    if g == 'devices':
        if c == 'list':          _call('show_all_devices', fmt)
        elif c == 'capabilities':_call('get_device_capabilities', fmt, router_name=args.device)
        elif c == 'modules':     _call('list_device_modules', fmt, router_name=args.device)
        elif c == 'ned-info':    _call('get_device_ned_info', fmt, router_name=args.device)
        elif c == 'version':     _call('get_device_version', fmt, router_name=args.device)
        elif c == 'yang-compat': _call('check_yang_modules_compatibility', fmt, router_name=args.device, verbose=args.verbose_output)
        else: print("Usage: nso-cli devices {list|capabilities|modules|ned-info|version|yang-compat}", file=sys.stderr)

    # ---------- sync ----------
    elif g == 'sync':
        if c == 'status':       _call('check_device_sync_status', fmt, router_name=args.device)
        elif c == 'from':       _call('sync_from_device', fmt, router_name=args.device)
        elif c == 'to':         _call('sync_to_device', fmt, router_name=args.device)
        elif c == 'diff':       _call('show_sync_differences', fmt, router_name=args.device)
        elif c == 'all':        _call('sync_all_devices', fmt, direction=args.direction)
        elif c == 'compare-all':_call('compare_all_devices', fmt)
        elif c == 'status-all': _call('get_all_devices_sync_status', fmt)
        else: print("Usage: nso-cli sync {status|from|to|diff|all|compare-all|status-all}", file=sys.stderr)

    # ---------- interfaces ----------
    elif g == 'interfaces':
        if c == 'show':         _call('get_router_interfaces_config', fmt, router_name=args.device)
        elif c == 'config':     _call('configure_router_interface', fmt, router_name=args.device, interface_name=args.interface, ip_address=args.ip, description=args.description, shutdown=args.shutdown, delete_ip=args.delete_ip)
        elif c == 'operational':_call('get_interface_operational_status', fmt, router_name=args.device, interface_name=args.interface)
        elif c == 'delete-subinterfaces': _call('delete_router_subinterfaces', fmt, router_name=args.device, confirm=args.confirm)
        elif c == 'shutdown-all':_call('shutdown_all_interfaces', fmt, router_name=args.device, confirm=args.confirm)
        else: print("Usage: nso-cli interfaces {show|config|operational|delete-subinterfaces|shutdown-all}", file=sys.stderr)

    # ---------- config ----------
    elif g == 'config':
        if c == 'diff':         _call('compare_device_config', fmt, router_name=args.device)
        elif c == 'section':    _call('get_router_config_section', fmt, router_name=args.device, section=args.section)
        elif c == 'sections':   _call('list_config_sections', fmt, router_name=args.device)
        elif c == 'delete-section': _call('delete_config_section', fmt, router_name=args.device, section=args.section, confirm=args.confirm)
        elif c == 'validate':   _call('validate_device_config', fmt, router_name=args.device)
        elif c == 'syntax':     _call('check_config_syntax', fmt, router_name=args.device)
        else: print("Usage: nso-cli config {diff|section|sections|delete-section|validate|syntax}", file=sys.stderr)

    # ---------- commit ----------
    elif g == 'commit':
        if c == 'apply':        _call('commit_with_description', fmt, description=args.description)
        elif c == 'dry-run':    _call('commit_dry_run', fmt, description=args.description)
        elif c == 'async':      _call('commit_async', fmt, description=args.description)
        elif c == 'queue':      _call('list_commit_queue', fmt, limit=args.limit)
        elif c == 'status':     _call('get_commit_status', fmt, commit_id=args.id)
        else: print("Usage: nso-cli commit {apply|dry-run|async|queue|status}", file=sys.stderr)

    # ---------- rollback ----------
    elif g == 'rollback':
        if c == 'list':         _call('list_rollback_points', fmt, limit=args.limit)
        elif c == 'apply':      _call('rollback_router_configuration', fmt, rollback_id=args.id, description=args.description)
        elif c == 'search':     _call('find_rollback_by_description', fmt, search_term=args.term, limit=args.limit)
        else: print("Usage: nso-cli rollback {list|apply|search}", file=sys.stderr)

    # ---------- exec ----------
    elif g == 'exec':
        if c == 'cmd':          _call('execute_device_command', fmt, router_name=args.device, command=args.command)
        elif c == 'batch':      _call('execute_device_command_batch', fmt, router_names=args.devices, command=args.command)
        else: print("Usage: nso-cli exec {cmd|batch}", file=sys.stderr)

    # ---------- services ----------
    elif g == 'services':
        if c == 'list':         _call('list_available_services', fmt)
        elif c == 'info':       _call('get_service_model_info', fmt, service_name=args.name)
        elif c == 'instances':  _call('list_service_instances', fmt, service_name=args.name)
        elif c == 'for-device': _call('get_services_for_device', fmt, router_name=args.device)
        elif c == 'status':     _call('get_service_status', fmt, service_type=args.type, service_name=args.name)
        elif c == 'count':      _call('count_services_by_type', fmt)
        elif c == 'redeploy':   _call('redeploy_service', fmt, service_type=args.type, service_name=args.name)
        elif c == 'redeploy-device': _call('redeploy_all_services_for_device', fmt, router_name=args.device)
        else: print("Usage: nso-cli services {list|info|instances|for-device|status|count|redeploy|redeploy-device}", file=sys.stderr)

    # ---------- ospf ----------
    elif g == 'ospf':
        if c == 'show':         _call('get_ospf_service_config', fmt, router_name=args.device)
        elif c == 'setup':      _call('setup_ospf_base_service', fmt, router_name=args.device, router_id=args.router_id, area=args.area)
        elif c == 'delete':     _call('delete_ospf_service', fmt, router_name=args.device, confirm=args.confirm)
        else: print("Usage: nso-cli ospf {show|setup|delete}", file=sys.stderr)

    # ---------- ibgp ----------
    elif g == 'ibgp':
        if c == 'show':         _call('get_ibgp_service_config', fmt, service_name=args.name)
        elif c == 'delete':     _call('delete_ibgp_service', fmt, service_name=args.name, confirm=args.confirm)
        else: print("Usage: nso-cli ibgp {show|delete}", file=sys.stderr)

    # ---------- connect ----------
    elif g == 'connect':
        if c == 'up':           _call('connect_device', fmt, router_name=args.device)
        elif c == 'down':       _call('disconnect_device', fmt, router_name=args.device)
        elif c == 'ssh-keys':   _call('fetch_ssh_host_keys', fmt, router_name=args.device)
        elif c == 'ping':       _call('ping_device', fmt, router_name=args.device)
        else: print("Usage: nso-cli connect {up|down|ssh-keys|ping}", file=sys.stderr)

    # ---------- monitor ----------
    elif g == 'monitor':
        if c == 'cpu':          _call('get_device_cpu_usage', fmt, router_name=args.device)
        elif c == 'memory':     _call('get_device_memory_usage', fmt, router_name=args.device)
        elif c == 'alarms':     _call('get_device_alarms', fmt, router_name=args.device, severity=args.severity)
        elif c == 'performance':_call('get_device_performance_metrics', fmt, router_name=args.device, metric_type=args.metric)
        else: print("Usage: nso-cli monitor {cpu|memory|alarms|performance}", file=sys.stderr)

    # ---------- routing ----------
    elif g == 'routing':
        if c == 'table':        _call('get_routing_table', fmt, router_name=args.device, protocol=args.protocol, prefix=args.prefix)
        elif c == 'route':      _call('get_route_details', fmt, router_name=args.device, prefix=args.prefix)
        elif c == 'bgp-neighbors': _call('get_bgp_neighbor_status', fmt, router_name=args.device)
        elif c == 'ospf-neighbors':_call('get_ospf_neighbor_status', fmt, router_name=args.device)
        elif c == 'cdp':        _call('get_cdp_neighbor_info', fmt, router_name=args.device)
        elif c == 'lldp':       _call('get_lldp_neighbor_info', fmt, router_name=args.device)
        else: print("Usage: nso-cli routing {table|route|bgp-neighbors|ospf-neighbors|cdp|lldp}", file=sys.stderr)

    # ---------- backup ----------
    elif g == 'backup':
        if c == 'device':       _call('backup_device_config', fmt, router_name=args.device, backup_name=args.name)
        elif c == 'ncs':        _call('backup_ncs_config', fmt, backup_name=args.name)
        elif c == 'list':       _call('list_device_backups', fmt, router_name=args.device)
        elif c == 'load-device':_call('load_device_config', fmt, router_name=args.device, backup_file=args.file, mode=args.mode, dry_run=args.dry_run)
        elif c == 'load-ncs':   _call('load_ncs_config', fmt, backup_file=args.file, mode=args.mode, dry_run=args.dry_run)
        else: print("Usage: nso-cli backup {device|ncs|list|load-device|load-ncs}", file=sys.stderr)

    # ---------- transactions ----------
    elif g == 'transactions':
        if c == 'list':         _call('list_transactions', fmt, limit=args.limit)
        elif c == 'locks':      _call('check_locks', fmt, router_name=args.device)
        elif c == 'clear':      _call('clear_stuck_sessions', fmt, automatic=args.auto)
        else: print("Usage: nso-cli transactions {list|locks|clear}", file=sys.stderr)

    # ---------- packages ----------
    elif g == 'packages':
        if c == 'redeploy':     _call('redeploy_nso_package', fmt, package_name=args.name)
        elif c == 'reload':     _call('reload_nso_packages', fmt, force=args.force)
        else: print("Usage: nso-cli packages {redeploy|reload}", file=sys.stderr)

    # ---------- groups ----------
    elif g == 'groups':
        if c == 'list':         _call('list_device_groups', fmt)
        elif c == 'create':     _call('create_device_group', fmt, group_name=args.name, device_names=args.devices)
        else: print("Usage: nso-cli groups {list|create}", file=sys.stderr)

    # ---------- health ----------
    elif g == 'health':
        if c == 'check':        _call('nso_health_check', fmt)
        elif c == 'live-status':_call('explore_live_status', fmt, router_name=args.device)
        else: print("Usage: nso-cli health {check|live-status}", file=sys.stderr)

    # ---------- echo ----------
    elif g == 'echo':
        _call('echo_text', fmt, text=args.text)

    else:
        build_parser().print_help()


def main():
    # Pre-process argv: pull out global flags (--format, -f, --verbose, -v)
    # so they work regardless of position (before or after subcommand).
    raw = sys.argv[1:]
    fmt = 'text'
    verbose = False
    cleaned = []
    skip_next = False
    for i, arg in enumerate(raw):
        if skip_next:
            skip_next = False
            continue
        if arg in ('--format', '-f') and i + 1 < len(raw):
            fmt = raw[i + 1]
            skip_next = True
            continue
        if arg.startswith('--format='):
            fmt = arg.split('=', 1)[1]
            continue
        if arg in ('--verbose', '-v'):
            verbose = True
            continue
        cleaned.append(arg)

    # Re-inject global flags at the front so argparse sees them
    rebuilt = []
    rebuilt.extend(['--format', fmt])
    if verbose:
        rebuilt.append('--verbose')
    rebuilt.extend(cleaned)

    parser = build_parser()
    args = parser.parse_args(rebuilt)
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    try:
        dispatch(args)
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == '__main__':
    main()
