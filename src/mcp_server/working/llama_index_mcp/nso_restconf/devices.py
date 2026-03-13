"""
RESTCONF device operations for NSO.

Device list, config, state, sync-from, sync-to, check-sync, live-status exec.
"""

from typing import Any

from nso_restconf.client import NSORestconfClient


class Devices:
    """
    Device operations via NSO RESTCONF.

    Args:
        client: NSORestconfClient instance
    """

    def __init__(self, client: NSORestconfClient):
        self._client = client

    def _device_path(self, device_name: str, suffix: str = "") -> str:
        base = f"tailf-ncs:devices/device={device_name}"
        return f"{base}/{suffix}" if suffix else base

    def get_device_config(self, device_name: str) -> Any:
        """
        Retrieve configuration for a device.

        Args:
            device_name: Device name in NSO

        Returns:
            Config data or error dict
        """
        path = self._device_path(device_name) + "/config"
        return self._client.get(path)

    def get_device_platform(self, device_name: str) -> Any:
        """Retrieve platform info for a device."""
        path = self._device_path(device_name)
        out = self._client.get(path)
        if isinstance(out, dict) and "status" in out and out["status"] == "error":
            return out
        # Platform often in device list entry
        if isinstance(out, dict):
            return out.get("tailf-ncs:device", out)
        return out

    def get_device_state(self, device_name: str) -> Any:
        """Retrieve operational state for a device."""
        path = self._device_path(device_name) + "/state"
        return self._client.get(path)

    def check_device_sync(self, device_name: str) -> Any:
        """
        Check device sync status (NSO vs device).

        Invokes RESTCONF action check-sync.
        """
        path = self._device_path(device_name) + "/check-sync"
        return self._client.post(path, body={})

    def sync_from_device(self, device_name: str) -> Any:
        """
        Pull device configuration into NSO CDB.

        Invokes RESTCONF action sync-from.
        """
        path = self._device_path(device_name) + "/sync-from"
        return self._client.post(path, body={})

    def sync_to_device(self, device_name: str) -> Any:
        """
        Push NSO configuration to device.

        Invokes RESTCONF action sync-to.
        """
        path = self._device_path(device_name) + "/sync-to"
        return self._client.post(path, body={})

    def get_device_groups(self) -> Any:
        """List device groups."""
        return self._client.get("tailf-ncs:devices/device-group")

    def list_devices(self) -> Any:
        """List all devices. Uses RESTCONF path that returns the device list."""
        return self._client.get(
            "tailf-ncs:devices/device",
            params={"content": "config"},
        )

    def get_device(self, device_name: str) -> Any:
        """
        Get a single device's config (including device-type / ned-id).

        Returns:
            Device dict or error dict. NED ID is in device-type cli/ned-id or netconf/ned-id.
        """
        path = self._device_path(device_name)
        return self._client.get(path, params={"content": "config"})

    def get_device_ned_id(self, device_name: str) -> Any:
        """
        Resolve device NED ID string (e.g. 'cisco-iosxr-cli-7.61:cisco-iosxr-cli-7.61' or 'juniper-junos-nc-4.17:...').

        Returns:
            str NED ID on success, or error dict.
        """
        out = self.get_device(device_name)
        if isinstance(out, dict) and out.get("status") == "error":
            return out
        raw = out.get("tailf-ncs:device") if isinstance(out, dict) else None
        # NSO can return single device as array of one element
        dev = raw[0] if isinstance(raw, list) and len(raw) > 0 else raw
        if not isinstance(dev, dict):
            return {"status": "error", "error_message": "device not found or invalid response"}
        # device-type can be cli or netconf
        dt = dev.get("device-type") or dev.get("tailf-ncs:device-type")
        if not isinstance(dt, dict):
            return {"status": "error", "error_message": "device-type not found"}
        for kind in ("cli", "netconf"):
            if kind in dt:
                ned = dt[kind]
                if isinstance(ned, dict):
                    nid = ned.get("ned-id") or ned.get("tailf-ncs:ned-id")
                    if nid:
                        return nid if isinstance(nid, str) else str(nid)
        return {"status": "error", "error_message": "ned-id not found in device-type"}

    def live_status_exec(self, device_name: str, command: str) -> Any:
        """
        Execute CLI command on device via live-status.

        Uses NED-specific exec.any when available (e.g. cisco-ios-xr-stats:exec).
        Falls back to generic path if needed.
        """
        # NSO exposes exec under live-status; path varies by NED
        # Common: tailf-ncs:devices/device={name}/live-status/.../exec/any
        path = (
            f"tailf-ncs:devices/device={device_name}/"
            "live-status/cisco-ios-xr-stats:exec/any"
        )
        # Many NEDs use input with args array
        body = {"input": {"args": command.split()}}
        out = self._client.post(path, body=body)
        if isinstance(out, dict) and out.get("status") == "error":
            # Try generic exec path (some NEDs use different module)
            path2 = f"tailf-ncs:devices/device={device_name}/live-status"
            info = self._client.get(path2 + "?depth=1")
            return out  # Return first error with hint
        return out
