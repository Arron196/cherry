"""Pre-configured STM32 device for refrigerated-transport monitoring."""

from __future__ import annotations

from .sensors import AccelerometerSimulator, MHZ19BSimulator, SHT31Simulator
from .stm32_device import STM32Device


class TransportDevice(STM32Device):
    """STM32H743 configured for refrigerated-truck transport monitoring.

    Default sensor parameters:
    - Temperature : 2-6 C (base 4.0 C, gaussian noise sigma=0.5)
    - Humidity    : 85-95% (base 88.0%, gaussian noise sigma=1.5)
    - CO2         : ~10% atmosphere = 100 000 ppm
    - Vibration   : moderate (base 0.3 g); 10% chance of bump >0.8 g
    - batch_id    : TRANSPORT-YYYYMMDD-XXX
    """

    def __init__(
        self,
        device_id: str = "STM32-TRANSPORT-001",
        gateway_url: str = "http://localhost:18941",
        signing_key_id: str | None = None,
        signing_secret: str | None = None,
        ingest_mode: str | None = None,
        *,
        base_temp: float = 4.0,
        base_humidity: float = 88.0,
        base_co2: float = 100000,
        base_vibration: float = 0.3,
    ) -> None:
        super().__init__(
            device_id=device_id,
            device_type="transport",
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
                base_vibration=base_vibration, is_transport=True
            ),
        }
