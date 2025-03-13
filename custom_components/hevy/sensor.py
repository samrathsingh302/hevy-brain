"""Sensor platform for hevy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass

from .entity import HevyEntity, HevyWorkoutEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HevyDataUpdateCoordinator
    from .data import HevyConfigEntry


@dataclass
class HevySensorEntityDescriptionRequired:
    """Required properties for HevySensorEntityDescription."""

    value_fn: callable[[dict[str, Any]], Any]


@dataclass
class HevySensorEntityDescription(
    SensorEntityDescription, HevySensorEntityDescriptionRequired
):
    """Hevy sensor entity description."""


WORKOUT_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="workout_count",
    translation_key="workout_count",
    icon="mdi:weight-lifter",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("workout_count"),
)

TODAY_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="today_count",
    translation_key="today_count",
    icon="mdi:calendar-today",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("today_count", 0),
)

WEEK_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="week_count",
    translation_key="week_count",
    icon="mdi:calendar-week",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("week_count", 0),
)

MONTH_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="month_count",
    translation_key="month_count",
    icon="mdi:calendar-month",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("month_count", 0),
)

YEAR_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="year_count",
    translation_key="year_count",
    icon="mdi:calendar",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("year_count", 0),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: HevyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Add the primary workout count sensors
    entities = [
        HevySensor(
            coordinator=coordinator,
            entity_description=description,
        )
        for description in [
            WORKOUT_COUNT_DESCRIPTION,
            TODAY_COUNT_DESCRIPTION,
            WEEK_COUNT_DESCRIPTION,
            MONTH_COUNT_DESCRIPTION,
            YEAR_COUNT_DESCRIPTION,
        ]
    ]

    # Add entities for each workout's exercises
    if coordinator.data and "workouts" in coordinator.data:
        for workout_id, workout_data in coordinator.data["workouts"].items():
            # Create a workout date sensor
            entities.append(HevyWorkoutDateSensor(coordinator, workout_id))

            # Create sensors for each exercise in the workout
            for exercise_key, exercise_data in workout_data.get(
                "exercises", {}
            ).items():
                entities.append(
                    HevyExerciseSensor(
                        coordinator=coordinator,
                        workout_id=workout_id,
                        exercise_key=exercise_key,
                        exercise_data=exercise_data,
                    )
                )

    async_add_entities(entities)


class HevySensor(HevyEntity, SensorEntity):
    """Hevy Sensor class."""

    entity_description: HevySensorEntityDescription

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        entity_description: HevySensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        # Create a simpler unique_id that doesn't include all these prefixes
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

        # Set the translation_key explicitly - this is what enables translation
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class HevyWorkoutDateSensor(HevyWorkoutEntity, SensorEntity):
    """Sensor showing the workout date."""

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
    ) -> None:
        """Initialize the workout date sensor."""
        super().__init__(coordinator, workout_id)

        # Use translation keys and proper entity naming
        self._attr_translation_key = "workout_date"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{workout_id}_date"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the native value of the sensor."""
        workout_data = self.workout_data
        return workout_data.get("start_time") if workout_data else None


class HevyExerciseSensor(HevyWorkoutEntity, SensorEntity):
    """Sensor showing exercise data."""

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
        exercise_key: str,
        exercise_data: dict[str, Any],
    ) -> None:
        """Initialize the exercise sensor."""
        super().__init__(coordinator, workout_id)
        self._exercise_key = exercise_key
        self._exercise_data = exercise_data

        exercise_title = exercise_data.get("title", "Unknown Exercise")

        # Use a more streamlined unique_id and better naming
        self._attr_unique_id = f"{workout_id}_{exercise_key}"
        self._attr_name = exercise_title  # Use just the exercise title as name

        # Use weight as the primary value if available
        if exercise_data.get("max_weight_kg", 0) > 0:
            self._attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the weight of the exercise."""
        if not self.available:
            return None

        if not self.workout_data:
            return None

        exercise_data = self.workout_data.get("exercises", {}).get(self._exercise_key)
        if not exercise_data:
            return None

        return exercise_data.get("max_weight_kg")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes about the exercise."""
        if not self.available or not self.workout_data:
            return {}

        exercise_data = self.workout_data.get("exercises", {}).get(
            self._exercise_key, {}
        )
        return {
            "sets": exercise_data.get("sets", 0),
            "total_reps": exercise_data.get("total_reps", 0),
        }
