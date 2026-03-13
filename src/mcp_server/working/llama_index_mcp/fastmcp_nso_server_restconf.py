#!/usr/bin/env python3
"""
FastMCP NSO Server - RESTCONF-only.

MCP server exposing Cisco NSO automation via RESTCONF only.
No NSO Python API (maapi/maagic). Uses nso_restconf client layer.

Configure via env: NSO_SCHEME, NSO_ADDRESS, NSO_PORT, NSO_USERNAME, NSO_PASSWORD.
"""

import json
import logging
import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

from nso_restconf import NSORestconfClient, Devices, Query
from nso_restconf.commit import apply_rollback, list_rollback_files

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RESTCONF client from env (no NCS_DIR / maapi)
_client = NSORestconfClient(
    scheme=os.environ.get("NSO_SCHEME", "http"),
    address=os.environ.get("NSO_ADDRESS", "localhost"),
    port=int(os.environ.get("NSO_PORT", "8080")),
    timeout=int(os.environ.get("NSO_TIMEOUT", "30")),
    username=os.environ.get("NSO_USERNAME", "admin"),
    password=os.environ.get("NSO_PASSWORD", "admin"),
)
_devices = Devices(_client)
_query = Query(_client)

mcp = FastMCP("NSO RESTCONF Tools Server")


def _err(msg: str) -> str:
    return json.dumps({"status": "error", "error_message": msg})


def _audit_log(tool_name: str, params: Optional[dict] = None, result_status: str = "ok") -> None:
    """Log tool invocation for audit (no secrets)."""
    safe = {k: v for k, v in (params or {}).items() if k.lower() not in ("password", "secret", "token")}
    logger.info("tool=%s params=%s result=%s", tool_name, safe, result_status)


def _ok(msg: str, extra: Optional[dict] = None) -> str:
    d = {"status": "ok", "message": msg}
    if extra:
        d.update(extra)
    return json.dumps(d)


# ---------------------------------------------------------------------------
# Device & Sync (RESTCONF)
# ---------------------------------------------------------------------------
def show_all_devices() -> str:
    """List all devices managed by NSO (RESTCONF)."""
    try:
        _audit_log("show_all_devices")
        out = _devices.list_devices()
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "list_devices failed"))
        devices = []
        if isinstance(out, dict):
            # Path tailf-ncs:devices/device returns {"tailf-ncs:device": [ {...}, ... ]}
            dev_list = out.get("tailf-ncs:device")
            if isinstance(dev_list, list):
                devices = [x.get("name", x) if isinstance(x, dict) else str(x) for x in dev_list]
            elif isinstance(dev_list, dict):
                devices = list(dev_list.keys())
            else:
                # Fallback: tailf-ncs:devices -> device (list or dict)
                d = out.get("tailf-ncs:devices", {})
                if isinstance(d, dict) and "device" in d:
                    dev_list = d["device"]
                    if isinstance(dev_list, list):
                        devices = [x.get("name", x) if isinstance(x, dict) else str(x) for x in dev_list]
                    elif isinstance(dev_list, dict):
                        devices = list(dev_list.keys())
        return f"Available devices: {', '.join(devices)}"
    except Exception as e:
        logger.exception("show_all_devices: %s", e)
        return _err(str(e))


def check_device_sync_status(router_name: Optional[str] = None) -> str:
    """Check NSO device sync status (RESTCONF check-sync)."""
    try:
        if router_name:
            out = _devices.check_device_sync(router_name)
            if isinstance(out, dict) and out.get("status") == "error":
                return _err(out.get("error_message", "check_sync failed"))
            return json.dumps(out) if isinstance(out, dict) else str(out)
        # All devices: list then check each (or use a bulk path if available)
        devs = _devices.list_devices()
        if isinstance(devs, dict) and devs.get("status") == "error":
            return _err(devs.get("error_message", "list failed"))
        return json.dumps(devs) if isinstance(devs, dict) else str(devs)
    except Exception as e:
        logger.exception("check_device_sync_status: %s", e)
        return _err(str(e))


def sync_from_device(router_name: str) -> str:
    """Pull device configuration into NSO CDB (RESTCONF sync-from)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    try:
        _audit_log("sync_from_device", {"router_name": router_name})
        out = _devices.sync_from_device(router_name)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "sync-from failed"))
        return _ok(f"sync-from completed for {router_name}", {"result": out})
    except Exception as e:
        logger.exception("sync_from_device: %s", e)
        return _err(str(e))


def sync_to_device(router_name: str) -> str:
    """Push NSO configuration to device (RESTCONF sync-to)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    try:
        _audit_log("sync_to_device", {"router_name": router_name})
        out = _devices.sync_to_device(router_name)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "sync-to failed"))
        return _ok(f"sync-to completed for {router_name}", {"result": out})
    except Exception as e:
        logger.exception("sync_to_device: %s", e)
        return _err(str(e))


def get_router_config_section(router_name: str, section: str) -> str:
    """Get a config section for a device (RESTCONF GET device config)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    try:
        path = f"tailf-ncs:devices/device={router_name}/config/{section}"
        out = _client.get(path)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("get_router_config_section: %s", e)
        return _err(str(e))


def execute_device_command(router_name: str, command: str) -> str:
    """Execute show/exec command on device (RESTCONF live-status exec)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (command or "").strip():
        return _err("command required")
    try:
        out = _devices.live_status_exec(router_name, command)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "exec failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("execute_device_command: %s", e)
        return _err(str(e))


def echo_text(text: str) -> str:
    """Echo back the provided text (debug/health)."""
    return f"Echo: {text}"


def list_rollback_points(limit: int = 50) -> str:
    """List rollback points (RESTCONF tailf-rollback:rollback-files)."""
    try:
        out = list_rollback_files(_client)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "list rollback failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("list_rollback_points: %s", e)
        return _err(str(e))


def rollback_router_configuration(
    rollback_id: int = 0, description: Optional[str] = None
) -> str:
    """Apply rollback by ID (RESTCONF apply-rollback-file). Destructive; use with care."""
    try:
        _audit_log("rollback_router_configuration", {"rollback_id": rollback_id})
        out = apply_rollback(_client, rollback_id)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "rollback failed"))
        return _ok(f"Rollback {rollback_id} applied", {"result": out})
    except Exception as e:
        logger.exception("rollback_router_configuration: %s", e)
        return _err(str(e))


# ---------------------------------------------------------------------------
# Stubs: RESTCONF equivalent not yet implemented or NSO-specific
# Return structured message so agents know to use Python API server for these
# ---------------------------------------------------------------------------
def _stub(name: str, hint: str = "RESTCONF equivalent not implemented in this build.") -> str:
    return _err(f"{name}: {hint}")


def get_ospf_service_config(router_name: Optional[str] = None) -> str:
    """Get OSPF service config (RESTCONF GET ospf:ospf/ospf:base)."""
    try:
        path = "ospf:ospf/ospf:base"
        if router_name:
            path += f"={router_name}"
        out = _client.get(path)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("get_ospf_service_config: %s", e)
        return _err(str(e))


def list_available_services() -> str:
    """List available service types (RESTCONF GET tailf-ncs:services)."""
    try:
        out = _client.get("tailf-ncs:services?depth=1")
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("list_available_services: %s", e)
        return _err(str(e))


def list_device_groups() -> str:
    """List device groups (RESTCONF)."""
    try:
        out = _devices.get_device_groups()
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("list_device_groups: %s", e)
        return _err(str(e))


def setup_ospf_neighbor_service(
    router_name: str,
    router_id: str,
    neighbor_device: str,
    local_interface: str,
    local_ip: str,
    remote_ip: str,
    area: str = "0",
    remote_interface: Optional[str] = None,
) -> str:
    """Configure OSPF neighbor for a router (RESTCONF). Ensures base exists, then PATCH/POST neighbor."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (neighbor_device or "").strip():
        return _err("neighbor_device required")
    if not (local_interface or "").strip():
        return _err("local_interface required")
    if not (local_ip or "").strip():
        return _err("local_ip required")
    if not (remote_ip or "").strip():
        return _err("remote_ip required")
    try:
        _audit_log("setup_ospf_neighbor_service", {"router_name": router_name, "neighbor_device": neighbor_device})
        if not (router_id or "").strip():
            router_id = local_ip
        # Ensure base exists (RESTCONF list key format: base=router_name)
        base_path = f"ospf:ospf/ospf:base={router_name}"
        try:
            get_out = _client.get(base_path)
        except requests.exceptions.HTTPError as e:
            if getattr(e, "response", None) and e.response.status_code == 404:
                setup_ospf_base_service(router_name, router_id, area)
            else:
                raise
            get_out = {}
        if isinstance(get_out, dict) and get_out.get("status") == "error":
            setup_ospf_base_service(router_name, router_id, area)
        path = f"ospf:ospf/ospf:base={router_name}/ospf:neighbor={neighbor_device}"
        local_if_norm = local_interface.replace("GigabitEthernet/", "GigabitEthernet").replace("/", "/").strip()
        if local_if_norm.startswith("GigabitEthernet"):
            local_if_norm = local_if_norm[len("GigabitEthernet"):].strip("/") or "0/0/0/0"
        body = {
            "local-interface": local_if_norm,
            "local-ip": local_ip,
            "remote-ip": remote_ip,
        }
        if remote_interface:
            rf = remote_interface.replace("GigabitEthernet/", "GigabitEthernet").strip()
            if rf.startswith("GigabitEthernet"):
                rf = rf[len("GigabitEthernet"):].strip("/") or "0/0/0/0"
            body["remote-interface"] = rf
        out = _client.patch(path, body)
        if isinstance(out, dict) and out.get("status") == "error":
            out = _client.post(path, body=body)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "OSPF neighbor setup failed"))
        return _ok(f"OSPF neighbor {router_name} -> {neighbor_device}: local {local_ip}, remote {remote_ip}", {"result": out})
    except Exception as e:
        logger.exception("setup_ospf_neighbor_service: %s", e)
        return _err(str(e))


def remove_ospf_neighbor_service(router_name: str, neighbor_device: str, confirm: bool = False) -> str:
    return _stub("remove_ospf_neighbor_service")


def delete_ospf_link_service(link_name: str, confirm: bool = False) -> str:
    return _stub("delete_ospf_link_service")


def delete_all_ospf_links_service(confirm: bool = False) -> str:
    return _stub("delete_all_ospf_links_service")


def normalize_ospf_service_interfaces() -> str:
    return _stub("normalize_ospf_service_interfaces")


def get_ibgp_service_config(service_name: Optional[str] = None) -> str:
    try:
        path = "ibgp:ibgp" if not service_name else f"ibgp:ibgp={service_name}"
        out = _client.get(path)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        return _err(str(e))


def setup_ibgp_service(
    service_name: str,
    as_number: int,
    router1: str,
    router1_lo0_ip: str,
    router1_router_id: str,
    router2: str,
    router2_lo0_ip: str,
    router2_router_id: str,
) -> str:
    """Create or update iBGP service between two routers (RESTCONF POST/PATCH to services/ibgp:ibgp)."""
    if not (service_name or "").strip():
        return _err("service_name required")
    if not (router1 or "").strip() or not (router2 or "").strip():
        return _err("router1 and router2 required")
    try:
        _audit_log("setup_ibgp_service", {"service_name": service_name, "router1": router1, "router2": router2})
        path = f"ibgp:ibgp={service_name}"
        body = {
            "as-number": as_number,
            "router1": router1,
            "router1-lo0-ip": router1_lo0_ip,
            "router1-router-id": router1_router_id,
            "router2": router2,
            "router2-lo0-ip": router2_lo0_ip,
            "router2-router-id": router2_router_id,
        }
        out = _client.patch(path, body)
        if isinstance(out, dict) and out.get("status") == "error":
            out = _client.post(path, body=body)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "iBGP setup failed"))
        return _ok(
            f"iBGP {service_name}: {router1}({router1_lo0_ip}) <-> {router2}({router2_lo0_ip}) AS{as_number}",
            {"result": out},
        )
    except Exception as e:
        logger.exception("setup_ibgp_service: %s", e)
        return _err(str(e))


def delete_ibgp_service(service_name: str, confirm: bool = False) -> str:
    return _stub("delete_ibgp_service")


def setup_ospf_base_service(router_name: str, router_id: str, area: str = "0") -> str:
    """Create or update OSPF base service for a router (RESTCONF POST/PATCH to ospf:ospf/ospf:base)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (router_id or "").strip():
        return _err("router_id required")
    try:
        _audit_log("setup_ospf_base_service", {"router_name": router_name, "router_id": router_id})
        path = f"ospf:ospf/ospf:base={router_name}"
        body = {"router-id": router_id, "area": area}
        out = _client.patch(path, body)
        if isinstance(out, dict) and out.get("status") == "error":
            path_create = "ospf:ospf/ospf:base"
            body_create = {"device": router_name, "router-id": router_id, "area": area}
            out = _client.post(path_create, body=body_create)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "OSPF base setup failed"))
        return _ok(f"OSPF base for {router_name}: router-id={router_id}, area={area}", {"result": out})
    except Exception as e:
        logger.exception("setup_ospf_base_service: %s", e)
        return _err(str(e))


def delete_ospf_service(router_name: str, confirm: bool = False) -> str:
    if not confirm:
        return _err("confirm=True required for delete_ospf_service")
    return _stub("delete_ospf_service")


def commit_with_description(description: str) -> str:
    return _ok("Commit is implicit on edit in RESTCONF; use label/comment on PATCH/POST.", {"description": description})


def get_router_interfaces_config(router_name: str) -> str:
    return get_router_config_section(router_name, "tailf-ned:interface")


def explore_live_status(router_name: str) -> str:
    try:
        path = f"tailf-ncs:devices/device={router_name}/live-status?depth=2"
        out = _client.get(path)
        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "GET failed"))
        return json.dumps(out) if isinstance(out, dict) else str(out)
    except Exception as e:
        logger.exception("explore_live_status: %s", e)
        return _err(str(e))


def find_rollback_by_description(search_term: str, limit: int = 20) -> str:
    return _stub("find_rollback_by_description")


def show_sync_differences(router_name: str) -> str:
    return _stub("show_sync_differences")


def compare_device_config(router_name: str) -> str:
    return _stub("compare_device_config")


def _prefix_to_mask(prefix: int) -> str:
    """Convert CIDR prefix (e.g. 31) to dotted decimal mask."""
    if prefix < 0 or prefix > 32:
        raise ValueError(f"Invalid prefix {prefix}")
    n = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    return f"{(n >> 24) & 0xFF}.{(n >> 16) & 0xFF}.{(n >> 8) & 0xFF}.{n & 0xFF}"


def _normalize_interface_id(interface_name: str, for_loopback: bool = False) -> str:
    """Normalize to NED format: GigabitEthernet id '0/0/0/0' or Loopback id '0'."""
    s = (interface_name or "").strip()
    s = s.replace("GigabitEthernet/", "GigabitEthernet").replace("GigabitEthernet", "")
    s = s.strip("/")
    parts = [p for p in s.split("/") if p != ""]
    if for_loopback:
        return parts[0] if parts else "0"
    if len(parts) == 3:
        parts = ["0"] + parts
    return "/".join(parts) if parts else "0/0/0/0"


def configure_router_interface(
    router_name: str,
    interface_name: str,
    ip_address: Optional[str] = None,
    mask_or_prefix: Optional[str] = None,
    description: Optional[str] = None,
    shutdown: Optional[bool] = None,
    delete_ip: bool = False,
) -> str:
    """Configure an interface on a device via RESTCONF (Cisco IOS XR or Juniper Junos)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (interface_name or "").strip():
        return _err("interface_name required")
    if not delete_ip and not ip_address:
        return _err("ip_address required unless delete_ip=True")
    try:
        _audit_log("configure_router_interface", {"router_name": router_name, "interface_name": interface_name})
        ned = _devices.get_device_ned_id(router_name)
        if isinstance(ned, dict) and ned.get("status") == "error":
            return _err(ned.get("error_message", "could not get device NED"))
        ned_id = str(ned)
        # Config tree namespace: Cisco IOS XR uses tailf-ned-cisco-ios-xr, not the CLI NED id
        if "cisco-iosxr" in ned_id.lower() or "ios-xr" in ned_id.lower():
            config_ns = "tailf-ned-cisco-ios-xr"
        elif "juniper" in ned_id.lower() or "junos" in ned_id.lower():
            config_ns = ned_id.split(":")[0] if ":" in ned_id else ned_id
        else:
            config_ns = ned_id.split(":")[0] if ":" in ned_id else ned_id

        # Mask: allow "255.255.255.254" or "31" (/31)
        mask = "255.255.255.255"
        if not delete_ip and mask_or_prefix:
            if mask_or_prefix.isdigit():
                prefix = int(mask_or_prefix)
                if prefix <= 32:
                    mask = _prefix_to_mask(prefix)
                else:
                    mask = mask_or_prefix
            else:
                mask = mask_or_prefix

        is_loopback = "oopback" in interface_name or interface_name.strip().lower().startswith("lo")
        if_id = _normalize_interface_id(interface_name, for_loopback=is_loopback)

        config_path = f"tailf-ncs:devices/device={router_name}/config"

        if "juniper" in ned_id.lower() or "junos" in ned_id.lower():
            # Juniper Junos: configuration/interfaces/interface + unit 0 family inet address
            unit_body: Any = {}
            if not delete_ip and ip_address:
                unit_body["family"] = {"inet": {"address": [{"name": f"{ip_address}/{mask_or_prefix or '32'}"}]}}
            if description:
                unit_body["description"] = description
            if_name = interface_name.strip()
            body = {
                f"{config_ns}:configuration": {
                    "interfaces": {
                        "interface": [
                            {"name": if_name, "unit": [{"name": "0", **unit_body}] if unit_body else []}
                        ]
                    }
                }
            }
            out = _client.patch(config_path, body)
        else:
            # Cisco IOS XR (cisco-iosxr-cli-* or similar)
            if_key = "Loopback" if is_loopback else "GigabitEthernet"
            entry = {"id": if_id}
            if not delete_ip and ip_address:
                # IOS-XR NED: address can be primary or direct ip/mask depending on NED version
                entry["ipv4"] = {"address": {"ip": ip_address, "mask": mask}}
            if description:
                entry["description"] = description
            if shutdown is True:
                entry["shutdown"] = {}
            body = {f"{config_ns}:interface": {if_key: [entry]}}
            out = _client.patch(config_path, body)

        if isinstance(out, dict) and out.get("status") == "error":
            return _err(out.get("error_message", "PATCH failed") + (f" | {out.get('body', '')}" if out.get("body") else ""))
        return _ok(f"Interface {interface_name} on {router_name} configured", {"result": out})
    except ValueError as e:
        return _err(str(e))
    except Exception as e:
        logger.exception("configure_router_interface: %s", e)
        return _err(str(e))


def delete_router_subinterfaces(router_name: Optional[str] = None, confirm: bool = False) -> str:
    return _stub("delete_router_subinterfaces")


def get_routing_policies(router_name: str) -> str:
    """Show RPL route-policy (Cisco IOS XR) or policy-options policy-statement (Juniper) on a device. Device type is auto-detected."""
    if not (router_name or "").strip():
        return _err("router_name required")
    try:
        _audit_log("get_routing_policies", {"router_name": router_name})
        ned = _devices.get_device_ned_id(router_name)
        if isinstance(ned, dict) and ned.get("status") == "error":
            return _err(ned.get("error_message", "could not get device NED"))
        ned_id = str(ned)
        base = f"tailf-ncs:devices/device={router_name}/config"

        if "cisco-iosxr" in ned_id.lower() or "ios-xr" in ned_id.lower():
            config_ns = "tailf-ned-cisco-ios-xr"
            path = f"{base}/{config_ns}:route-policy"
            out = _client.get(path)
            if isinstance(out, dict) and out.get("status") == "error":
                if "404" in out.get("error_message", ""):
                    return _ok(f"No route-policy on {router_name}", {"policies": [], "raw": {}})
                return _err(out.get("error_message", "GET failed"))
            # Response may be { "tailf-ned-cisco-ios-xr:route-policy": [ { "name": "...", "value": "..." }, ... ] }
            rp_list = out.get(f"{config_ns}:route-policy") if isinstance(out, dict) else out
            if not isinstance(rp_list, list):
                rp_list = []
            return _ok(
                f"RPL route-policy on {router_name}: {len(rp_list)} policy(ies)",
                {"policies": rp_list, "raw": out},
            )
        elif "juniper" in ned_id.lower() or "junos" in ned_id.lower():
            # Junos YANG prefix is "junos" in RESTCONF
            path = f"{base}/junos:configuration/policy-options"
            out = _client.get(path)
            if isinstance(out, dict) and out.get("status") == "error":
                if "404" in out.get("error_message", ""):
                    return _ok(f"No policy-options on {router_name}", {"policies": {}, "raw": {}})
                return _err(out.get("error_message", "GET failed"))
            # Response: { "junos:policy-options": { "policy-statement": [ ... ], ... } }
            policies = out.get("junos:policy-options", out) if isinstance(out, dict) else out
            return _ok(
                f"Policy-options (policy-statement / route-map) on {router_name}",
                {"policies": policies, "raw": out},
            )
        else:
            return _err(
                f"routing policy show not supported for NED '{ned_id}'; supported: cisco-ios-xr, juniper-junos-nc"
            )
    except Exception as e:
        logger.exception("get_routing_policies: %s", e)
        return _err(str(e))


def configure_routing_policy(
    router_name: str,
    policy_name: str,
    policy_body: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """Create or update a routing policy on a device. Cisco IOS XR: RPL route-policy. Juniper: policy-statement. Device type is auto-detected."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (policy_name or "").strip():
        return _err("policy_name required")
    try:
        _audit_log("configure_routing_policy", {"router_name": router_name, "policy_name": policy_name})
        ned = _devices.get_device_ned_id(router_name)
        if isinstance(ned, dict) and ned.get("status") == "error":
            return _err(ned.get("error_message", "could not get device NED"))
        ned_id = str(ned)
        config_path = f"tailf-ncs:devices/device={router_name}/config"

        if "cisco-iosxr" in ned_id.lower() or "ios-xr" in ned_id.lower():
            # Cisco IOS XR RPL (Routing Policy Language); NSO expects PATCH body wrapped in "config"
            config_ns = "tailf-ned-cisco-ios-xr"
            value = (policy_body or "  pass\n").strip()
            if not value.endswith("\n"):
                value += "\n"
            body = {"config": {f"{config_ns}:route-policy": [{"name": policy_name, "value": value}]}}
            out = _client.patch(config_path, body)
        elif "juniper" in ned_id.lower() or "junos" in ned_id.lower():
            # Junos YANG prefix is "junos"; NSO expects PATCH body wrapped in "config"
            junos_cfg = {
                "policy-options": {
                    "policy-statement": [
                        {
                            "name": policy_name,
                            "term": [
                                {
                                    "name": "default",
                                    "then": {"accept": [None]},
                                }
                            ],
                        }
                    ]
                }
            }
            body = {"config": {"junos:configuration": junos_cfg}}
            out = _client.patch(config_path, body)
        else:
            return _err(
                f"routing policy not supported for NED '{ned_id}'; supported: cisco-ios-xr, juniper-junos-nc"
            )

        if isinstance(out, dict) and out.get("status") == "error":
            return _err(
                out.get("error_message", "PATCH failed")
                + (f" | {out.get('body', '')}" if out.get("body") else "")
            )
        return _ok(
            f"Routing policy '{policy_name}' configured on {router_name}",
            {"result": out},
        )
    except Exception as e:
        logger.exception("configure_routing_policy: %s", e)
        return _err(str(e))


def apply_routing_policy_to_bgp(
    router_name: str,
    policy_name: str,
    direction: str = "export",
    bgp_group: Optional[str] = None,
) -> str:
    """Apply a routing policy to BGP on a device (e.g. export to all neighbors on Juniper). Supported: Juniper (protocols bgp group export)."""
    if not (router_name or "").strip():
        return _err("router_name required")
    if not (policy_name or "").strip():
        return _err("policy_name required")
    direction = (direction or "export").strip().lower()
    if direction not in ("export", "import"):
        return _err("direction must be 'export' or 'import'")
    try:
        _audit_log(
            "apply_routing_policy_to_bgp",
            {"router_name": router_name, "policy_name": policy_name, "direction": direction},
        )
        ned = _devices.get_device_ned_id(router_name)
        if isinstance(ned, dict) and ned.get("status") == "error":
            return _err(ned.get("error_message", "could not get device NED"))
        ned_id = str(ned)
        config_path = f"tailf-ncs:devices/device={router_name}/config"

        if "juniper" in ned_id.lower() or "junos" in ned_id.lower():
            group_name = (bgp_group or "internal").strip()
            group_entry = {"name": group_name}
            if direction == "export":
                group_entry["export"] = [policy_name]
            else:
                group_entry["import"] = [policy_name]
            body = {"config": {"junos:configuration": {"protocols": {"bgp": {"group": [group_entry]}}}}}
            out = _client.patch(config_path, body)
        elif "cisco-iosxr" in ned_id.lower() or "ios-xr" in ned_id.lower():
            return _err(
                "apply_routing_policy_to_bgp: BGP apply not yet implemented for Cisco IOS XR; use Juniper or apply route-policy manually on BGP neighbor address-family"
            )
        else:
            return _err(
                f"BGP policy apply not supported for NED '{ned_id}'; supported: juniper-junos-nc"
            )

        if isinstance(out, dict) and out.get("status") == "error":
            return _err(
                out.get("error_message", "PATCH failed")
                + (f" | {out.get('body', '')}" if out.get("body") else "")
            )
        return _ok(
            f"Routing policy '{policy_name}' applied to BGP {direction} on {router_name} (group={group_name})",
            {"result": out},
        )
    except Exception as e:
        logger.exception("apply_routing_policy_to_bgp: %s", e)
        return _err(str(e))


def redeploy_nso_package(package_name: str) -> str:
    return _stub("redeploy_nso_package")


def reload_nso_packages(force: bool = False) -> str:
    return _stub("reload_nso_packages")


def _stub_tool(name: str, hint: str = "RESTCONF equivalent not implemented.") -> str:
    return _stub(name, hint)


# Stub functions for all other tools (same names as original for compatibility)
def get_BGP_GRP__BGP_GRP_config(router_name: Optional[str] = None) -> str:
    return _stub_tool("get_BGP_GRP__BGP_GRP_config")


def create_BGP_GRP__BGP_GRP_service(
    service_name: str, router_name: str, as_number: Optional[str] = None
) -> str:
    return _stub_tool("create_BGP_GRP__BGP_GRP_service")


def delete_BGP_GRP__BGP_GRP_service(service_name: str, confirm: bool = False) -> str:
    return _stub_tool("delete_BGP_GRP__BGP_GRP_service")


def get_device_capabilities(router_name: Optional[str] = None) -> str:
    return _stub_tool("get_device_capabilities")


def check_yang_modules_compatibility(router_name: str, verbose: bool = False) -> str:
    return _stub_tool("check_yang_modules_compatibility")


def list_device_modules(router_name: str) -> str:
    return _stub_tool("list_device_modules")


def get_device_ned_info(router_name: str) -> str:
    return _stub_tool("get_device_ned_info")


def get_device_version(router_name: str) -> str:
    return _stub_tool("get_device_version")


def get_service_model_info(service_name: str) -> str:
    return _stub_tool("get_service_model_info")


def list_service_instances(service_name: str) -> str:
    return _stub_tool("list_service_instances")


def list_transactions(limit: int = 50) -> str:
    return _stub_tool("list_transactions")


def check_locks(router_name: Optional[str] = None) -> str:
    return _stub_tool("check_locks")


def clear_stuck_sessions(automatic: bool = True) -> str:
    return _stub_tool("clear_stuck_sessions")


def connect_device(router_name: str) -> str:
    return _stub_tool("connect_device")


def fetch_ssh_host_keys(router_name: str) -> str:
    return _stub_tool("fetch_ssh_host_keys")


def disconnect_device(router_name: str) -> str:
    return _stub_tool("disconnect_device")


def ping_device(router_name: str) -> str:
    return _stub_tool("ping_device")


def list_commit_queue(limit: int = 50) -> str:
    return _stub_tool("list_commit_queue")


def get_commit_status(commit_id: str) -> str:
    return _stub_tool("get_commit_status")


def commit_dry_run(description: Optional[str] = None) -> str:
    return _stub_tool("commit_dry_run")


def commit_async(description: Optional[str] = None) -> str:
    return _stub_tool("commit_async")


def sync_all_devices(direction: str = "to") -> str:
    return _stub_tool("sync_all_devices")


def compare_all_devices() -> str:
    return _stub_tool("compare_all_devices")


def get_all_devices_sync_status() -> str:
    return _stub_tool("get_all_devices_sync_status")


def delete_config_section(router_name: str, section: str, confirm: bool = False) -> str:
    return _stub_tool("delete_config_section")


def list_config_sections(router_name: str) -> str:
    return _stub_tool("list_config_sections")


def execute_device_command_batch(router_names: str, command: str) -> str:
    return _stub_tool("execute_device_command_batch")


def get_bgp_neighbor_status(router_name: str) -> str:
    return _stub_tool("get_bgp_neighbor_status")


def get_ospf_neighbor_status(router_name: str) -> str:
    return _stub_tool("get_ospf_neighbor_status")


def get_cdp_neighbor_info(router_name: str, detail: bool = True) -> str:
    return _stub_tool("get_cdp_neighbor_info")


def get_lldp_neighbor_info(router_name: str, detail: bool = True) -> str:
    return _stub_tool("get_lldp_neighbor_info")


def redeploy_service(service_type: str, service_name: str) -> str:
    return _stub_tool("redeploy_service")


def redeploy_all_services_for_device(router_name: str) -> str:
    return _stub_tool("redeploy_all_services_for_device")


def get_routing_table(router_name: str, protocol: Optional[str] = None, prefix: Optional[str] = None) -> str:
    return _stub_tool("get_routing_table")


def get_route_details(router_name: str, prefix: str) -> str:
    return _stub_tool("get_route_details")


def get_device_cpu_usage(router_name: str) -> str:
    return _stub_tool("get_device_cpu_usage")


def get_device_memory_usage(router_name: str) -> str:
    return _stub_tool("get_device_memory_usage")


def get_device_alarms(router_name: str, severity: Optional[str] = None) -> str:
    return _stub_tool("get_device_alarms")


def get_services_for_device(router_name: str) -> str:
    return _stub_tool("get_services_for_device")


def get_service_status(service_type: str, service_name: str) -> str:
    return _stub_tool("get_service_status")


def count_services_by_type() -> str:
    return _stub_tool("count_services_by_type")


def backup_ncs_config(backup_name: Optional[str] = None) -> str:
    return _stub_tool("backup_ncs_config")


def load_ncs_config(
    backup_file: Optional[str] = None, mode: str = "merge", dry_run: bool = False
) -> str:
    return _stub_tool("load_ncs_config")


def backup_device_config(router_name: str, backup_name: Optional[str] = None) -> str:
    return _stub_tool("backup_device_config")


def load_device_config(
    router_name: str, backup_file: Optional[str] = None, mode: str = "merge", dry_run: bool = False
) -> str:
    return _stub_tool("load_device_config")


def list_device_backups(router_name: str) -> str:
    return _stub_tool("list_device_backups")


def validate_device_config(router_name: str) -> str:
    return _stub_tool("validate_device_config")


def check_config_syntax(router_name: str) -> str:
    return _stub_tool("check_config_syntax")


def shutdown_all_interfaces(router_name: str, confirm: bool = False) -> str:
    return _stub_tool("shutdown_all_interfaces")


def create_device_group(group_name: str, device_names: str) -> str:
    return _stub_tool("create_device_group")


def get_device_performance_metrics(router_name: str, metric_type: str = "cpu") -> str:
    return _stub_tool("get_device_performance_metrics")


def get_configuration_changes(router_name: str, hours: int = 24) -> str:
    return _stub_tool("get_configuration_changes")


def get_snmp_config(router_name: str) -> str:
    return _stub_tool("get_snmp_config")


def get_access_lists(router_name: str) -> str:
    return _stub_tool("get_access_lists")


def list_notifications(router_name: Optional[str] = None, limit: int = 100) -> str:
    return _stub_tool("list_notifications")


def nso_health_check(auto_fix: bool = True) -> str:
    return _stub_tool("nso_health_check", "Use NSO CLI or Python API for health check.")


# Register all tools
def _register_tools() -> None:
    mcp.tool(show_all_devices)
    mcp.tool(check_device_sync_status)
    mcp.tool(sync_from_device)
    mcp.tool(sync_to_device)
    mcp.tool(get_router_config_section)
    mcp.tool(execute_device_command)
    mcp.tool(echo_text)
    mcp.tool(list_rollback_points)
    mcp.tool(rollback_router_configuration)
    mcp.tool(get_ospf_service_config)
    mcp.tool(list_available_services)
    mcp.tool(list_device_groups)
    mcp.tool(setup_ospf_base_service)
    mcp.tool(setup_ospf_neighbor_service)
    mcp.tool(remove_ospf_neighbor_service)
    mcp.tool(delete_ospf_service)
    mcp.tool(delete_ospf_link_service)
    mcp.tool(delete_all_ospf_links_service)
    mcp.tool(normalize_ospf_service_interfaces)
    mcp.tool(get_ibgp_service_config)
    mcp.tool(setup_ibgp_service)
    mcp.tool(delete_ibgp_service)
    mcp.tool(get_BGP_GRP__BGP_GRP_config)
    mcp.tool(create_BGP_GRP__BGP_GRP_service)
    mcp.tool(delete_BGP_GRP__BGP_GRP_service)
    mcp.tool(get_device_capabilities)
    mcp.tool(check_yang_modules_compatibility)
    mcp.tool(list_device_modules)
    mcp.tool(get_device_ned_info)
    mcp.tool(get_device_version)
    mcp.tool(get_service_model_info)
    mcp.tool(list_service_instances)
    mcp.tool(list_transactions)
    mcp.tool(check_locks)
    mcp.tool(clear_stuck_sessions)
    mcp.tool(connect_device)
    mcp.tool(fetch_ssh_host_keys)
    mcp.tool(disconnect_device)
    mcp.tool(ping_device)
    mcp.tool(list_commit_queue)
    mcp.tool(get_commit_status)
    mcp.tool(commit_dry_run)
    mcp.tool(commit_async)
    mcp.tool(sync_all_devices)
    mcp.tool(compare_all_devices)
    mcp.tool(get_all_devices_sync_status)
    mcp.tool(delete_config_section)
    mcp.tool(list_config_sections)
    mcp.tool(execute_device_command_batch)
    mcp.tool(get_bgp_neighbor_status)
    mcp.tool(get_ospf_neighbor_status)
    mcp.tool(get_cdp_neighbor_info)
    mcp.tool(get_lldp_neighbor_info)
    mcp.tool(redeploy_service)
    mcp.tool(redeploy_all_services_for_device)
    mcp.tool(get_routing_table)
    mcp.tool(get_route_details)
    mcp.tool(get_device_cpu_usage)
    mcp.tool(get_device_memory_usage)
    mcp.tool(get_device_alarms)
    mcp.tool(get_services_for_device)
    mcp.tool(get_service_status)
    mcp.tool(count_services_by_type)
    mcp.tool(backup_ncs_config)
    mcp.tool(load_ncs_config)
    mcp.tool(backup_device_config)
    mcp.tool(load_device_config)
    mcp.tool(list_device_backups)
    mcp.tool(validate_device_config)
    mcp.tool(check_config_syntax)
    mcp.tool(shutdown_all_interfaces)
    mcp.tool(create_device_group)
    mcp.tool(get_device_performance_metrics)
    mcp.tool(get_configuration_changes)
    mcp.tool(get_snmp_config)
    mcp.tool(get_access_lists)
    mcp.tool(list_notifications)
    mcp.tool(nso_health_check)
    mcp.tool(commit_with_description)
    mcp.tool(find_rollback_by_description)
    mcp.tool(show_sync_differences)
    mcp.tool(compare_device_config)
    mcp.tool(get_router_interfaces_config)
    mcp.tool(configure_router_interface)
    mcp.tool(get_routing_policies)
    mcp.tool(configure_routing_policy)
    mcp.tool(apply_routing_policy_to_bgp)
    mcp.tool(delete_router_subinterfaces)
    mcp.tool(redeploy_nso_package)
    mcp.tool(reload_nso_packages)
    mcp.tool(explore_live_status)


_register_tools()

if __name__ == "__main__":
    logger.info("Starting FastMCP NSO RESTCONF-only server...")
    mcp.run()
