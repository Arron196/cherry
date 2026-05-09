# Cherry PCB Reconstruction Notes

This folder now contains a repository-owned netlist artifact, [cherry.net.json](C:/学校/cherry/hardware/pcb/cherry.net.json), reconstructed from the firmware source and the hardware guide.

## Why this exists

The existing [cherry.eprj2](C:/学校/cherry/hardware/pcb/cherry.eprj2) file is an SQLite-backed EDA project container. In the current repository state it does not expose a complete, stable schematic/device dataset that can be safely edited by hand. Rather than corrupt that database, this repo stores a traceable JSON netlist next to it.

## Evidence labels

- `code-confirmed`: directly backed by `main.h`, HAL MSP pin mapping, `main.c`, or active peripheral usage in `cherry_hw.c`
- `guide-confirmed`: derived from `HARDWARE_GUIDE.md`
- `inferred-shared-rail`: shared power or board-level support net inferred from the hardware guide
- `not-populated`: intentionally absent hardware, such as the current vibration sensor input

## Scope

The reconstructed netlist covers the current firmware-supported boundary:

- STM32H743ZIT6 MCU
- I2C1 bus for SHT31-DIS, ATECC608A, DS3231SN
- UART4 link for MH-Z19B
- USART1 link for ESP8266
- SPI1 plus GPIO/EXTI control lines for SX1278
- PB0 status LED
- Shared `3V3`, `GND`, and I2C pull-up requirements

It does not claim to be a vendor-native schematic export, and it does not modify the original `.eprj2` database.

## JLC / EasyEDA JSON

For JLCEDA / EasyEDA standard import, this folder also includes [cherry.easyeda.std.json](C:/学校/cherry/hardware/pcb/cherry.easyeda.std.json).

- This file follows the EasyEDA standard source JSON container shape (`docType = 5`).
- It is a lightweight reconstructed overview sheet derived from the firmware-backed netlist, not a full symbol-accurate native schematic capture.
- In EasyEDA standard, the intended import path is the "open EasyEDA source" workflow documented by the official EasyEDA format docs.
