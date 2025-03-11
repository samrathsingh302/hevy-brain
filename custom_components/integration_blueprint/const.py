"""Constants for Hevy integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "hevy"
ATTRIBUTION = "Data provided by Hevy"
CONF_API_KEY = "api_key"
BASE_URL = "https://api.hevyapp.com/v1"
