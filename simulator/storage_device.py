"""Pre-configured STM32 device for cold-storage warehouse monitoring."""

from __future__ import annotations

from .sensors import AccelerometerSimulator, MHZ19BSimulator, SHT31Simulator
from .stm32_device import STM32Device


class StorageDevice(STM32Device):
    """STM32H743 configured for cold-storage warehouse monitoring.

    Default sensor parameters:
    - Temperature : 0-4 C (base 2.0 C, gaussian noise sigma=0.5)
    - Humidity    : 90-95% (base 92.0%, gaussian noise sigma=1.5)
    - CO2         : ~12% atmosphere = 120 000 ppm
    - Vibration   : very low (base 0.05 g, stationary)
    - batch_id    : STORAGE-YYYYMMDD-XXX
    """

    def __init__(
        self,
        device_id: str = "STM32-STORAGE-001",
        gateway_url: str = "http://localhost:18941",
        signing_key_id: str | None = None,
        signing_secret: str | None = None,
        ingest_mode: str | None = None,
        *,
        base_temp: float = 2.0,
        base_humidity: float = 92.0,
        base_co2: float = 120000,
        base_vibration: float = 0.05,
    ) -> None:
        # Bypass parent _init_sensors -- we configure sensors ourselves
        super().__init__(
            device_id=device_id,
            device_type="storage",
            gateway_url=gateway_url,
            signing_key_id=signing_key_id,
            signing_secret=signing_secret,
            ingest_mode=ingest_mode,
        )
        # Override sensors with caller-controlled baselines
        self.sensors = {
            "sht31": SHT31Simulator(base_temp=base_temp, base_humidity=base_humidity),
            "mhz19b": MHZ19BSimulator(base_co2=base_co2),
            "accel": AccelerometerSimulator(
                base_vibration=base_vibration, is_transport=False
            ),
        }
