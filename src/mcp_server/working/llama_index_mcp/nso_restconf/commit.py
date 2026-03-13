"""
RESTCONF commit and rollback helpers for NSO.
"""

from typing import Any, Optional

from nso_restconf.client import NSORestconfClient


def apply_rollback(client: NSORestconfClient, fixed_number: int) -> Any:
    """Apply rollback file by ID. POST apply-rollback-file."""
    path = "tailf-rollback:rollback-files/apply-rollback-file"
    body = {"input": {"fixed-number": fixed_number}}
    return client.post(path, body=body)


def list_rollback_files(client: NSORestconfClient, limit: int = 50) -> Any:
    """List rollback files."""
    path = "tailf-rollback:rollback-files"
    return client.get(path)
