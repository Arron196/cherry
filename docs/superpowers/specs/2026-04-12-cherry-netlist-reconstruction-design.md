# Cherry Netlist Reconstruction And CubeMX Sync Design

## Summary

This change reconstructs a repository-owned netlist for the STM32-based Cherry hardware from the current firmware source and synchronizes the CubeMX project file so its pin/peripheral model matches the code that is actually running. The work favors traceability and low risk over trying to reverse-engineer or directly modify the existing `hardware/pcb/cherry.eprj2` database.

## Goals

- Rebuild a usable netlist artifact under `hardware/pcb/` from the current firmware and hardware guide.
- Make each reconstructed network traceable back to code or documentation evidence.
- Update `hardware/cherry/cherry.ioc` so its peripheral and pin assignments match the current firmware implementation.
- Preserve the existing hand-maintained firmware source files and avoid accidental CubeMX/codegen drift during this pass.
- Make it obvious which hardware connections are confirmed by code, which are inferred from documentation, and which are intentionally unpopulated.

## Non-Goals

- Editing the internal SQLite contents of `hardware/pcb/cherry.eprj2`.
- Claiming that the reconstructed netlist is a vendor-native schematic export.
- Adding new firmware features or changing runtime behavior.
- Regenerating STM32 source from CubeMX in this change.
- Inventing circuitry that is not supported by the current repository evidence.

## Current Constraints

### PCB Project State

`hardware/pcb/cherry.eprj2` is an SQLite-backed EDA project container. Its top-level project metadata exists, but the main schematic, board, and device tables are effectively empty in the current checkout. There is not enough stable, human-readable source inside the repository to safely reconstruct or patch the vendor-native design database.

### Firmware As Source Of Truth

The current firmware is the most reliable description of the active hardware boundary:

- `hardware/cherry/Core/Inc/main.h` defines logical pins and device I2C addresses.
- `hardware/cherry/Core/Src/main.c` initializes I2C1, UART4, USART1, SPI1, GPIO, and EXTI usage.
- `hardware/cherry/Core/Src/stm32h7xx_hal_msp.c` maps those peripherals onto physical STM32 pins.
- `hardware/cherry/Core/Src/cherry_hw.c` proves which external modules are actually spoken to on each bus.
- `hardware/cherry/HARDWARE_GUIDE.md` provides shared rails, pull-up guidance, and module-level naming that code alone does not fully encode.

### CubeMX Drift

`hardware/cherry/cherry.ioc` currently contains almost no explicit peripheral pin configuration, even though the C source initializes and uses the buses. That mismatch increases maintenance risk because the CubeMX project does not reflect the real firmware hardware boundary.

## Source Priority

When reconstructing the netlist, evidence should be resolved in this order:

1. `hardware/cherry/Core/Inc/main.h`
2. `hardware/cherry/Core/Src/stm32h7xx_hal_msp.c`
3. `hardware/cherry/Core/Src/main.c`
4. `hardware/cherry/Core/Src/cherry_hw.c`
5. `hardware/cherry/HARDWARE_GUIDE.md`

Rationale:

- `main.h` and HAL MSP code define the pin truth most directly.
- `main.c` confirms configured peripheral instances and GPIO directions.
- `cherry_hw.c` confirms protocol-level usage and external module identities.
- `HARDWARE_GUIDE.md` is used to complete shared power and pull-up relationships that firmware does not model directly.

## Proposed Outputs

### Reconstructed Netlist

Create a machine-readable netlist file at:

- `hardware/pcb/cherry.net.json`

This file will represent:

- Components/modules involved in the current firmware-supported hardware boundary.
- Nets and connected pins.
- A confidence/evidence trail for each net.
- Explicit notes for inferred shared rails and optional/not-populated hardware.

### Supporting Documentation

Create a short companion document at:

- `hardware/pcb/README.md`

This document will explain:

- That the netlist is reconstructed from firmware and repository documentation.
- How to interpret evidence tags.
- Why `cherry.eprj2` was left untouched.

### CubeMX Sync

Update:

- `hardware/cherry/cherry.ioc`

So it reflects the current firmware pin/peripheral model without changing unrelated clocking or generated-source assumptions.

## Netlist Scope

### Included Hardware

- MCU: `STM32H743ZIT6`
- I2C bus: `SHT31-DIS`, `ATECC608A`, `DS3231SN`
- UART4 bus: `MH-Z19B`
- USART1 bus: `ESP8266`
- SPI1 and control lines: `SX1278`
- GPIO output: status LED on `PB0`
- Shared power rails and ground
- I2C pull-up requirement on `PB8`/`PB9`

### Explicitly Marked As Unpopulated Or Undriven

- Dedicated vibration sensor hardware

The firmware now explicitly treats vibration as not currently wired in this build. The reconstructed netlist should not fabricate a vibration signal path.

## Reconstructed Connectivity

### I2C1

- `PB8` -> `I2C1_SCL` -> shared with `SHT31-DIS.SCL`, `ATECC608A.SCL`, `DS3231SN.SCL`
- `PB9` -> `I2C1_SDA` -> shared with `SHT31-DIS.SDA`, `ATECC608A.SDA`, `DS3231SN.SDA`
- `3V3` pull-ups required on both lines per hardware guide

Evidence:

- `main.h` I2C addresses
- `stm32h7xx_hal_msp.c` pin map to `PB8/PB9`
- `cherry_hw.c` I2C transactions to all three devices
- `HARDWARE_GUIDE.md` pull-up and module naming

### UART4 / MH-Z19B

- `PA0` -> `UART4_TX` -> `MH-Z19B.RX`
- `PA1` -> `UART4_RX` -> `MH-Z19B.TX`

Evidence:

- `stm32h7xx_hal_msp.c`
- `main.c` UART4 init at `9600 8N1`
- `cherry_hw.c` MH-Z19B command/response flow
- `HARDWARE_GUIDE.md`

### USART1 / ESP8266

- `PA9` -> `USART1_TX` -> `ESP8266.RX`
- `PA10` -> `USART1_RX` -> `ESP8266.TX`
- `ESP8266.EN` -> pulled high (documented requirement)

Evidence:

- `stm32h7xx_hal_msp.c`
- `main.c` USART1 init at `115200 8N1`
- `cherry_hw.c` AT command transport
- `HARDWARE_GUIDE.md`

### SPI1 / SX1278

- `PA5` -> `SPI1_SCK` -> `SX1278.SCK`
- `PA6` -> `SPI1_MISO` -> `SX1278.MISO`
- `PA7` -> `SPI1_MOSI` -> `SX1278.MOSI`
- `PB6` -> GPIO output -> `SX1278.NSS`
- `PB5` -> GPIO output -> `SX1278.RESET`
- `PB4` -> EXTI rising input -> `SX1278.DIO0`

Evidence:

- `main.h`
- `main.c` GPIO and SPI init
- `stm32h7xx_hal_msp.c`
- `cherry_hw.c` LoRa register writes and DIO0 completion handling
- `stm32h7xx_it.c` EXTI callback
- `HARDWARE_GUIDE.md`

### Status LED

- `PB0` -> GPIO output -> status LED signal

Evidence:

- `main.h`
- `main.c`
- `HARDWARE_GUIDE.md`

### Power Nets

- `3V3` shared to all modules and MCU-side IO domain
- `GND` common across all modules
- `18650` plus charger/regulator feeding the `3V3` domain

Evidence:

- `HARDWARE_GUIDE.md`

These nets are documentation-backed rather than firmware-addressable, so the output should mark them as guide-derived.

## Netlist Data Shape

The JSON netlist should be structured for both human review and later conversion work. It should include:

- Project metadata
- Source files used for reconstruction
- Components with names, roles, and note fields
- Nets with:
  - net name
  - member endpoints
  - evidence list
  - confidence level
  - notes

Suggested confidence levels:

- `code-confirmed`
- `guide-confirmed`
- `inferred-shared-rail`
- `not-populated`

## CubeMX Sync Plan

Update `hardware/cherry/cherry.ioc` so it declares the same pin usage already present in firmware:

- `PB8` as `I2C1_SCL`
- `PB9` as `I2C1_SDA`
- `PA0` as `UART4_TX`
- `PA1` as `UART4_RX`
- `PA9` as `USART1_TX`
- `PA10` as `USART1_RX`
- `PA5` as `SPI1_SCK`
- `PA6` as `SPI1_MISO`
- `PA7` as `SPI1_MOSI`
- `PB4` as GPIO external interrupt input
- `PB5` as GPIO output for LoRa reset
- `PB6` as GPIO output for LoRa chip select
- `PB0` as GPIO output for status LED

The sync should also declare the enabled peripherals and their intended modes so the `.ioc` file stops representing a blank board.

## Change Boundaries

### Files Expected To Change

- `hardware/cherry/cherry.ioc`
- `hardware/pcb/cherry.net.json`
- `hardware/pcb/README.md`

### Files Not Expected To Change

- `hardware/cherry/Core/Src/main.c`
- `hardware/cherry/Core/Src/stm32h7xx_hal_msp.c`
- `hardware/cherry/Core/Src/cherry_hw.c`
- `hardware/cherry/Core/Inc/main.h`
- `hardware/pcb/cherry.eprj2`

If repository reality forces a change outside this list, that should be treated as a design mismatch and revisited explicitly instead of quietly expanding scope.

## Error Handling And Ambiguity Rules

- If a connection is proven by code but the external module pin name only exists in the hardware guide, keep the net and mark the external endpoint as guide-named.
- If a connection exists in the guide but not in firmware, include it only when it is a shared rail or board-level support connection needed to make the listed modules operable.
- If a device capability is mentioned in old docs but explicitly absent in current firmware behavior, mark it as `not-populated` or omit it rather than inventing nets.

## Verification Strategy

### Netlist Verification

- Cross-check each net against `main.h`, `main.c`, `stm32h7xx_hal_msp.c`, and `cherry_hw.c`.
- Confirm each bus has both MCU endpoints and module endpoints.
- Confirm no vibration sensor net is introduced.

### CubeMX Verification

- Re-read the updated `.ioc` file and confirm all intended pins/peripherals appear.
- Ensure the `.ioc` update does not silently alter unrelated system-clock settings beyond what is needed for the newly declared peripherals.

### Repository Verification

- Verify `hardware/pcb` contains the new netlist and companion documentation.
- Verify the design remains readable without requiring the proprietary EDA tool.

## Risks And Mitigations

### Risk: Overstating certainty

Mitigation: every reconstructed net carries source evidence and confidence labeling.

### Risk: CubeMX file diverges from hand-written init code again

Mitigation: mirror only the firmware behavior already present in code and avoid speculative peripheral configuration.

### Risk: Consumers mistake the JSON file for a vendor-native netlist export

Mitigation: document the reconstructed nature clearly in `hardware/pcb/README.md`.

### Risk: Shared power circuitry is under-specified

Mitigation: include only the rails and regulator relationship that the hardware guide explicitly states.

## Success Criteria

- `hardware/pcb/cherry.net.json` exists and describes the firmware-supported hardware boundary.
- Each reconstructed net is traceable to repository evidence.
- `hardware/pcb/README.md` explains provenance and limitations.
- `hardware/cherry/cherry.ioc` reflects the current firmware pin/peripheral assignments.
- No changes are made to `hardware/pcb/cherry.eprj2`.
- No new runtime behavior is introduced in firmware source as part of this work.
