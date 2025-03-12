"""Switch platform for HA hevy."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import HevyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: HevyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    # Not creating any switch entities as the HevyApiClient doesn't have the required methods
    return
