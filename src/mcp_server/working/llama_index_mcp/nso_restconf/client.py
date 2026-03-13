"""
RESTCONF HTTP client for Cisco NSO.

Uses HTTP Basic Auth and NSO RESTCONF paths. No NSO Python API dependency.
"""

import logging
from typing import Any, Dict, Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class NSORestconfClient:
    """
    Synchronous RESTCONF client for NSO.

    Args:
        scheme: http or https
        address: NSO host
        port: NSO RESTCONF port (e.g. 8080)
        timeout: Request timeout in seconds
        username: NSO username
        password: NSO password

    Returns:
        None
    """

    def __init__(
        self,
        scheme: str = "http",
        address: str = "localhost",
        port: int = 8080,
        timeout: int = 10,
        username: str = "admin",
        password: str = "admin",
    ):
        self.scheme = scheme.rstrip("/")
        self.address = address
        self.port = port
        self.timeout = timeout
        self.auth = HTTPBasicAuth(username, password)
        self.base_url = f"{self.scheme}://{self.address}:{self.port}/restconf"

    def _headers(self, content_type: Optional[str] = None) -> Dict[str, str]:
        h = {"Accept": "application/yang-data+json"}
        if content_type:
            h["Content-Type"] = content_type
        return h

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        GET a RESTCONF resource.

        Args:
            path: Path under /restconf/data (leading slash optional)
            params: Optional query parameters

        Returns:
            Parsed JSON or dict; on error returns {"status": "error", "error_message": "..."}
        """
        path = path.lstrip("/")
        if not path.startswith("data/"):
            path = f"data/{path}" if path != "data" else "data"
        url = f"{self.base_url}/{path}"
        try:
            r = requests.get(
                url,
                auth=self.auth,
                headers=self._headers(),
                timeout=self.timeout,
                params=params,
            )
            r.raise_for_status()
            if r.status_code == 204 or not r.text:
                return {}
            return r.json()
        except requests.exceptions.RequestException as e:
            logger.exception("RESTCONF GET failed: %s", e)
            return {"status": "error", "error_message": str(e)}
        except ValueError:
            return {"status": "error", "error_message": "Invalid JSON response"}

    def post(
        self,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        POST to a RESTCONF resource or action.

        Args:
            path: Path under /restconf/data
            body: Optional JSON body
            params: Optional query parameters (e.g. dry-run, label)

        Returns:
            Parsed JSON or dict; on error returns {"status": "error", "error_message": "..."}
        """
        path = path.lstrip("/")
        if not path.startswith("data/"):
            path = f"data/{path}"
        url = f"{self.base_url}/{path}"
        try:
            r = requests.post(
                url,
                auth=self.auth,
                headers=self._headers("application/yang-data+json"),
                json=body or {},
                timeout=self.timeout,
                params=params,
            )
            if r.status_code in (200, 201, 204):
                if r.text:
                    try:
                        return r.json()
                    except ValueError:
                        return {"result": r.text}
                return {}
            return {"status": "error", "error_message": f"{r.status_code} {r.reason}", "body": r.text}
        except requests.exceptions.RequestException as e:
            logger.exception("RESTCONF POST failed: %s", e)
            return {"status": "error", "error_message": str(e)}

    def patch(self, path: str, body: Dict[str, Any]) -> Any:
        """PATCH a RESTCONF resource."""
        path = path.lstrip("/")
        if not path.startswith("data/"):
            path = f"data/{path}"
        url = f"{self.base_url}/{path}"
        try:
            r = requests.patch(
                url,
                auth=self.auth,
                headers=self._headers("application/yang-data+json"),
                json=body,
                timeout=self.timeout,
            )
            if r.status_code in (200, 204):
                return {} if not r.text else (r.json() if r.text else {})
            return {"status": "error", "error_message": f"{r.status_code} {r.reason}"}
        except requests.exceptions.RequestException as e:
            logger.exception("RESTCONF PATCH failed: %s", e)
            return {"status": "error", "error_message": str(e)}

    def delete(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """DELETE a RESTCONF resource."""
        path = path.lstrip("/")
        if not path.startswith("data/"):
            path = f"data/{path}"
        url = f"{self.base_url}/{path}"
        try:
            r = requests.delete(url, auth=self.auth, headers=self._headers(), timeout=self.timeout, params=params)
            if r.status_code in (200, 204):
                return {} if not r.text else (r.json() if r.text else {})
            return {"status": "error", "error_message": f"{r.status_code} {r.reason}"}
        except requests.exceptions.RequestException as e:
            logger.exception("RESTCONF DELETE failed: %s", e)
            return {"status": "error", "error_message": str(e)}
