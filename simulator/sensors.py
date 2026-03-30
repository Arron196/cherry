"""Simulated sensors for the cherry cold-chain monitoring system."""

from __future__ import annotations

import random


class SHT31Simulator:
    """SHT31 temperature / humidity sensor (I2C)."""

    def __init__(self, base_temp: float = 2.0, base_humidity: float = 92.0) -> None:
        self.base_temp = base_temp
        self.base_humidity = base_humidity

    def read(self) -> dict:
        temp = self.base_temp + random.gauss(0, 0.5)
        humidity = self.base_humidity + random.gauss(0, 1.5)
        return {
            "temperature_c": round(temp, 2),
            "humidity_pct": round(min(100.0, max(0.0, humidity)), 2),
        }


class MHZ19BSimulator:
    """MH-Z19B CO2 sensor (UART).  Values in ppm."""

    def __init__(self, base_co2: float = 120000) -> None:
        self.base_co2 = base_co2

    def read(self) -> dict:
        return {"co2_ppm": round(self.base_co2 + random.gauss(0, 5000), 0)}


class AccelerometerSimulator:
    """Generic 3-axis accelerometer for vibration monitoring."""

    def __init__(self, base_vibration: float = 0.1, is_transport: bool = False) -> None:
        self.base_vibration = base_vibration
        self.is_transport = is_transport

    def read(self) -> dict:
        if self.is_transport:
            if random.random() < 0.10:
                vib = random.uniform(0.8, 2.0)
            else:
                vib = self.base_vibration + random.gauss(0, 0.1)
        else:
            vib = self.base_vibration + random.gauss(0, 0.02)
        return {"vibration_g": round(max(0.0, vib), 3)}
