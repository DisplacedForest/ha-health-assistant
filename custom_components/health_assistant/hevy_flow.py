from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_HEVY_SOURCE
from .hevy_source import discover_hevy

KEEP_WORKOUT_SOURCE = "keep_current"
DISABLE_WORKOUT_SOURCE = "disable_capture"


def select_workout_source(hass, options, user_input):
    choice = user_input.get("workout_source", KEEP_WORKOUT_SOURCE)
    if choice == KEEP_WORKOUT_SOURCE:
        return KEEP_WORKOUT_SOURCE, None
    if choice == DISABLE_WORKOUT_SOURCE:
        return None, None
    offer = next(
        (
            item
            for item in discover_hevy(hass)
            if item.choice == choice and item.binding
        ),
        None,
    )
    if offer is None:
        return KEEP_WORKOUT_SOURCE, "source_unavailable"
    if offer.binding != options.get(CONF_HEVY_SOURCE) and not user_input.get(
        "confirm_person"
    ):
        return KEEP_WORKOUT_SOURCE, "confirm_person"
    return offer.binding, None


def workout_source_field(hass, options):
    offers = discover_hevy(hass)
    current = options.get(CONF_HEVY_SOURCE)
    if not offers and not current:
        return None, KEEP_WORKOUT_SOURCE, []
    choices = [
        {"value": KEEP_WORKOUT_SOURCE, "label": "Keep current workout source"},
        {"value": DISABLE_WORKOUT_SOURCE, "label": "No automatic workout capture"},
    ]
    choices.extend(
        {"value": offer.choice, "label": offer.label}
        for offer in offers
        if offer.binding
    )
    default = next(
        (
            offer.choice
            for offer in offers
            if offer.binding and offer.binding == current
        ),
        KEEP_WORKOUT_SOURCE,
    )
    details = [
        f"{offer.label}: {offer.warning or 'Latest completed workout; no history import or export.'}"
        for offer in offers
    ]
    if current and not any(
        offer.config_entry_id == current.get("config_entry_id") for offer in offers
    ):
        details.append(
            "Configured Hevy account is missing. Recorded workouts are kept."
        )
    return (
        SelectSelector(SelectSelectorConfig(options=choices, mode="dropdown")),
        default,
        details,
    )


def selected_workout_source_is_current(hass, binding):
    return any(offer.binding == binding for offer in discover_hevy(hass))
