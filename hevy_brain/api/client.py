"""Hevy API client (ported from the original Home Assistant integration)."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import aiohttp

BASE_URL = "https://api.hevyapp.com/v1"
DEFAULT_PAGE_SIZE = 10
REQUEST_TIMEOUT_S = 10


class HevyApiClientError(Exception):
    """Exception to indicate a general API error."""


class HevyApiClientCommunicationError(HevyApiClientError):
    """Exception to indicate a communication error."""


class HevyApiClientAuthenticationError(HevyApiClientError):
    """Exception to indicate an authentication error."""


class HevyApiClientConflictError(HevyApiClientError):
    """Exception to indicate the server reported a duplicate (HTTP 409)."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid API key"
        raise HevyApiClientAuthenticationError(msg)
    if response.status == 409:
        msg = "Resource already exists for the given key"
        raise HevyApiClientConflictError(msg)
    response.raise_for_status()


class HevyApiClient:
    """Async client for the Hevy public API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        """Initialize Hevy API Client."""
        self._api_key = api_key
        self._session = session
        self._headers = {
            "accept": "application/json",
            "api-key": api_key,
        }

    async def async_get_workout_events(
        self,
        since: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        """Get workout events (updates + deletes) since ISO 8601 timestamp."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/workouts/events",
            params={"since": since, "page": page, "pageSize": page_size},
        )

    async def async_get_workout_count(self) -> dict[str, Any]:
        """Get workout count from the API."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/workouts/count",
        )

    async def async_get_workouts(
        self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> dict[str, Any]:
        """Get workouts from the API."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/workouts",
            params={"page": page, "pageSize": page_size},
        )

    async def async_get_user_info(self) -> dict[str, Any]:
        """Get authenticated user info."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/user/info",
        )

    async def async_get_body_measurements(
        self, page: int = 1, page_size: int = 10
    ) -> dict[str, Any]:
        """Get body measurements (paginated, max 10 per page)."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/body_measurements",
            params={"page": page, "pageSize": page_size},
        )

    async def async_get_exercise_templates(
        self, page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """Get exercise templates (id, title, muscle groups)."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/exercise_templates",
            params={"page": page, "pageSize": page_size},
        )

    async def async_get_routines(
        self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> dict[str, Any]:
        """Get routines (paginated, max 10 per page)."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/routines",
            params={"page": page, "pageSize": page_size},
        )

    async def async_get_routine(self, routine_id: str) -> dict[str, Any]:
        """Get a single routine by id."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/routines/{routine_id}",
        )

    async def async_get_routine_folders(
        self, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> dict[str, Any]:
        """Get routine folders (paginated)."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/routine_folders",
            params={"page": page, "pageSize": page_size},
        )

    async def async_update_routine(
        self, routine_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT (full replacement) a routine — there is no partial update."""
        return await self._api_wrapper(
            method="put",
            url=f"{BASE_URL}/routines/{routine_id}",
            data=body,
        )

    async def async_create_body_measurement(
        self, body: dict[str, Any]
    ) -> dict[str, Any]:
        """POST a new body measurement. Returns 409 if entry exists for date."""
        return await self._api_wrapper(
            method="post",
            url=f"{BASE_URL}/body_measurements",
            data=body,
        )

    async def async_create_workout(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST a new workout."""
        return await self._api_wrapper(
            method="post",
            url=f"{BASE_URL}/workouts",
            data=body,
        )

    async def async_update_body_measurement(
        self, date: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT (overwrite) body measurement for a given YYYY-MM-DD date."""
        return await self._api_wrapper(
            method="put",
            url=f"{BASE_URL}/body_measurements/{date}",
            data=body,
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_S):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise HevyApiClientCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise HevyApiClientCommunicationError(msg) from exception
        except HevyApiClientError:
            raise
        except Exception as exception:
            msg = f"Something really wrong happened! - {exception}"
            raise HevyApiClientError(msg) from exception
