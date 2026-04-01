from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
NETLIST_PATH = PROJECT_ROOT / "hardware/pcb/cherry.net.json"
EASYEDA_STD_PATH = PROJECT_ROOT / "hardware/pcb/cherry.easyeda.std.json"
IOC_PATH = PROJECT_ROOT / "hardware/cherry/cherry.ioc"


def test_cherry_netlist_captures_firmware_backed_connectivity() -> None:
    data = json.loads(NETLIST_PATH.read_text(encoding="utf-8"))

    assert data["project"]["name"] == "cherry"
    assert "STM32H743ZIT6" in {component["value"] for component in data["components"]}

    nets = {net["name"]: net for net in data["nets"]}

    assert {"PB8", "SHT31-DIS.SCL", "ATECC608A.SCL", "DS3231SN.SCL"} <= set(
        nets["I2C1_SCL"]["nodes"]
    )
    assert {"PB9", "SHT31-DIS.SDA", "ATECC608A.SDA", "DS3231SN.SDA"} <= set(
        nets["I2C1_SDA"]["nodes"]
    )
    assert {"PA5", "SX1278.SCK"} <= set(nets["SPI1_SCK"]["nodes"])
    assert {"PB4", "SX1278.DIO0"} <= set(nets["LORA_DIO0"]["nodes"])
    assert nets["VIBRATION_SENSOR"]["confidence"] == "not-populated"


def test_cherry_ioc_declares_runtime_pin_mapping() -> None:
    text = IOC_PATH.read_text(encoding="utf-8")

    for expected in [
        "Mcu.Pin0=PA0",
        "Mcu.Pin1=PA1",
        "Mcu.Pin2=PA5",
        "Mcu.Pin3=PA6",
        "Mcu.Pin4=PA7",
        "Mcu.Pin5=PA9",
        "Mcu.Pin6=PA10",
        "Mcu.Pin7=PB0",
        "Mcu.Pin8=PB4",
        "Mcu.Pin9=PB5",
        "Mcu.Pin10=PB6",
        "Mcu.Pin11=PB8",
        "Mcu.Pin12=PB9",
        "PA0.Signal=UART4_TX",
        "PA1.Signal=UART4_RX",
        "PA5.Signal=SPI1_SCK",
        "PA6.Signal=SPI1_MISO",
        "PA7.Signal=SPI1_MOSI",
        "PA9.Signal=USART1_TX",
        "PA10.Signal=USART1_RX",
        "PB8.Signal=I2C1_SCL",
        "PB9.Signal=I2C1_SDA",
        "PB4.Signal=GPXTI4",
        "PB5.Signal=GPIO_Output",
        "PB6.Signal=GPIO_Output",
        "PB0.Signal=GPIO_Output",
    ]:
        assert expected in text


def test_cherry_easyeda_std_export_exists_with_expected_nets() -> None:
    export = json.loads(EASYEDA_STD_PATH.read_text(encoding="utf-8"))

    assert export["docType"] == "5"
    assert export["title"] == "Cherry Reconstructed Schematic"
    assert len(export["schematics"]) == 1

    sheet = export["schematics"][0]
    assert sheet["docType"] == "1"
    data = json.loads(sheet["dataStr"])

    assert data["head"]["docType"] == "1"
    assert data["head"]["editorVersion"].startswith("6.")
    shape_blob = "\n".join(data["shape"])
    assert "N~420~200~0~#0000ff~I2C1_SCL" in shape_blob
    assert "N~420~240~0~#0000ff~I2C1_SDA" in shape_blob
    assert "N~420~360~0~#0000ff~LORA_DIO0" in shape_blob
    assert "T~L~40~50~0~#0000FF~~14pt" in shape_blob
