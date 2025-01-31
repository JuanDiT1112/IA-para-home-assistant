async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the AI Automation Suggester component."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_apply_patterns(call: ServiceCall) -> None:
        """Handle the apply_patterns service call."""
        entity_id = call.data.get("entity_id")

        if not entity_id:
            raise ValueError("Missing entity_id")

        coordinator = hass.data[DOMAIN].get(call.data.get("entry_id"))

        if not coordinator:
            _LOGGER.error("Coordinator not found for AI Automation Suggester")
            return

        _LOGGER.info("Applying AI automation patterns for %s", entity_id)
        await coordinator.apply_patterns(entity_id)

    hass.services.async_register(
        DOMAIN, "apply_patterns", handle_apply_patterns
    )

    return True
