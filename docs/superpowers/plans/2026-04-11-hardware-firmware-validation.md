# Hardware Firmware Validation Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the STM32 firmware transport/signing boundary errors and restore a runnable repository validation path for the firmware/backend integration.

**Architecture:** Keep the current firmware/backend contracts intact while tightening the firmware's definition of success and separating LoRa interrupt state from payload data. Validation stays split between STM32 C firmware checks and Python integration tests, with the project virtual environment as the single local entry point for backend-related verification.

**Tech Stack:** STM32 HAL, FreeRTOS, CMake, FastAPI, pytest, httpx, Python 3.11

---

## File Structure

- Modify: `hardware/cherry/Core/Inc/cherry_hw.h`
  - Add internal firmware status flags needed to distinguish ATECC signing from fallback signing and to track degraded reads without changing public backend contracts.
- Modify: `hardware/cherry/Core/Src/cherry_hw.c`
  - Fix PB4 usage, implement LoRa completion handling, add ESP8266 HTTP status parsing, and tighten canonical-mode send behavior.
- Modify: `hardware/cherry/Core/Src/app_freertos.c`
  - Consume the corrected transport results without changing the overall task topology.
- Modify: `hardware/cherry/Core/Src/stm32h7xx_it.c`
  - Bridge EXTI4 into the LoRa completion state handler.
- Modify: `hardware/cherry/HARDWARE_GUIDE.md`
  - Align the wiring/runtime guide with the repaired firmware behavior.
- Modify: `pyproject.toml`
  - Ensure the repository's dev environment can execute the required tests.
- Modify: `run_local.py`
  - Keep local development guidance aligned with the repaired validation flow.
- Modify: `tests/integration/test_hardware_ingest_migration_modes.py`
  - Lock in compat/canonical defaults and hardware ingest expectations.
- Possibly create: `tests/integration/test_hardware_runtime_defaults.py`
  - Add focused tests if existing migration tests become too dense.

### Task 1: Restore Python Validation Entry Point

**Files:**
- Modify: `pyproject.toml`
- Modify: `run_local.py`
- Test: `tests/integration/test_hardware_ingest_migration_modes.py`

- [ ] **Step 1: Write the failing validation command**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q
```

Expected: the command currently fails because the virtual environment does not yet provide the required dev tooling.

- [ ] **Step 2: Update dev dependencies**

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0.0,<9.0.0",
  "pytest-asyncio>=0.23.0,<1.0.0",
]
```

Add any missing minimal test dependency only if it is required by the targeted hardware-related test commands.

- [ ] **Step 3: Keep the local runtime path explicit**

```python
print("  Use: .venv\\Scripts\\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q")
```

Place this only where it fits the existing `run_local.py` startup guidance style.

- [ ] **Step 4: Reinstall the local project in editable dev mode**

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: the environment now includes `pytest`.

- [ ] **Step 5: Re-run the hardware-related test command**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q
```

Expected: the suite now runs to assertion results instead of failing at missing-module startup.

### Task 2: Add Failing Tests For Intended Hardware/Simulator Defaults

**Files:**
- Modify: `tests/integration/test_hardware_ingest_migration_modes.py`
- Test: `tests/integration/test_hardware_ingest_migration_modes.py`

- [ ] **Step 1: Add a failing test for simulator default canonical mode**

```python
def test_simulator_defaults_to_canonical_mode_when_not_overridden() -> None:
    device = STM32Device(
        device_id="sim-default-mode",
        device_type="transport",
        gateway_url="http://test.local",
        signing_key_id="factory-key-1",
        signing_secret="super-secret",
    )

    assert device.ingest_mode == "canonical"
```

- [ ] **Step 2: Add a failing test that documents compat payload fallback expectations**

```python
def test_compat_payload_contains_transport_stage_defaults() -> None:
    payload = _compat_payload(sequence=303)

    assert payload["stage"] == "transport"
    assert payload["key_id"] == "factory-key-1"
```

- [ ] **Step 3: Run the targeted test file and verify failure or existing gap**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q
```

Expected: either the new tests fail before implementation or they demonstrate that the existing behavior is already covered and no further code change is needed for that exact branch.

- [ ] **Step 4: Keep or trim duplicate coverage after confirming results**

```python
# Keep the new tests only if they enforce behavior not already covered elsewhere.
```

- [ ] **Step 5: Re-run the targeted test file until it is green**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q
```

Expected: PASS.

### Task 3: Repair Firmware LoRa, Vibration, And Wi-Fi Success Semantics

**Files:**
- Modify: `hardware/cherry/Core/Inc/cherry_hw.h`
- Modify: `hardware/cherry/Core/Src/cherry_hw.c`
- Modify: `hardware/cherry/Core/Src/app_freertos.c`
- Modify: `hardware/cherry/Core/Src/stm32h7xx_it.c`

- [ ] **Step 1: Add firmware status fields needed by transport logic**

```c
typedef struct {
  uint32_t unix_time;
  float temperature_c;
  float humidity_rh;
  uint16_t co2_ppm;
  bool vibration_alarm;
  bool rtc_valid;
  bool env_valid;
  bool co2_valid;
} CherrySensorSnapshot;

typedef struct {
  CherrySensorSnapshot snapshot;
  uint8_t digest[32];
  uint8_t signature[64];
  uint8_t signature_len;
  uint32_t sequence;
  bool signature_from_secure_element;
} CherrySignedPacket;
```

- [ ] **Step 2: Add a minimal LoRa completion API**

```c
void CherryHw_OnLoRaDio0Rise(void);
```

Implement it so EXTI can mark a volatile transmit-complete flag.

- [ ] **Step 3: Stop using `PB4` as a vibration source**

```c
out->vibration_alarm = false;
```

Replace the current `HAL_GPIO_ReadPin(LORA_DIO0_GPIO_Port, LORA_DIO0_Pin)` use in sensor sampling with a stable default.

- [ ] **Step 4: Track degraded sensor state explicitly**

```c
out->rtc_valid = true;
out->env_valid = true;
out->co2_valid = true;
```

Flip these booleans to `false` on read failure while preserving the current fallback value behavior.

- [ ] **Step 5: Record whether signing came from ATECC**

```c
if (atecc_sign_digest(out->digest, out->signature) == HAL_OK) {
  out->signature_len = 64U;
  out->signature_from_secure_element = true;
  return HAL_OK;
}

fallback_sign(out->digest, out->signature);
out->signature_len = 64U;
out->signature_from_secure_element = false;
return HAL_ERROR;
```

- [ ] **Step 6: Add a LoRa transmit wait helper**

```c
static HAL_StatusTypeDef lora_wait_tx_done(uint32_t timeout_ms) {
  uint32_t start = HAL_GetTick();
  while ((HAL_GetTick() - start) < timeout_ms) {
    if (g_lora_tx_done != 0U) {
      g_lora_tx_done = 0U;
      return HAL_OK;
    }
  }
  return HAL_TIMEOUT;
}
```

- [ ] **Step 7: Change LoRa send to require completion**

```c
g_lora_tx_done = 0U;
if (lora_write_reg(0x01U, 0x83U) != HAL_OK) {
  return HAL_ERROR;
}
return lora_wait_tx_done(1000U);
```

- [ ] **Step 8: Add ESP8266 HTTP status parsing**

```c
static HAL_StatusTypeDef esp8266_wait_http_2xx(uint32_t timeout_ms) {
  char window[192] = {0};
  size_t used = 0U;
  uint32_t start = HAL_GetTick();

  while ((HAL_GetTick() - start) < timeout_ms) {
    uint8_t ch;
    if (HAL_UART_Receive(&huart1, &ch, 1U, 20U) != HAL_OK) {
      continue;
    }
    if (used < sizeof(window) - 1U) {
      window[used++] = (char)ch;
    } else {
      memmove(window, &window[1], sizeof(window) - 2U);
      window[sizeof(window) - 2U] = (char)ch;
      used = sizeof(window) - 1U;
    }
    window[used] = '\0';

    if (strstr(window, "HTTP/1.1 2") != NULL || strstr(window, "HTTP/1.0 2") != NULL) {
      return HAL_OK;
    }
    if (strstr(window, "HTTP/1.1 4") != NULL || strstr(window, "HTTP/1.1 5") != NULL ||
        strstr(window, "HTTP/1.0 4") != NULL || strstr(window, "HTTP/1.0 5") != NULL) {
      return HAL_ERROR;
    }
  }
  return HAL_TIMEOUT;
}
```

- [ ] **Step 9: Make Wi-Fi send require `SEND OK` and HTTP `2xx`**

```c
if (esp8266_wait_for_token("SEND OK", 5000U) != HAL_OK) {
  (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
  return HAL_ERROR;
}

if (esp8266_wait_http_2xx(5000U) != HAL_OK) {
  (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
  return HAL_ERROR;
}
```

- [ ] **Step 10: Block canonical sends that only have fallback signatures**

```c
#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
  if (!packet->signature_from_secure_element) {
    g_wifi_ready = 0U;
    return HAL_ERROR;
  }
#endif
```

- [ ] **Step 11: Wire EXTI4 into the new LoRa completion hook**

```c
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  if (GPIO_Pin == LORA_DIO0_Pin) {
    CherryHw_OnLoRaDio0Rise();
  }
}
```

- [ ] **Step 12: Build the firmware if the toolchain exists**

```powershell
cmake --preset Debug hardware/cherry
cmake --build --preset Debug --target cherry
```

Expected: successful firmware build, or a documented toolchain-missing blocker if `arm-none-eabi` tooling is unavailable on this machine.

### Task 4: Align Documentation With Implemented Behavior

**Files:**
- Modify: `hardware/cherry/HARDWARE_GUIDE.md`

- [ ] **Step 1: Remove the incorrect vibration implication from the pin map/runtime notes**

```md
- `PB4` is reserved for `SX1278 DIO0` interrupt handling.
- Firmware currently emits no dedicated vibration alarm unless separate vibration hardware is added.
```

- [ ] **Step 2: Clarify compat/canonical expectations**

```md
- STM32 firmware defaults to compat ingest for bring-up.
- Canonical ingest requires valid backend-verifiable signing material.
```

- [ ] **Step 3: Clarify Wi-Fi success semantics**

```md
- Wi-Fi transmission is only considered successful after the backend returns an HTTP 2xx response.
```

### Task 5: Final Verification

**Files:**
- Test: `tests/integration/test_hardware_ingest_migration_modes.py`
- Test: `tests/integration/test_compat_signature_parity.py`
- Test: firmware CMake build outputs

- [ ] **Step 1: Run the targeted Python hardware migration tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_hardware_ingest_migration_modes.py -q
```

- [ ] **Step 2: Run the compat signature parity tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_compat_signature_parity.py -q
```

- [ ] **Step 3: Run the firmware build check if toolchain is available**

```powershell
cmake --preset Debug hardware/cherry
cmake --build --preset Debug --target cherry
```

- [ ] **Step 4: Record any remaining non-fixable local blockers explicitly**

```text
Examples: missing ARM toolchain, missing board hardware, or environment-only secrets not present in this workspace.
```

## Self-Review

- Spec coverage: the plan covers validation repair, firmware boundary repair, LoRa completion, Wi-Fi HTTP confirmation, docs, and verification.
- Placeholder scan: no `TODO`/`TBD` markers remain.
- Type consistency: plan uses `CherrySensorSnapshot`, `CherrySignedPacket`, and `CherryHw_OnLoRaDio0Rise` consistently across firmware steps.
