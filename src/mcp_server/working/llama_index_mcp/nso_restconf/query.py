"""
RESTCONF Query helper for NSO.

Provides GET on arbitrary RESTCONF data paths.
"""

from typing import Any

from nso_restconf.client import NSORestconfClient


class Query:
    """
    Helper to GET RESTCONF data paths.

    Args:
        client: NSORestconfClient instance
    """

    def __init__(self, client: NSORestconfClient):
        self._client = client

    def get(self, path: str) -> Any:
        """
        GET a RESTCONF path (e.g. /restconf/data/tailf-ncs:devices/device=xr1/live-status/...).

        Args:
            path: Full path including /restconf/data/...

        Returns:
            Parsed JSON or error dict
        """
        path = path.strip("/")
        if path.startswith("restconf/"):
            path = path[9:]  # restconf/data/...
        return self._client.get(path)
