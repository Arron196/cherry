# Cherry Hardware Assembly Guide

## 1. Hardware Set

- MCU: `STM32H743ZIT6` (development board: `NUCLEO-H743ZI2`)
- Temperature/Humidity: `SHT31-DIS` (I2C)
- CO2: `MH-Z19B` (UART)
- Secure Element: `ATECC608A` (I2C)
- RTC: `DS3231SN` (I2C)
- Wi-Fi: `ESP8266` (UART)
- LoRa: `SX1278` (SPI)
- Power: `18650` + charger + stable `3.3V` regulator

## 2. STM32 Pin Map

| Function | STM32 Pin | Peripheral | Module Pin |
|---|---|---|---|
| I2C1_SCL | PB8 | I2C1 | SHT31/ATECC608A/DS3231 SCL |
| I2C1_SDA | PB9 | I2C1 | SHT31/ATECC608A/DS3231 SDA |
| UART4_TX | PA0 | UART4 | MH-Z19B RX |
| UART4_RX | PA1 | UART4 | MH-Z19B TX |
| USART1_TX | PA9 | USART1 | ESP8266 RX |
| USART1_RX | PA10 | USART1 | ESP8266 TX |
| SPI1_SCK | PA5 | SPI1 | SX1278 SCK |
| SPI1_MISO | PA6 | SPI1 | SX1278 MISO |
| SPI1_MOSI | PA7 | SPI1 | SX1278 MOSI |
| LORA_DIO0 | PB4 | GPIO EXTI | SX1278 DIO0 |
| LORA_RESET | PB5 | GPIO Output | SX1278 RESET |
| LORA_NSS | PB6 | GPIO Output | SX1278 NSS |
| STATUS_LED | PB0 | GPIO Output | LED |

## 3. Wiring Rules

1. All modules and STM32 must share common `GND`.
2. Keep digital IO at `3.3V` level.
3. Add level shifting if any module TX is `5V`.
4. I2C needs pull-up resistors (`4.7k` to `3.3V`).
5. Connect LoRa antenna before transmission.

## 4. Wiring Diagram (ASCII)

```text
                  +--------------------+
                  |   STM32H743 (MCU) |
                  |                    |
     PB8  SCL ----+--------------------+---- SCL (SHT31)
     PB9  SDA ----+--------------------+---- SDA (SHT31)
                  |                    +---- SCL/SDA (ATECC608A)
                  |                    +---- SCL/SDA (DS3231)
                  |
     PA0  TX4 ----+--------------------+---- RX (MH-Z19B)
     PA1  RX4 <---+--------------------+---- TX (MH-Z19B)
                  |
     PA9  TX1 ----+--------------------+---- RX (ESP8266)
    PA10  RX1 <---+--------------------+---- TX (ESP8266)
                  |
     PA5  SCK ----+--------------------+---- SCK (SX1278)
     PA6 MISO <---+--------------------+---- MISO (SX1278)
     PA7 MOSI ----+--------------------+---- MOSI (SX1278)
     PB6  NSS ----+--------------------+---- NSS (SX1278)
     PB5 RST  ----+--------------------+---- RESET (SX1278)
     PB4 DIO0 <---+--------------------+---- DIO0 (SX1278)
                  |
     PB0  LED ----+--------------------+---- Status LED
                  |
     3.3V/GND ----+--------------------+---- All modules power rails
                  +--------------------+
```

## 5. Step-by-Step Assembly

1. Build power rails first (`3.3V` + `GND`) and confirm voltage stability.
2. Wire I2C bus (PB8/PB9) to SHT31, ATECC608A, DS3231.
3. Wire MH-Z19B to UART4 (PA0/PA1).
4. Wire ESP8266 to USART1 (PA9/PA10), and pull `EN` high.
5. Wire SX1278 to SPI1 + control pins (PA5/PA6/PA7 + PB6/PB5/PB4).
6. Add status LED on PB0.
7. Recheck all grounds and no swapped TX/RX lines.

## 6. Firmware Runtime Behavior

- `sensor` task: reads SHT31, MH-Z19B, DS3231 every 5 seconds.
- `sign` task: computes digest and requests ATECC608A signature.
- `tx` task: sends packet via Wi-Fi HTTP and LoRa.
- `retry` task: retries failed transmissions.
- `STATUS_LED` (PB0): ON only when both Wi-Fi and LoRa send succeed.
- `PB4` is reserved for LoRa `DIO0` transmit-complete interrupt handling.
- Firmware does not currently include a dedicated vibration sensor input; vibration is reported as inactive unless separate hardware is added.
- Wi-Fi transmission is only treated as successful after the backend returns an HTTP `2xx` response.

## 7. Wi-Fi/HTTP Configuration

Firmware uses AT commands to join Wi-Fi and POST JSON to your server.

Edit these macros in `Core/Src/cherry_hw.c` before flashing:

- `CHERRY_WIFI_SSID`
- `CHERRY_WIFI_PASSWORD`
- `CHERRY_HTTP_HOST`
- `CHERRY_HTTP_PORT`
- `CHERRY_HTTP_PATH`

Default placeholders (`YOUR_SSID`, `YOUR_PASSWORD`) must be replaced, otherwise Wi-Fi transmission is intentionally treated as failed.

Canonical ingest also requires a backend-verifiable device signature. The STM32 firmware therefore defaults to compat ingest for bring-up, while canonical mode should be used only after device signing has been provisioned end-to-end.

## 8. Device Addresses and UART Speeds

- I2C addresses:
  - SHT31: `0x44`
  - ATECC608A: `0x60`
  - DS3231: `0x68`
- UART speeds:
  - MH-Z19B (`UART4`): `9600 8N1`
  - ESP8266 (`USART1`): `115200 8N1`

## 9. Bring-Up Checklist

1. Check `3.3V` stability under module load.
2. Scan I2C and confirm `0x44`, `0x60`, `0x68`.
3. Verify MH-Z19B returns a valid `0x86` frame.
4. Verify ESP8266 responds to `AT`.
5. Verify SX1278 reset and SPI register writes.
6. Observe periodic packets and LED behavior after boot.
