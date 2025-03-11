"""DataUpdateCoordinator for hevy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    HevyApiClientAuthenticationError,
    HevyApiClientError,
)

if TYPE_CHECKING:
    from .data import HevyConfigEntry


class HevyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: HevyConfigEntry

    async def _async_update_data(self) -> dict:
        """Update data via library."""
        try:
            return await self.config_entry.runtime_data.client.async_get_workout_count()
        except HevyApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except HevyApiClientError as exception:
            raise UpdateFailed(exception) from exception
