"""
Modbus client wrapper for py-kermi-xcenter with async connection management.

Provides:
- Automatic device discovery (HeatPump, StorageSystem)
- Exponential backoff reconnection
- Connection health monitoring
- Async context manager for proper cleanup
"""

import asyncio
import logging
from typing import Any

from kermi_xcenter import HeatPump, KermiModbusClient, StorageSystem

from kermi2mqtt.config import ModbusConfig

logger = logging.getLogger(__name__)


class ModbusClient:
    """
    Async wrapper around py-kermi-xcenter device connections.

    Based on research findings (research.md):
    - HeatPump at Unit 40
    - StorageSystem at Units 50/51 (auto-detect heating vs DHW)
    - UniversalModule at Unit 30 (optional - not all devices have this)
    """

    def __init__(
        self,
        config: ModbusConfig,
        initial_reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 30.0,
    ):
        """
        Initialize Modbus client.

        Args:
            config: Modbus connection configuration
            initial_reconnect_delay: Initial reconnection delay in seconds
            max_reconnect_delay: Maximum reconnection delay in seconds
        """
        self.config = config
        self.initial_reconnect_delay = initial_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.current_reconnect_delay = initial_reconnect_delay

        # Modbus client instance
        self.client: KermiModbusClient | None = None

        # Device instances (populated on connection)
        self.heat_pump: HeatPump | None = None
        self.storage_heating: StorageSystem | None = None
        self.storage_dhw: StorageSystem | None = None

        self._connected = False
        self._reconnect_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "ModbusClient":
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

    async def connect(self) -> None:
        """
        Connect to Modbus devices and discover available units.

        Discovers:
        - HeatPump (Unit 40)
        - StorageSystem heating (Unit 50) - auto-detected via heating_actual > 0
        - StorageSystem DHW (Unit 51) - auto-detected via hot_water_actual > 0

        Raises:
            ConnectionError: If unable to connect to any devices
        """
        logger.info(
            f"Connecting to Modbus {self.config.mode.upper()} at {self.config.host}:{self.config.port}"
        )

        try:
            # Create Modbus client connection
            self.client = KermiModbusClient(
                host=self.config.host,
                port=self.config.port,
            )

            # Enter the client context
            await self.client.__aenter__()
            logger.debug("Modbus client connection established")

            # Create HeatPump instance (Unit 40)
            self.heat_pump = HeatPump(self.client)
            logger.debug("HeatPump instance created (Unit 40)")

            # Create StorageSystem instances
            # Unit 50 and 51 - will auto-detect which is heating vs DHW
            storage_50 = StorageSystem(self.client, unit_id=50)
            storage_51 = StorageSystem(self.client, unit_id=51)
            logger.debug("StorageSystem instances created (Units 50, 51)")

            # Auto-detect which storage is heating vs DHW
            # Based on research: heating_actual > 0 for heating, hot_water_actual > 0 for DHW
            try:
                data_50 = await storage_50.get_all_readable_values()
                data_51 = await storage_51.get_all_readable_values()

                # Unit 50 detection
                if data_50.get("heating_actual", 0) > 0:
                    self.storage_heating = storage_50
                    logger.info("Unit 50: Detected as heating circuit (heating_actual > 0)")
                elif data_50.get("hot_water_actual", 0) > 0:
                    self.storage_dhw = storage_50
                    logger.info("Unit 50: Detected as DHW (hot_water_actual > 0)")
                else:
                    # Fallback to unit ID convention if both are 0
                    self.storage_heating = storage_50
                    logger.info("Unit 50: Using as heating circuit (fallback - no active values)")

                # Unit 51 detection
                if data_51.get("hot_water_actual", 0) > 0:
                    self.storage_dhw = storage_51
                    logger.info("Unit 51: Detected as DHW (hot_water_actual > 0)")
                elif data_51.get("heating_actual", 0) > 0:
                    self.storage_heating = storage_51
                    logger.info("Unit 51: Detected as heating circuit (heating_actual > 0)")
                # Fallback to unit ID convention if both are 0
                elif not self.storage_dhw:  # Only if not already assigned
                    self.storage_dhw = storage_51
                    logger.info("Unit 51: Using as DHW (fallback - no active values)")

            except Exception as e:
                logger.warning(f"Auto-detection failed, using unit ID convention: {e}")
                # Fallback: Unit 50 = heating, Unit 51 = DHW
                self.storage_heating = storage_50
                self.storage_dhw = storage_51

            # Verify connection by reading from HeatPump
            outdoor_temp = await self.heat_pump.get_outdoor_temperature()
            logger.info(f"Connection verified - outdoor temperature: {outdoor_temp}°C")

            self._connected = True
            self.current_reconnect_delay = self.initial_reconnect_delay
            logger.info("Modbus connection established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to Modbus: {e}")
            self._connected = False
            raise ConnectionError(f"Modbus connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Modbus devices."""
        logger.info("Disconnecting from Modbus")

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Close the Modbus client connection
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Modbus client: {e}")

        # Clear references
        self.client = None
        self.heat_pump = None
        self.storage_heating = None
        self.storage_dhw = None

        self._connected = False
        logger.info("Modbus disconnected")

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

    async def read_device_data(self, device: HeatPump | StorageSystem) -> dict[str, Any]:
        """
        Read all data from a device using get_all_readable_values().

        Args:
            device: HeatPump or StorageSystem instance

        Returns:
            Dictionary of all readable values

        Raises:
            ConnectionError: If read fails
        """
        if not self._connected:
            raise ConnectionError("Not connected to Modbus")

        try:
            data = await device.get_all_readable_values()

            # Check if data is empty or all reads failed
            # kermi-xcenter doesn't raise exceptions on connection loss,
            # it just returns empty dict and logs warnings
            if not data:
                logger.warning("Device returned empty data - connection may be lost")
                self._connected = False
                self.schedule_reconnect()
                raise ConnectionError("Device returned no data - connection lost")

            return data
        except ConnectionError:
            # Re-raise ConnectionError (including our own from above)
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
            Dictionary with keys 'heat_pump', 'storage_heating', 'storage_dhw'
            Each value is the device's get_all_readable_values() result
        """
        result: dict[str, dict[str, Any]] = {}

        if self.heat_pump:
            result["heat_pump"] = await self.read_device_data(self.heat_pump)

        if self.storage_heating:
            result["storage_heating"] = await self.read_device_data(self.storage_heating)

        if self.storage_dhw:
            result["storage_dhw"] = await self.read_device_data(self.storage_dhw)

        return result
