"""
Main entry point for kermi2mqtt.

Handles:
- Configuration loading
- Logging setup
- Signal handling (SIGTERM, SIGINT)
- Main async event loop
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from kermi2mqtt.bridge import ModbusMQTTBridge
from kermi2mqtt.config import load_config
from kermi2mqtt.modbus_client import ModbusClient
from kermi2mqtt.mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = asyncio.Event()


def setup_logging(level: str, log_file: str | None = None) -> None:
    """
    Configure logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        logger.info(f"Logging to file: {log_file}")

    logger.info(f"Log level set to {level.upper()}")


def handle_signal(sig: signal.Signals) -> None:
    """
    Handle shutdown signals.

    Args:
        sig: Signal received
    """
    logger.info(f"Received signal {sig.name}, initiating shutdown...")
    shutdown_event.set()


async def run_bridge(config_path: str) -> int:
    """
    Run the Modbus-to-MQTT bridge.

    Args:
        config_path: Path to configuration file

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load configuration
        logger.info(f"Loading configuration from {config_path}")
        config = load_config(config_path)
        logger.info("Configuration loaded successfully")

        # Create clients
        modbus_client = ModbusClient(
            config=config.modbus,
            initial_reconnect_delay=config.advanced.modbus_reconnect_delay,
            max_reconnect_delay=config.advanced.modbus_max_reconnect_delay,
        )

        mqtt_client = MQTTClient(
            mqtt_config=config.mqtt,
            advanced_config=config.advanced,
            ha_discovery_prefix=config.integration.ha_discovery_prefix,
        )

        # Connect to both systems
        logger.info("Connecting to Modbus and MQTT...")

        async with modbus_client, mqtt_client:
            logger.info("All connections established")

            # Create bridge
            bridge = ModbusMQTTBridge(
                config=config,
                modbus_client=modbus_client,
                mqtt_client=mqtt_client,
            )

            # Run bridge in a task
            bridge_task = asyncio.create_task(bridge.run())

            logger.info("kermi2mqtt is running. Press Ctrl+C to stop.")

            # Wait for shutdown signal
            await shutdown_event.wait()

            # Stop bridge gracefully
            logger.info("Shutting down gracefully...")
            bridge.stop()

            # Wait for bridge to finish
            try:
                await asyncio.wait_for(bridge_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Bridge shutdown timed out")
                bridge_task.cancel()

        logger.info("Shutdown complete")
        return 0

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        return 1

    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        return 1

    except ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return 1

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Kermi heat pump to MQTT bridge with Home Assistant discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        default="/config/config.yaml",
        help="Path to configuration file (default: /config/config.yaml)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level from config",
    )

    args = parser.parse_args()

    # Load config early to get logging settings
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    # Setup logging
    log_level = args.log_level or config.logging.level
    setup_logging(log_level, config.logging.file)

    logger.info("=" * 60)
    logger.info("kermi2mqtt - Kermi heat pump to MQTT bridge")
    logger.info("=" * 60)

    # Setup signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    # Run bridge
    try:
        exit_code = loop.run_until_complete(run_bridge(args.config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        exit_code = 0
    finally:
        loop.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
