"""
RESTCONF service operations for NSO.

get_service_types, get_services.
"""

from typing import Any

from nso_restconf.client import NSORestconfClient


def get_service_types(client: NSORestconfClient) -> Any:
    """
    Retrieve available service types in NSO.

    Args:
        client: RESTCONF client

    Returns:
        List of service types or error dict
    """
    out = client.get("tailf-ncs:services?depth=1")
    if isinstance(out, dict) and out.get("status") == "error":
        return out
    if isinstance(out, dict) and "tailf-ncs:services" in out:
        svc = out["tailf-ncs:services"]
        if isinstance(svc, dict):
            return list(svc.keys())
    return out or []


def get_services(client: NSORestconfClient, service_type: str) -> Any:
    """
    Retrieve service instances for a given service type.

    Args:
        client: RESTCONF client
        service_type: Service type (e.g. ospf:base, l3vpn:vpn1)

    Returns:
        Service instances or error dict
    """
    path = f"tailf-ncs:services/{service_type}"
    out = client.get(path)
    if isinstance(out, dict) and out.get("status") == "error":
        return out
    return out
