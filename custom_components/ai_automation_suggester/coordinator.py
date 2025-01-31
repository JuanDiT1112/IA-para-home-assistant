# custom_components/ai_automation_suggester/coordinator.py

"""Coordinator for AI Automation Suggester."""
import logging
import sqlite3
import pandas as pd
from datetime import datetime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr, entity_registry as er, area_registry as ar

from .const import DOMAIN, CONF_PROVIDER

_LOGGER = logging.getLogger(__name__)

class AIAutomationCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from AI model and analyzing usage patterns."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.last_update = None
        self.data = {
            "suggestions": "No suggestions yet",
            "last_update": None,
            "patterns": None,  # Almacena patrones detectados
            "provider": entry.data.get(CONF_PROVIDER, "unknown")
        }

        self.update_interval = None
        self.session = async_get_clientsession(hass)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=self.update_interval)

    async def _async_update_data(self):
        """Update data, store usage history, and analyze patterns."""
        try:
            _LOGGER.debug("Starting AI Automation Suggester update")
            self.last_update = datetime.now()

            # Guardar datos de los dispositivos en SQLite
            await self.store_device_data()

            # Analizar patrones de uso
            patterns = await self.analyze_usage_patterns()

            # Guardar los patrones en la variable de datos
            self.data["patterns"] = patterns

            return self.data

        except Exception as err:
            _LOGGER.error("Unexpected error in update: %s", err)
            return self.data

    async def store_device_data(self):
        """Guarda los estados de los dispositivos en una base de datos local."""
        try:
            conn = sqlite3.connect("home_usage.db")
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage_data (
                    entity_id TEXT,
                    state TEXT,
                    last_changed REAL,
                    attributes TEXT
                )
            """)

            for entity_id in self.hass.states.async_entity_ids():
                state = self.hass.states.get(entity_id)
                if state:
                    cursor.execute("INSERT INTO usage_data VALUES (?, ?, ?, ?)",
                                   (entity_id, state.state, state.last_changed.timestamp(), str(state.attributes)))

            conn.commit()
            conn.close()
            _LOGGER.debug("Datos de uso almacenados correctamente.")

        except Exception as e:
            _LOGGER.error("Error guardando datos de uso: %s", e)

    async def analyze_usage_patterns(self):
        """Analiza patrones de uso en los dispositivos IoT."""
        try:
            conn = sqlite3.connect("home_usage.db")
            df = pd.read_sql_query("SELECT * FROM usage_data", conn)
            conn.close()

            if df.empty:
                _LOGGER.warning("No hay datos almacenados para analizar.")
                return None

            df["last_changed"] = pd.to_datetime(df["last_changed"], unit="s")
            df["hour"] = df["last_changed"].dt.hour
            df["day"] = df["last_changed"].dt.day_name()

            usage_patterns = df.groupby(["entity_id", "hour", "day"])["state"].count().reset_index()

            patterns_dict = {}
            for _, row in usage_patterns.iterrows():
                entity = row["entity_id"]
                hour = row["hour"]
                day = row["day"]
                count = row["state"]

                patterns_dict.setdefault(entity, {}).setdefault(day, {})[hour] = count

            _LOGGER.debug("Patrones de uso detectados: %s", patterns_dict)
            return patterns_dict

        except Exception as e:
            _LOGGER.error("Error analizando patrones de uso: %s", e)
            return None

    async def apply_patterns(self, entity_id):
        """Aplica los patrones detectados a un dispositivo."""
        try:
            patterns = self.data.get("patterns", {})

            if not patterns or entity_id not in patterns:
                _LOGGER.warning("No patterns found for %s", entity_id)
                return False

            _LOGGER.info("Applying patterns for %s", entity_id)
            entity_patterns = patterns[entity_id]

            for day, hours in entity_patterns.items():
                for hour, count in hours.items():
                    if count > 3:
                        await self.hass.services.async_call(
                            "automation", "trigger",
                            {"entity_id": entity_id}, blocking=True
                        )

            return True

        except Exception as e:
            _LOGGER.error("Error applying patterns to %s: %s", entity_id, e)
            return False
