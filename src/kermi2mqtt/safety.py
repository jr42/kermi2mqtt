"""
Safety validation for write operations.

Based on specs/001-modbus-mqtt/safety.md:
- DHW temperature: 40-60°C (prevent Legionella < 40, scalding > 60)
- PV modulation power: >= 0W
- Rate limiting: 60s minimum between commands
- All validation rules documented in safety.md
"""

import time
from typing import Any, Callable


class RangeValidator:
    """Validates values are within a safe range."""

    def __init__(self, min_val: float, max_val: float, parameter_name: str):
        """
        Initialize range validator.

        Args:
            min_val: Minimum safe value
            max_val: Maximum safe value
            parameter_name: Parameter name for error messages
        """
        self.min_val = min_val
        self.max_val = max_val
        self.parameter_name = parameter_name

    def validate(self, value: float) -> tuple[bool, str]:
        """
        Validate value is in safe range.

        Args:
            value: Value to validate

        Returns:
            (is_valid, error_message) tuple
        """
        if not (self.min_val <= value <= self.max_val):
            return (
                False,
                f"{self.parameter_name} value {value} outside safe range "
                f"[{self.min_val}, {self.max_val}]",
            )
        return True, "OK"


class RateLimiter:
    """Prevents rapid repeated commands that could stress equipment."""

    def __init__(self, min_interval_seconds: float = 60.0):
        """
        Initialize rate limiter.

        Args:
            min_interval_seconds: Minimum seconds between writes (default: 60)
        """
        self.min_interval = min_interval_seconds
        self.last_write: dict[str, float] = {}

    def can_write(self, parameter: str) -> tuple[bool, str]:
        """
        Check if write is allowed (rate limit).

        Args:
            parameter: Parameter name to check

        Returns:
            (can_write, message) tuple
        """
        now = time.time()
        last = self.last_write.get(parameter, 0)

        if now - last < self.min_interval:
            remaining = self.min_interval - (now - last)
            return False, f"Rate limit: wait {remaining:.0f}s before changing {parameter}"

        self.last_write[parameter] = now
        return True, "OK"

    def reset(self, parameter: str | None = None) -> None:
        """
        Reset rate limiter.

        Args:
            parameter: Specific parameter to reset, or None for all
        """
        if parameter is None:
            self.last_write.clear()
        elif parameter in self.last_write:
            del self.last_write[parameter]


class SafetyValidator:
    """
    Additional validation layer on top of py-kermi-xcenter's safety.

    From research findings:
    - py-kermi-xcenter only exposes safe methods (library does initial validation)
    - We add additional range checks for extra safety
    - Document: specs/001-modbus-mqtt/safety.md
    """

    def __init__(self, attribute_name: str):
        """
        Initialize safety validator.

        Args:
            attribute_name: Which attribute this validates
        """
        self.attribute_name = attribute_name
        self.validation_rules: list[Callable[[Any], tuple[bool, str]]] = []
        self.block_reason: str | None = None

    def add_rule(self, rule: Callable[[Any], tuple[bool, str]]) -> None:
        """
        Add a validation rule.

        Args:
            rule: Validation function that returns (is_valid, error_message)
        """
        self.validation_rules.append(rule)

    def block(self, reason: str) -> None:
        """
        Permanently block this attribute from writes.

        Args:
            reason: Why this attribute is blocked
        """
        self.block_reason = reason

    def validate(self, value: Any) -> tuple[bool, str]:
        """
        Validate a value before passing to library setter.

        Args:
            value: Value to validate

        Returns:
            (is_valid, error_message) tuple
        """
        if self.block_reason:
            return False, self.block_reason

        for rule in self.validation_rules:
            is_valid, error = rule(value)
            if not is_valid:
                return False, error

        return True, "OK"


# Pre-configured validators for known safe parameters
def create_dhw_validator() -> SafetyValidator:
    """
    Create validator for DHW setpoint.

    Safe range: 40-60°C per safety.md
    - Below 40°C: Risk of Legionella bacteria
    - Above 60°C: Risk of scalding, increased energy use

    Returns:
        Configured SafetyValidator
    """
    validator = SafetyValidator("set_hot_water_setpoint_constant")
    range_check = RangeValidator(40.0, 60.0, "DHW temperature")
    validator.add_rule(range_check.validate)
    return validator


def create_pv_power_validator() -> SafetyValidator:
    """
    Create validator for PV modulation power.

    Safe range: >= 0W per safety.md
    - Cannot be negative (nonsensical)
    - Upper bound enforced by library based on device capabilities

    Returns:
        Configured SafetyValidator
    """
    validator = SafetyValidator("set_pv_modulation_power")
    validator.add_rule(lambda v: (v >= 0, "PV power cannot be negative") if v < 0 else (True, "OK"))
    return validator


# Default rate limiter (60s between commands per safety.md)
default_rate_limiter = RateLimiter(min_interval_seconds=60.0)
