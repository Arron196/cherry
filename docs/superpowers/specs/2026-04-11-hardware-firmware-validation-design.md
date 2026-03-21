# Hardware Firmware And Validation Repair Design

## Summary

This change repairs the STM32 firmware's current hardware boundary mistakes and restores a usable repository-level validation path for the firmware/backend integration. The work keeps the existing product contract stable while removing false success paths in the firmware and eliminating the current ambiguity around compat versus canonical ingest behavior.

## Goals

- Repair the firmware's incorrect reuse of `PB4` as both LoRa `DIO0` and a vibration input.
- Make LoRa transmit success mean "transmission completed or timed out cleanly", not merely "SPI registers were written".
- Make ESP8266 Wi-Fi success mean "HTTP request received a 2xx response", not merely "`SEND OK` was observed".
- Preserve the current system contract that STM32 firmware defaults to compat ingest while the Python simulator defaults to canonical ingest.
- Restore a reliable local validation path for hardware-related Python tests and development startup.
- Update hardware documentation so it matches the actual firmware behavior and current known limitations.

## Non-Goals

- Introducing a new physical vibration sensor driver in this change.
- Reworking the entire firmware into a full driver architecture.
- Changing backend ingest contracts or removing compat routes.
- Switching the STM32 firmware default ingest mode from compat to canonical.

## Root Causes

### PB4 Boundary Error

`PB4` is wired and configured as the SX1278 `DIO0` interrupt line, but the firmware also reads it as `vibration_alarm`. That makes the vibration field a side effect of LoRa state, not a real sensor reading.

### False LoRa Success

`CherryHw_SendViaLoRa()` currently writes registers and enters transmit mode, then immediately returns success. There is no completion wait based on `DIO0`, no timeout result, and no cleared transmit status flow.

### False Wi-Fi Success

`CherryHw_SendViaWiFi()` currently treats ESP8266 `SEND OK` as end-to-end success. That only proves the module accepted the outbound bytes. It does not prove the backend returned a successful HTTP status.

### Ambiguous Signature Fallback Behavior

The firmware currently falls back to a local digest-derived signature if ATECC signing fails. That is acceptable for compat-mode bring-up, but it is not acceptable for canonical-mode ingest that expects verifiable signatures on the backend.

### Broken Validation Environment

The repository currently mixes firmware C, backend Python, and simulator/test Python. That is valid, but the local validation path is incomplete because the project virtual environment does not currently provide the dev test tooling needed to execute the hardware-related Python test suite cleanly.

## Design Decisions

### Ingest Mode Defaults

- Keep STM32 firmware default ingest mode as `compat`.
- Keep simulator default ingest mode as `canonical`.

Rationale:

- The canonical backend path verifies signatures more strictly.
- The STM32 firmware is still designed for field bring-up where ATECC availability and backend key registration may lag.
- The simulator is a development tool with deterministic HMAC signing and can safely exercise canonical ingest by default.

### Vibration Semantics

- Remove the implicit use of LoRa `DIO0` as vibration state.
- Treat vibration as an optional hardware capability.
- When no dedicated vibration sensor exists, emit a stable default of "no vibration alarm" on the firmware side.

This preserves payload shape while removing bogus readings.

### LoRa Transmit Completion

- Add firmware state that records LoRa transmit completion from the `DIO0` interrupt.
- Clear that state before each transmit.
- Wait for completion with a bounded timeout.
- Return success only when transmit completion is observed.

### Wi-Fi HTTP Result Handling

- Continue using the ESP8266 AT flow.
- After `SEND OK`, read the HTTP response stream and parse the first status line.
- Treat `2xx` as success.
- Treat timeout, malformed response, or non-`2xx` status as failure.

### Signature Fallback Policy

- Compat mode may continue to send with fallback signatures to support bring-up and legacy backend behavior.
- Canonical mode must not report success if the firmware had to use fallback signing instead of ATECC.

This prevents known-invalid canonical payloads from being treated as successfully transmitted.

## Planned Code Changes

### Firmware

- `hardware/cherry/Core/Src/cherry_hw.c`
  - Add LoRa interrupt/completion state.
  - Add a LoRa transmit wait routine.
  - Stop reading `PB4` as vibration input.
  - Add explicit signing-origin and sensor-validity tracking.
  - Parse HTTP status codes from ESP8266 responses.
  - Make canonical-mode Wi-Fi send reject fallback-signed payloads.
- `hardware/cherry/Core/Inc/cherry_hw.h`
  - Extend firmware packet/snapshot structures with lightweight status flags needed by task logic.
- `hardware/cherry/Core/Src/app_freertos.c`
  - Preserve retry behavior while reacting to the more accurate transport results.
- `hardware/cherry/Core/Src/stm32h7xx_it.c`
  - Route `DIO0` interrupts into firmware LoRa completion handling.
- `hardware/cherry/HARDWARE_GUIDE.md`
  - Remove the implication that `PB4` is a vibration sensor input.
  - Document current vibration behavior as optional/not populated without dedicated hardware.
  - Clarify canonical-mode expectations and Wi-Fi placeholders.

### Validation Chain

- `pyproject.toml`
  - Ensure local dev/test dependencies are sufficient for the hardware-related test suite.
- `run_local.py`
  - Document or reinforce local runtime expectations for backend validation.
- `tests/integration/test_hardware_ingest_migration_modes.py`
  - Add assertions that codify the intended default mode split and idempotency behavior.
- Potential new test file under `tests/integration/`
  - Add focused coverage for any new simulator-side or runtime-side validation behavior if existing tests would become overloaded.

## Error Handling

- RTC read failure continues to fall back to `HAL_GetTick() / 1000`, but this is treated as degraded sensor state internally.
- Sensor read failure continues to populate sentinel/default values instead of crashing task flow.
- LoRa timeout returns transport failure and triggers existing retry logic.
- Wi-Fi timeout or non-`2xx` response returns transport failure and triggers existing retry logic.
- Canonical mode with fallback signing returns Wi-Fi failure without issuing the HTTP request.

## Testing Strategy

### Firmware-Oriented Validation

- If the ARM toolchain is available, configure and build `hardware/cherry` through the existing CMake presets.
- Verify that the changed firmware files compile under the current STM32 project configuration.

### Python Validation

- Use the project virtual environment, not system Python.
- Install missing dev dependencies if the virtual environment lacks them.
- Run the hardware migration and compat-signature tests first because they are the closest repository-level contract for firmware/backend interoperability.

### Documentation Validation

- Reconcile `HARDWARE_GUIDE.md` with the actual pin behavior and runtime behavior in firmware.

## Risks And Mitigations

### Risk: Interrupt race around LoRa completion

Mitigation: clear completion state before transmit, use volatile state, and only set completion from the EXTI callback path.

### Risk: ESP8266 response parsing is brittle

Mitigation: implement a minimal parser that only searches for the HTTP status line and treats ambiguous responses as failure.

### Risk: Over-coupling packet status to payload contract

Mitigation: keep new firmware status flags internal to firmware structures unless they are already part of an existing payload contract.

## Success Criteria

- Firmware no longer uses `PB4` for vibration data.
- LoRa success requires interrupt-backed completion or an equivalent positive confirmation.
- Wi-Fi success requires a parsed `2xx` HTTP result.
- Compat and canonical defaults remain intentional and documented.
- The local Python validation path for hardware-related tests is runnable from the project environment.
- Hardware documentation matches the implemented firmware behavior.
