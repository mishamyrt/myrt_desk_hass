"""MyrtDesk light integration"""
from typing import Any, List
from asyncio import gather
from aiohttp import ClientError
from homeassistant import config_entries, core
from homeassistant.core import callback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_EFFECT,
    COLOR_MODE_HS,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
    SUPPORT_EFFECT
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_util
from myrt_desk_api.backlight import MyrtDeskBacklight, Effect

from .coordinator import MyrtDeskCoordinator
from .const import DOMAIN, DEVICE_INFO

effects: List[str] = []
for effect in Effect:
    effects.append(effect.name.lower().capitalize())

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Set up desk light."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([MyrtDeskLight(
        data["coordinator"],
        data["desk"].backlight
    )])

class MyrtDeskLight(CoordinatorEntity, LightEntity):
    """MyrtDesk backlight entity"""
    _backlight: MyrtDeskBacklight = None
    _is_on: bool = False
    _rgb: tuple[int, int, int] = (255, 255, 255)
    _temperature = 0
    _brightness: int = 255
    _attr_supported_features = SUPPORT_EFFECT
    _attr_effect_list = effects
    _attr_min_mireds = 166
    _attr_effect = effects[0]
    _attr_max_mireds = 400
    _attr_name = "MyrtDesk Backlight"
    _attr_color_mode = COLOR_MODE_HS
    _attr_available = False
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: MyrtDeskCoordinator, backlight: MyrtDeskBacklight):
        super().__init__(coordinator)
        self._backlight = backlight
        self._mireds_range_max = self._attr_max_mireds - self._attr_min_mireds

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the light."""
        return "myrt_desk_light"

    @property
    def icon(self):
        return "mdi:led-strip-variant"

    @property
    def brightness(self) -> int:
        """Return the brightness of the device."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def supported_color_modes(self) -> set:
        """Flag supported color modes."""
        return {COLOR_MODE_HS, COLOR_MODE_COLOR_TEMP}

    @property
    def hs_color(self) -> tuple[int, int, int]:
        """Return the color of the device."""
        return color_util.color_RGB_to_hs(*self._rgb)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        state = self.coordinator.data["light"]
        self._brightness = state["brightness"]
        self._is_on = state["enabled"]
        self._rgb = state["color"]
        self._attr_effect = state["effect"].name.lower().capitalize()
        self._temperature = self._byte_to_mireds(state["warmness"])
        if state["mode"].value == 0:
            self._attr_color_mode = COLOR_MODE_HS
        else:
            self._attr_color_mode = COLOR_MODE_COLOR_TEMP
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Update the current value."""
        try:
            futures = []
            if not self._is_on:
                futures.append(self._backlight.set_power(True))
                self._is_on = True

            if ATTR_EFFECT in kwargs:
                self._attr_effect = kwargs[ATTR_EFFECT]
                effect_index = effects.index(kwargs[ATTR_EFFECT])
                if len(futures) > 0:
                    await gather(*futures)
                await self._backlight.set_effect(Effect(effect_index))
                return
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
                futures.append(self._backlight.set_brightness(self._brightness))
            if ATTR_COLOR_TEMP in kwargs:
                self._temperature = kwargs[ATTR_COLOR_TEMP]
                self._attr_color_mode = COLOR_MODE_COLOR_TEMP
                futures.append(self._backlight.set_white(self._mireds_to_byte(self._temperature)))
            elif ATTR_HS_COLOR in kwargs:
                if not self._is_same_color(*kwargs[ATTR_HS_COLOR]):
                    self._rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                    self._attr_color_mode = COLOR_MODE_HS
                    futures.append(self._backlight.set_color(self._rgb))
            self.async_write_ha_state()
            await gather(*futures)
            self._attr_available = True
        except ClientError:
            self._attr_available = False

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            await self._backlight.set_power(False)
            self._is_on = False
            self._attr_available = True
        except ClientError:
            self._attr_available = False
        self.async_write_ha_state()

    def _is_same_color(self, hue: float, saturation: float):
        return self._rgb == color_util.color_hs_to_RGB(hue, saturation)

    def _mireds_to_byte(self, mireds: int) -> int:
        ranged_temp = mireds - self._attr_min_mireds
        percent = ranged_temp / self._mireds_range_max
        return int(255 * percent)

    def _byte_to_mireds(self, byte_temp: int) -> int:
        percent = byte_temp / 255
        return int(percent *  self._mireds_range_max) + self._attr_min_mireds
