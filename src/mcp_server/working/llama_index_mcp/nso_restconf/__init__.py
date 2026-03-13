"""
NSO RESTCONF client layer for MCP servers.

Provides NSORestconfClient, Devices, and Query for RESTCONF-only
integration with Cisco NSO. No NSO Python API (maapi/maagic) required.
"""

from nso_restconf.client import NSORestconfClient
from nso_restconf.devices import Devices
from nso_restconf.query import Query

__all__ = ["NSORestconfClient", "Devices", "Query"]
