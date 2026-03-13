"""
RESTCONF package operations for NSO.

list_packages, get_package.
"""

from typing import Any

from nso_restconf.client import NSORestconfClient


def list_packages(client: NSORestconfClient) -> Any:
    """
    List installed NSO packages.

    Args:
        client: RESTCONF client

    Returns:
        Package list or error dict
    """
    out = client.get("tailf-ncs:packages/package?depth=2")
    if isinstance(out, dict) and out.get("status") == "error":
        return out
    return out or {"packages": []}


def get_package(client: NSORestconfClient, name: str) -> Any:
    """
    Get details of a specific NSO package.

    Args:
        client: RESTCONF client
        name: Package name

    Returns:
        Package details or error dict
    """
    path = f"tailf-ncs:packages/package={name}"
    return client.get(path)
