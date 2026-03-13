"""
RESTCONF environment summary for NSO.
"""

from typing import Any

from nso_restconf.client import NSORestconfClient
from nso_restconf.devices import Devices


def get_environment_summary(
    query_helper: Any,
    devices_helper: Devices,
) -> Any:
    """
    NSO environment summary (devices count, packages hint).

    Args:
        query_helper: Query instance (for optional extra paths)
        devices_helper: Devices instance

    Returns:
        Dict with summary or error
    """
    try:
        devs = devices_helper.list_devices()
        if isinstance(devs, dict) and devs.get("status") == "error":
            return devs
        count = 0
        if isinstance(devs, dict):
            d = devs.get("tailf-ncs:devices", {})
            if isinstance(d, dict) and "device" in d:
                count = len(d["device"]) if isinstance(d["device"], list) else len(d["device"].keys())
        return {"devices_count": count, "status": "ok"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}
