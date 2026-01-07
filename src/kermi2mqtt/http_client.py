"""
HTTP client wrapper for py-kermi-xcenter with async connection management.

Provides:
- Automatic device discovery (IFM, HeatPump, StorageSystem)
- Device metadata (serial numbers, model, software version)
- Alarm access
- Exponential backoff reconnection
- Same interface as ModbusClient for easy switching
"""

import asyncio
import logging
from typing import Any

from kermi_xcenter import KermiHttpClient
from kermi_xcenter.http.models import Alarm, DeviceInfo, HttpDevice, SceneOverview

from kermi2mqtt.config import HttpConfig

logger = logging.getLogger(__name__)


class HttpClient:
    """
    Async wrapper around py-kermi-xcenter HTTP client.

    Provides the same interface as ModbusClient for seamless switching.

    Device discovery:
    - IFM (Unit 0) - x-center gateway
    - HeatPump (Unit 40)
    - StorageSystem heating (Unit 50)
    - StorageSystem DHW (Unit 51)
    """

    def __init__(
        self,
        config: HttpConfig,
        initial_reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 30.0,
    ):
        """
        Initialize HTTP client.

        Args:
            config: HTTP connection configuration
            initial_reconnect_delay: Initial reconnection delay in seconds
            max_reconnect_delay: Maximum reconnection delay in seconds
        """
        self.config = config
        self.initial_reconnect_delay = initial_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.current_reconnect_delay = initial_reconnect_delay

        # HTTP client instance
        self.client: KermiHttpClient | None = None

        # Device references (populated on connection)
        # Store HttpDevice objects for metadata access
        self._devices: list[HttpDevice] = []
        self._device_map: dict[int, HttpDevice] = {}  # unit_id -> HttpDevice

        # Compatibility properties (same as ModbusClient)
        self.ifm: HttpDevice | None = None  # Unit 0
        self.heat_pump: HttpDevice | None = None  # Unit 40
        self.storage_heating: HttpDevice | None = None  # Unit 50
        self.storage_dhw: HttpDevice | None = None  # Unit 51

        self._connected = False
        self._reconnect_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "HttpClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    @property
    def devices(self) -> list[HttpDevice]:
        """Get list of discovered devices."""
        return self._devices

    async def connect(self) -> None:
        """
        Connect to HTTP API and discover available devices.

        Discovers:
        - IFM (Unit 0) - always present
        - HeatPump (Unit 40) - if present
        - StorageSystem heating (Unit 50) - auto-detected
        - StorageSystem DHW (Unit 51) - auto-detected

        Raises:
            ConnectionError: If unable to connect
        """
        logger.info(f"Connecting to HTTP API at {self.config.host}:{self.config.port}")

        try:
            # Create HTTP client
            self.client = KermiHttpClient(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                timeout=self.config.timeout,
            )

            # Connect and discover devices
            await self.client.connect()

            # Store discovered devices
            self._devices = self.client.devices
            self._device_map = {d.unit_id: d for d in self._devices}

            # Set convenience references (compatible with ModbusClient)
            self.ifm = self._device_map.get(0)
            self.heat_pump = self._device_map.get(40)
            self.storage_heating = self._device_map.get(50)
            self.storage_dhw = self._device_map.get(51)

            # Log discovered devices
            device_names = [f"{d.display_name} (Unit {d.unit_id})" for d in self._devices]
            logger.info(f"Discovered devices: {', '.join(device_names)}")

            # Verify connection by reading outdoor temperature
            if self.heat_pump:
                values = await self.client.get_all_values(40)
                outdoor_temp = values.get("outdoor_temperature")
                logger.info(f"Connection verified - outdoor temperature: {outdoor_temp}°C")

            self._connected = True
            self.current_reconnect_delay = self.initial_reconnect_delay
            logger.info("HTTP connection established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to HTTP API: {e}")
            self._connected = False
            raise ConnectionError(f"HTTP connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from HTTP API."""
        logger.info("Disconnecting from HTTP API")

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Close the HTTP client
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")

        # Clear references
        self.client = None
        self._devices = []
        self._device_map = {}
        self.ifm = None
        self.heat_pump = None
        self.storage_heating = None
        self.storage_dhw = None

        self._connected = False
        logger.info("HTTP disconnected")

    async def reconnect_with_backoff(self) -> None:
        """
        Reconnect with exponential backoff.

        Delays start at initial_reconnect_delay and double each attempt
        up to max_reconnect_delay.
        """
        while True:
            logger.info(f"Reconnecting in {self.current_reconnect_delay:.1f}s...")
            await asyncio.sleep(self.current_reconnect_delay)

            try:
                await self.connect()
                logger.info("Reconnection successful")
                return
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                # Exponential backoff
                self.current_reconnect_delay = min(
                    self.current_reconnect_delay * 2,
                    self.max_reconnect_delay,
                )

    def schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt in the background."""
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self.reconnect_with_backoff())
            logger.debug("Reconnection task scheduled")

    async def read_device_data(self, unit_id: int) -> dict[str, Any]:
        """
        Read all data from a device using get_all_values().

        Args:
            unit_id: Device unit ID (0, 40, 50, 51)

        Returns:
            Dictionary of all readable values

        Raises:
            ConnectionError: If read fails
        """
        if not self._connected or not self.client:
            raise ConnectionError("Not connected to HTTP API")

        try:
            data = await self.client.get_all_values(unit_id)

            # Check if data is empty
            if not data:
                logger.warning(f"Device {unit_id} returned empty data")
                self._connected = False
                self.schedule_reconnect()
                raise ConnectionError("Device returned no data - connection lost")

            return data

        except ConnectionError:
            raise
        except Exception as e:
            logger.error(f"Failed to read device data: {e}")
            self._connected = False
            self.schedule_reconnect()
            raise ConnectionError(f"Device read failed: {e}") from e

    async def read_all_devices(self) -> dict[str, dict[str, Any]]:
        """
        Read data from all connected devices.

        Returns:
            Dictionary with keys 'ifm', 'heat_pump', 'storage_heating', 'storage_dhw'
            Each value is the device's get_all_values() result
        """
        result: dict[str, dict[str, Any]] = {}

        if self.ifm:
            result["ifm"] = await self.read_device_data(0)

        if self.heat_pump:
            result["heat_pump"] = await self.read_device_data(40)

        if self.storage_heating:
            result["storage_heating"] = await self.read_device_data(50)

        if self.storage_dhw:
            result["storage_dhw"] = await self.read_device_data(51)

        return result

    # =========================================================================
    # HTTP-specific methods (not available in ModbusClient)
    # =========================================================================

    async def get_device_info(self, unit_id: int) -> DeviceInfo:
        """
        Get device metadata (serial number, model, software version).

        Args:
            unit_id: Device unit ID

        Returns:
            DeviceInfo with serial_number, model, software_version
        """
        if not self.client:
            raise ConnectionError("Not connected")
        return await self.client.get_device_info(unit_id)

    async def get_current_alarms(self) -> list[Alarm]:
        """
        Get current active alarms.

        Returns:
            List of active Alarm objects
        """
        if not self.client:
            raise ConnectionError("Not connected")
        return await self.client.get_current_alarms()

    async def get_alarm_history(self) -> list[Alarm]:
        """
        Get alarm history.

        Returns:
            List of historical Alarm objects
        """
        if not self.client:
            raise ConnectionError("Not connected")
        return await self.client.get_alarm_history()

    async def clear_alarms(self) -> None:
        """Acknowledge/clear current active alarms."""
        if not self.client:
            raise ConnectionError("Not connected")
        await self.client.clear_current_alarms()

    async def set_value(self, name: str, value: Any, unit_id: int) -> None:
        """
        Set a datapoint value.

        Args:
            name: Python attribute name (e.g., "hot_water_boost_active")
            value: Value to write
            unit_id: Device unit ID
        """
        if not self.client:
            raise ConnectionError("Not connected")
        await self.client.set_value(name, value, unit_id)

    def get_device_by_unit(self, unit_id: int) -> HttpDevice | None:
        """
        Get HttpDevice by unit ID.

        Args:
            unit_id: Device unit ID

        Returns:
            HttpDevice or None if not found
        """
        return self._device_map.get(unit_id)

    # =========================================================================
    # Scene API (py-kermi-xcenter 0.3.1+)
    # =========================================================================

    async def get_scenes(self) -> list[SceneOverview]:
        """
        Get all scenes configured on the x-center.

        Returns:
            List of SceneOverview objects with scene metadata
        """
        if not self.client:
            raise ConnectionError("Not connected")
        return await self.client.get_scenes()

    async def execute_scene(self, scene_id: str) -> None:
        """
        Execute a scene's actions immediately.

        This triggers all actions defined in the scene regardless of
        whether conditions are met. Use with caution.

        Args:
            scene_id: UUID of the scene to execute
        """
        if not self.client:
            raise ConnectionError("Not connected")
        await self.client.execute_scene(scene_id)

    async def set_scene_enabled(self, scene_id: str, enabled: bool) -> None:
        """
        Enable or disable a scene.

        Args:
            scene_id: UUID of the scene
            enabled: True to enable, False to disable
        """
        if not self.client:
            raise ConnectionError("Not connected")
        # py-kermi-xcenter 0.3.1+ should have this method
        # If not available, call the HTTP API directly
        if hasattr(self.client, "set_scene_enabled"):
            await self.client.set_scene_enabled(scene_id, enabled)
        else:
            # Direct HTTP API call as fallback
            await self.client._session.request(
                "Scene/SetSceneEnabled",
                {"SceneId": scene_id, "Enabled": enabled},
            )
