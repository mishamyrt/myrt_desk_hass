"""MyrtDesk update coordinator"""
from logging import getLogger
from datetime import timedelta
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from async_timeout import timeout
from aiohttp import ClientError
from myrt_desk_api import MyrtDesk

_LOGGER = getLogger(__name__)

class MyrtDeskCoordinator(DataUpdateCoordinator):
    """MyrtDesk update coordinator"""

    def __init__(self, hass, desk: MyrtDesk):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="MyrtDesk API",
            update_interval=timedelta(seconds=5),
        )
        self.desk = desk

    async def _async_update_data(self):
        try:
            async with timeout(10):
                light = await self.desk.backlight.read_state()
                heap = await self.desk.system.read_heap()
                height = await self.desk.legs.get_height()
                return {
                    "light": light,
                    "heap": heap,
                    "height": height
                }
        except (ClientError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
