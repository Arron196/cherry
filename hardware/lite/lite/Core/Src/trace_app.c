#include "trace_app.h"
#include "crypto_sha256.h"
#include "main.h"
#include "oled_ssd1306.h"
#include "trace_upload_config.h"
#include "wifi_config.h"
#include "FreeRTOS.h"
#include "queue.h"
#include "semphr.h"
#include "task.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define PAGE_COUNT 6U
#define IR_LEARN_MODE 0U
#define IR_FRAME_TIMEOUT_US 20000U
#define IR_KEY_DEBOUNCE_MS 160U
#define IR_NAV_REPEAT_MS 320U
#define ESP8266_RX_BUFFER_SIZE 768U
#define ESP8266_CMD_BUFFER_SIZE 128U
#define ESP8266_RETRY_INTERVAL_MS 30000UL
#define ESP8266_READY_CHECK_INTERVAL_MS 120000UL
#define ESP8266_READY_MISS_LIMIT 3U
#define ESP8266_POST_JOIN_SETTLE_MS 5000UL
#define TRACE_UPLOAD_INTERVAL_MS 20000UL
#define TRACE_CANONICAL_BUFFER_SIZE 760U
#define TRACE_BODY_BUFFER_SIZE 960U
#define TRACE_HTTP_BUFFER_SIZE 1200U
#define TRACE_QR_SIZE 41U
#define TRACE_QR_SCALE 1U
#define TRACE_QR_X 0U
#define TRACE_QR_Y 1U

typedef enum
{
  IR_WAIT_LEADER_LOW = 0,
  IR_WAIT_LEADER_HIGH,
  IR_READ_BITS
} IR_State;

typedef struct
{
  uint8_t temp_c;
  uint8_t hum_pct;
  uint8_t ok;
} DHT11_Data;

typedef struct
{
  int16_t temp_centi;
  uint8_t ok;
  uint8_t converting;
  uint32_t convert_started_ms;
} DS18B20_Data;

typedef struct
{
  uint8_t w25_ok;
  uint8_t w25_id[3];
  uint8_t at24_ok;
  uint8_t oled_ok;
  uint8_t wifi_seen;
  uint8_t wifi_joined;
  uint8_t bt_seen;
} BoardStatus;

typedef enum
{
  WIFI_STATE_IDLE = 0,
  WIFI_STATE_NO_SSID,
  WIFI_STATE_AT_FAIL,
  WIFI_STATE_JOINING,
  WIFI_STATE_READY,
  WIFI_STATE_FAIL
} WifiState;

typedef enum
{
  UPLOAD_STATE_IDLE = 0,
  UPLOAD_STATE_NO_HOST,
  UPLOAD_STATE_NO_KEY,
  UPLOAD_STATE_NO_TIME,
  UPLOAD_STATE_SENDING,
  UPLOAD_STATE_OK,
  UPLOAD_STATE_FAIL
} UploadState;

typedef enum
{
  UPLOAD_FAIL_NONE = 0,
  UPLOAD_FAIL_AT,
  UPLOAD_FAIL_WIFI,
  UPLOAD_FAIL_MUX,
  UPLOAD_FAIL_START,
  UPLOAD_FAIL_BUILD,
  UPLOAD_FAIL_PROMPT,
  UPLOAD_FAIL_SEND,
  UPLOAD_FAIL_SEND_OK,
  UPLOAD_FAIL_RESP,
  UPLOAD_FAIL_BUSY,
  UPLOAD_FAIL_CLOSED,
  UPLOAD_FAIL_ERROR,
  UPLOAD_FAIL_NOLINK,
  UPLOAD_FAIL_DNS,
  UPLOAD_FAIL_STAT
} UploadFailReason;

typedef struct
{
  uint8_t key;
  uint8_t repeat;
} IR_Event;

typedef struct
{
  uint16_t sample;
  uint8_t dht_temp;
  uint8_t dht_hum;
  uint8_t dht_ok;
  int16_t ds18b20_temp_centi;
  uint8_t ds18b20_ok;
  uint8_t quality;
  uint8_t w25_ok;
  uint8_t at24_ok;
  uint8_t wifi_joined;
} TraceSnapshot;

static I2C_HandleTypeDef *app_i2c;
static SPI_HandleTypeDef *app_spi;
static TIM_HandleTypeDef *app_tim;

extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart3;

static volatile IR_State ir_state = IR_WAIT_LEADER_LOW;
static volatile uint16_t ir_last_us;
static volatile uint32_t ir_bits;
static volatile uint8_t ir_bit_count;

static DHT11_Data dht = {0};
static DS18B20_Data ds18b20 = {0};
static BoardStatus board = {0};

static uint8_t current_page;
static uint8_t auto_rotate;
static uint8_t quality_score = 75U;
static uint16_t sample_id = 1U;
static uint32_t batch_hash = 0x4C484552UL;
static uint8_t last_ir_key;
static const char *last_ir_action = "NONE";
#if IR_LEARN_MODE
static uint16_t ir_key_count;
static uint8_t last_ir_repeat;
#endif

static uint32_t last_sensor_ms;
static uint32_t last_auto_ms;
static uint32_t last_selftest_ms;
static uint32_t last_wifi_try_ms;
static uint32_t last_upload_ms;
static volatile uint8_t ui_dirty = 1U;
static WifiState wifi_state = WIFI_STATE_IDLE;
static UploadState upload_state = UPLOAD_STATE_IDLE;
static uint8_t esp_booted;
static uint8_t wifi_ready_miss_count;
static uint16_t upload_ok_count;
static uint16_t upload_fail_count;
static uint16_t upload_seq = 1U;
static uint16_t last_http_status;
static UploadFailReason upload_fail_reason = UPLOAD_FAIL_NONE;
static uint8_t trace_clock_valid;
static uint32_t trace_clock_synced_ms;
static uint32_t trace_clock_epoch_seconds;
static char esp_rx_buffer[ESP8266_RX_BUFFER_SIZE];
static char esp_cmd_buffer[ESP8266_CMD_BUFFER_SIZE];
static char trace_time_buffer[21];
static char trace_batch_buffer[28];
static char trace_signature_buffer[65];
static char trace_canonical_buffer[TRACE_CANONICAL_BUFFER_SIZE];
static char trace_body_buffer[TRACE_BODY_BUFFER_SIZE];
static char trace_http_buffer[TRACE_HTTP_BUFFER_SIZE];
static const uint8_t trace_qr_bitmap[TRACE_QR_SIZE][6] = {
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x0F, 0xE2, 0xF7, 0x53, 0xF8, 0x00},
  {0x08, 0x2A, 0x78, 0x0A, 0x08, 0x00},
  {0x0B, 0xA0, 0xD0, 0xE2, 0xE8, 0x00},
  {0x0B, 0xAE, 0xB7, 0x22, 0xE8, 0x00},
  {0x0B, 0xA4, 0x19, 0x92, 0xE8, 0x00},
  {0x08, 0x2D, 0x86, 0xC2, 0x08, 0x00},
  {0x0F, 0xEA, 0xAA, 0xAB, 0xF8, 0x00},
  {0x00, 0x07, 0x2A, 0x48, 0x00, 0x00},
  {0x0F, 0xBD, 0x06, 0x2D, 0x50, 0x00},
  {0x06, 0x0A, 0xF1, 0xD2, 0x38, 0x00},
  {0x08, 0x7A, 0x72, 0xEB, 0xD0, 0x00},
  {0x0B, 0x98, 0xD2, 0xFA, 0xA0, 0x00},
  {0x04, 0x2E, 0xB6, 0x2D, 0xC0, 0x00},
  {0x0B, 0x98, 0x11, 0xF3, 0x18, 0x00},
  {0x06, 0xEF, 0x9E, 0x06, 0x10, 0x00},
  {0x04, 0x9B, 0x33, 0x71, 0xA0, 0x00},
  {0x04, 0x33, 0x1E, 0x9C, 0x90, 0x00},
  {0x06, 0xD8, 0xE1, 0x9E, 0x58, 0x00},
  {0x0E, 0xA4, 0x74, 0xA3, 0xD0, 0x00},
  {0x04, 0x0E, 0xD2, 0xE5, 0x20, 0x00},
  {0x0A, 0x2C, 0xBF, 0x2C, 0x90, 0x00},
  {0x0F, 0x9A, 0x01, 0x56, 0x58, 0x00},
  {0x08, 0x23, 0x92, 0x89, 0xD0, 0x00},
  {0x09, 0x5F, 0x32, 0x61, 0x60, 0x00},
  {0x08, 0x37, 0x1F, 0xAF, 0x88, 0x00},
  {0x00, 0x0E, 0xE1, 0x88, 0xA8, 0x00},
  {0x0F, 0xE8, 0x78, 0x5A, 0xD0, 0x00},
  {0x08, 0x22, 0xD9, 0x58, 0xE0, 0x00},
  {0x0B, 0xAE, 0xA6, 0xAF, 0x88, 0x00},
  {0x0B, 0xAA, 0x01, 0xC4, 0x98, 0x00},
  {0x0B, 0xAD, 0x92, 0x76, 0x20, 0x00},
  {0x08, 0x2F, 0x33, 0x62, 0x60, 0x00},
  {0x0F, 0xEB, 0x0E, 0xA8, 0x10, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
  {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
};

static QueueHandle_t ir_queue;
static SemaphoreHandle_t state_mutex;
static SemaphoreHandle_t oled_mutex;
static TaskHandle_t ui_task_handle;
static TaskHandle_t buzzer_task_handle;

static void SensorTask(void *argument);
static void UITask(void *argument);
static void IRTask(void *argument);
static void SelfTestTask(void *argument);
static void BuzzerTask(void *argument);
static void CommTask(void *argument);
static void esp8266_reset_module(void);
static uint8_t esp8266_probe(void);
static uint8_t esp8266_is_joined(void);
static uint8_t parse_http_date_time(char iso_time[21]);
static void trace_set_upload_fail_reason(UploadFailReason reason);
static void lock_state(void);
static void unlock_state(void);
static void request_ui_refresh(void);

static uint16_t micros_now(void)
{
  return (uint16_t)__HAL_TIM_GET_COUNTER(app_tim);
}

static uint16_t micros_elapsed(uint16_t start, uint16_t now)
{
  return (uint16_t)(now - start);
}

static void delay_us(uint16_t us)
{
  uint16_t start = micros_now();
  while (micros_elapsed(start, micros_now()) < us)
  {
  }
}

static uint8_t in_range_u16(uint16_t value, uint16_t min, uint16_t max)
{
  return (value >= min) && (value <= max);
}

static void one_wire_output_low(GPIO_TypeDef *port, uint16_t pin)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  HAL_GPIO_WritePin(port, pin, GPIO_PIN_RESET);
  GPIO_InitStruct.Pin = pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_OD;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(port, &GPIO_InitStruct);
}

static void one_wire_release(GPIO_TypeDef *port, uint16_t pin)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  GPIO_InitStruct.Pin = pin;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_PULLUP;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(port, &GPIO_InitStruct);
}

static uint8_t wait_pin_level(GPIO_TypeDef *port, uint16_t pin, GPIO_PinState level, uint16_t timeout_us)
{
  uint16_t start = micros_now();

  while (HAL_GPIO_ReadPin(port, pin) != level)
  {
    if (micros_elapsed(start, micros_now()) > timeout_us)
    {
      return 0U;
    }
  }

  return 1U;
}

static uint8_t dht11_read(DHT11_Data *out)
{
  uint8_t data[5] = {0};

  one_wire_output_low(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin);
  HAL_Delay(20U);
  one_wire_release(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin);
  delay_us(40U);

  if (!wait_pin_level(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin, GPIO_PIN_RESET, 100U) ||
      !wait_pin_level(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin, GPIO_PIN_SET, 100U) ||
      !wait_pin_level(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin, GPIO_PIN_RESET, 100U))
  {
    out->ok = 0U;
    return 0U;
  }

  for (uint8_t i = 0; i < 40U; ++i)
  {
    uint16_t high_start;
    uint16_t high_width;

    if (!wait_pin_level(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin, GPIO_PIN_SET, 80U))
    {
      out->ok = 0U;
      return 0U;
    }

    high_start = micros_now();
    if (!wait_pin_level(DHT11_DATA_GPIO_Port, DHT11_DATA_Pin, GPIO_PIN_RESET, 120U))
    {
      out->ok = 0U;
      return 0U;
    }

    high_width = micros_elapsed(high_start, micros_now());
    data[i / 8U] <<= 1U;
    if (high_width > 45U)
    {
      data[i / 8U] |= 1U;
    }
  }

  if ((uint8_t)(data[0] + data[1] + data[2] + data[3]) != data[4])
  {
    out->ok = 0U;
    return 0U;
  }

  out->hum_pct = data[0];
  out->temp_c = data[2];
  out->ok = 1U;
  return 1U;
}

static uint8_t ds18b20_reset(void)
{
  uint8_t present;

  one_wire_output_low(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
  delay_us(500U);
  one_wire_release(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
  delay_us(70U);
  present = (HAL_GPIO_ReadPin(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin) == GPIO_PIN_RESET);
  delay_us(430U);
  return present;
}

static void ds18b20_write_bit(uint8_t bit)
{
  one_wire_output_low(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
  if (bit != 0U)
  {
    delay_us(6U);
    one_wire_release(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
    delay_us(64U);
  }
  else
  {
    delay_us(60U);
    one_wire_release(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
    delay_us(10U);
  }
}

static uint8_t ds18b20_read_bit(void)
{
  uint8_t bit;

  one_wire_output_low(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
  delay_us(6U);
  one_wire_release(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin);
  delay_us(9U);
  bit = (HAL_GPIO_ReadPin(DS18B20_DATA_GPIO_Port, DS18B20_DATA_Pin) == GPIO_PIN_SET) ? 1U : 0U;
  delay_us(55U);
  return bit;
}

static void ds18b20_write_byte(uint8_t byte)
{
  for (uint8_t i = 0; i < 8U; ++i)
  {
    ds18b20_write_bit((uint8_t)(byte & 0x01U));
    byte >>= 1U;
  }
}

static uint8_t ds18b20_read_byte(void)
{
  uint8_t value = 0U;

  for (uint8_t i = 0; i < 8U; ++i)
  {
    value >>= 1U;
    if (ds18b20_read_bit() != 0U)
    {
      value |= 0x80U;
    }
  }

  return value;
}

static uint8_t ds18b20_start_conversion(void)
{
  if (!ds18b20_reset())
  {
    ds18b20.ok = 0U;
    ds18b20.converting = 0U;
    return 0U;
  }

  ds18b20_write_byte(0xCCU);
  ds18b20_write_byte(0x44U);
  ds18b20.convert_started_ms = HAL_GetTick();
  ds18b20.converting = 1U;
  return 1U;
}

static uint8_t ds18b20_finish_conversion(void)
{
  uint8_t lsb;
  uint8_t msb;
  int16_t raw;

  if (!ds18b20_reset())
  {
    ds18b20.ok = 0U;
    ds18b20.converting = 0U;
    return 0U;
  }

  ds18b20_write_byte(0xCCU);
  ds18b20_write_byte(0xBEU);
  lsb = ds18b20_read_byte();
  msb = ds18b20_read_byte();

  raw = (int16_t)(((uint16_t)msb << 8) | lsb);
  ds18b20.temp_centi = (int16_t)(((int32_t)raw * 100L) / 16L);
  ds18b20.ok = 1U;
  ds18b20.converting = 0U;
  return 1U;
}

static uint8_t w25q32_read_id(uint8_t id[3])
{
  uint8_t cmd = 0x9FU;
  uint8_t rx[3] = {0};

  HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, W25Q32_CS_Pin, GPIO_PIN_RESET);
  if (HAL_SPI_Transmit(app_spi, &cmd, 1U, 100U) != HAL_OK)
  {
    HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, W25Q32_CS_Pin, GPIO_PIN_SET);
    return 0U;
  }
  if (HAL_SPI_Receive(app_spi, rx, 3U, 100U) != HAL_OK)
  {
    HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, W25Q32_CS_Pin, GPIO_PIN_SET);
    return 0U;
  }
  HAL_GPIO_WritePin(W25Q32_CS_GPIO_Port, W25Q32_CS_Pin, GPIO_PIN_SET);

  id[0] = rx[0];
  id[1] = rx[1];
  id[2] = rx[2];
  return ((rx[0] != 0x00U) && (rx[0] != 0xFFU)) ? 1U : 0U;
}

static void esp8266_clear_uart_error(void)
{
  if (huart3.ErrorCode != HAL_UART_ERROR_NONE)
  {
    __HAL_UART_CLEAR_PEFLAG(&huart3);
    __HAL_UART_CLEAR_FEFLAG(&huart3);
    __HAL_UART_CLEAR_NEFLAG(&huart3);
    __HAL_UART_CLEAR_OREFLAG(&huart3);
    huart3.ErrorCode = HAL_UART_ERROR_NONE;
  }
}

static void esp8266_rx_clear(void)
{
  uint8_t ch;

  esp8266_clear_uart_error();
  while (HAL_UART_Receive(&huart3, &ch, 1U, 2U) == HAL_OK)
  {
  }
  esp8266_clear_uart_error();
}

static uint8_t esp8266_append_text(char *dst, uint16_t *pos, uint16_t size, const char *text)
{
  while (*text != '\0')
  {
    if (*pos + 1U >= size)
    {
      return 0U;
    }
    dst[*pos] = *text;
    ++(*pos);
    ++text;
  }
  dst[*pos] = '\0';
  return 1U;
}

static uint8_t esp8266_append_quoted(char *dst, uint16_t *pos, uint16_t size, const char *text)
{
  while (*text != '\0')
  {
    if ((*text == '"') || (*text == '\\'))
    {
      if (!esp8266_append_text(dst, pos, size, "\\"))
      {
        return 0U;
      }
    }
    if (*pos + 1U >= size)
    {
      return 0U;
    }
    dst[*pos] = *text;
    ++(*pos);
    ++text;
  }
  dst[*pos] = '\0';
  return 1U;
}

static uint8_t esp8266_build_join_cmd(void)
{
  uint16_t pos = 0U;

  esp_cmd_buffer[0] = '\0';
  if (!esp8266_append_text(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, "AT+CWJAP=\""))
  {
    return 0U;
  }
  if (!esp8266_append_quoted(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, ESP8266_WIFI_SSID))
  {
    return 0U;
  }
  if (!esp8266_append_text(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, "\",\""))
  {
    return 0U;
  }
  if (!esp8266_append_quoted(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, ESP8266_WIFI_PASS))
  {
    return 0U;
  }
  return esp8266_append_text(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, "\"\r\n");
}

static const char *esp8266_upload_link_type(void)
{
#if TRACE_UPLOAD_USE_SSL
  return "SSL";
#else
  return "TCP";
#endif
}

#if TRACE_UPLOAD_USE_SSL
static uint8_t esp8266_build_ssl_sni_cmd(void)
{
  uint16_t pos = 0U;

  esp_cmd_buffer[0] = '\0';
  if (!esp8266_append_text(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, "AT+CIPSSLCSNI=\""))
  {
    return 0U;
  }
  if (!esp8266_append_quoted(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, TRACE_UPLOAD_HOST))
  {
    return 0U;
  }
  return esp8266_append_text(esp_cmd_buffer, &pos, ESP8266_CMD_BUFFER_SIZE, "\"\r\n");
}
#endif

static void esp8266_capture_http_status(void)
{
  const char *cursor = strstr(esp_rx_buffer, "HTTP/1.");
  uint16_t status = 0U;
  uint8_t digits = 0U;

  if ((cursor == NULL) || (last_http_status != 0U))
  {
    return;
  }

  while ((*cursor != '\0') && (*cursor != ' '))
  {
    ++cursor;
  }
  while ((*cursor == ' ') || (*cursor == '\t'))
  {
    ++cursor;
  }
  while ((*cursor >= '0') && (*cursor <= '9') && (digits < 3U))
  {
    status = (uint16_t)(status * 10U + (uint16_t)(*cursor - '0'));
    ++cursor;
    ++digits;
  }
  if (digits == 3U)
  {
    last_http_status = status;
  }
}

static uint8_t esp8266_wait_for(const char *expect, uint32_t timeout_ms)
{
  uint8_t ch;
  uint16_t pos = 0U;
  uint32_t start = HAL_GetTick();

  esp_rx_buffer[0] = '\0';
  while ((uint32_t)(HAL_GetTick() - start) < timeout_ms)
  {
    HAL_StatusTypeDef status = HAL_UART_Receive(&huart3, &ch, 1U, 20U);
    if (status == HAL_OK)
    {
      if (pos + 1U < ESP8266_RX_BUFFER_SIZE)
      {
        esp_rx_buffer[pos] = (char)ch;
        ++pos;
        esp_rx_buffer[pos] = '\0';
      }
      else
      {
        memmove(esp_rx_buffer, &esp_rx_buffer[1], ESP8266_RX_BUFFER_SIZE - 2U);
        esp_rx_buffer[ESP8266_RX_BUFFER_SIZE - 2U] = (char)ch;
        esp_rx_buffer[ESP8266_RX_BUFFER_SIZE - 1U] = '\0';
      }

      if ((expect != NULL) && (strstr(esp_rx_buffer, expect) != NULL))
      {
        return 1U;
      }
      esp8266_capture_http_status();
      if ((strstr(esp_rx_buffer, "ERROR") != NULL) || (strstr(esp_rx_buffer, "FAIL") != NULL))
      {
        return 0U;
      }
    }
    else
    {
      esp8266_clear_uart_error();
      vTaskDelay(pdMS_TO_TICKS(1U));
    }
  }

  return 0U;
}

static uint8_t esp8266_send_cmd(const char *cmd, const char *expect, uint32_t timeout_ms)
{
  esp8266_rx_clear();
  if (HAL_UART_Transmit(&huart3, (uint8_t *)cmd, (uint16_t)strlen(cmd), 200U) != HAL_OK)
  {
    esp8266_clear_uart_error();
    return 0U;
  }
  return esp8266_wait_for(expect, timeout_ms);
}

static uint8_t esp8266_send_bytes_chunked(const char *data, uint16_t length)
{
  uint16_t sent = 0U;

  while (sent < length)
  {
    uint16_t chunk = (uint16_t)(length - sent);
    if (chunk > 64U)
    {
      chunk = 64U;
    }
    if (HAL_UART_Transmit(&huart3, (uint8_t *)&data[sent], chunk, 1000U) != HAL_OK)
    {
      esp8266_clear_uart_error();
      return 0U;
    }
    sent = (uint16_t)(sent + chunk);
    vTaskDelay(pdMS_TO_TICKS(2U));
  }

  return 1U;
}

static uint8_t esp8266_wait_at_ready(uint32_t timeout_ms)
{
  uint32_t start = HAL_GetTick();

  while ((uint32_t)(HAL_GetTick() - start) < timeout_ms)
  {
    if (esp8266_send_cmd("AT\r\n", "OK", 1500U))
    {
      return 1U;
    }
    vTaskDelay(pdMS_TO_TICKS(500U));
  }

  return 0U;
}

static uint8_t esp8266_probe_or_reset(void)
{
  if (esp8266_wait_at_ready(8000U))
  {
    esp_booted = 1U;
    return 1U;
  }

  esp_booted = 0U;
  esp8266_reset_module();
  if (esp8266_wait_at_ready(12000U))
  {
    esp_booted = 1U;
    return 1U;
  }

  return 0U;
}

static uint8_t esp8266_rx_status_code(uint8_t *status_code)
{
  const char *cursor = strstr(esp_rx_buffer, "STATUS:");

  if ((cursor == NULL) || (cursor[7] < '0') || (cursor[7] > '9'))
  {
    return 0U;
  }

  *status_code = (uint8_t)(cursor[7] - '0');
  return 1U;
}

static uint8_t esp8266_wait_wifi_joined(uint32_t timeout_ms)
{
  uint32_t start = HAL_GetTick();

  while ((uint32_t)(HAL_GetTick() - start) < timeout_ms)
  {
    if (esp8266_is_joined())
    {
      if (esp8266_send_cmd("AT+CIFSR\r\n", "OK", 5000U))
      {
        return 1U;
      }
      return 1U;
    }
    vTaskDelay(pdMS_TO_TICKS(1000U));
  }

  return 0U;
}

static uint8_t esp8266_close_link_until_idle(void)
{
  uint8_t status_code = 0U;

  for (uint8_t i = 0U; i < 5U; ++i)
  {
    if (esp8266_send_cmd("AT+CIPSTATUS\r\n", "OK", 2500U) &&
        esp8266_rx_status_code(&status_code))
    {
      if (status_code != 3U)
      {
        return 1U;
      }
    }

    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 3000U);
    vTaskDelay(pdMS_TO_TICKS(700U));
  }

  return 0U;
}

static uint8_t esp8266_set_single_connection_mode(void)
{
  for (uint8_t i = 0U; i < 6U; ++i)
  {
    (void)esp8266_wait_at_ready(2500U);
    (void)esp8266_close_link_until_idle();

    if (esp8266_send_cmd("AT+CIPMUX=0\r\n", "OK", 5000U))
    {
      (void)esp8266_send_cmd("AT+CIPMODE=0\r\n", "OK", 2000U);
      return 1U;
    }

    vTaskDelay(pdMS_TO_TICKS(1000U + ((uint32_t)i * 500UL)));
  }

  return 0U;
}

static uint8_t esp8266_prepare_single_connection(void)
{
  if (!esp8266_probe_or_reset())
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_AT);
    return 0U;
  }

  if (!esp8266_send_cmd("ATE0\r\n", "OK", 2000U))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_AT);
    return 0U;
  }
  if (!esp8266_send_cmd("AT+CWMODE=1\r\n", "OK", 3000U))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_AT);
    return 0U;
  }

  if (!esp8266_wait_wifi_joined(12000U))
  {
    if (!esp8266_build_join_cmd())
    {
      trace_set_upload_fail_reason(UPLOAD_FAIL_WIFI);
      return 0U;
    }
    if (!esp8266_send_cmd(esp_cmd_buffer, "OK", 30000U))
    {
      trace_set_upload_fail_reason(UPLOAD_FAIL_WIFI);
      return 0U;
    }
    if (!esp8266_wait_wifi_joined(15000U))
    {
      trace_set_upload_fail_reason(UPLOAD_FAIL_WIFI);
      return 0U;
    }
  }

  vTaskDelay(pdMS_TO_TICKS(ESP8266_POST_JOIN_SETTLE_MS));
  if (esp8266_set_single_connection_mode())
  {
    return 1U;
  }
  trace_set_upload_fail_reason(UPLOAD_FAIL_MUX);

  esp_booted = 0U;
  esp8266_reset_module();
  if (!esp8266_wait_at_ready(12000U))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_AT);
    return 0U;
  }
  esp_booted = 1U;
  (void)esp8266_send_cmd("ATE0\r\n", "OK", 2000U);
  (void)esp8266_send_cmd("AT+CWMODE=1\r\n", "OK", 3000U);
  if (!esp8266_build_join_cmd() ||
      !esp8266_send_cmd(esp_cmd_buffer, "OK", 30000U) ||
      !esp8266_wait_wifi_joined(15000U))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_WIFI);
    return 0U;
  }

  vTaskDelay(pdMS_TO_TICKS(ESP8266_POST_JOIN_SETTLE_MS));
  if (!esp8266_set_single_connection_mode())
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_MUX);
    return 0U;
  }

  return 1U;
}

static void esp8266_set_state(WifiState state, uint8_t seen, uint8_t joined)
{
  lock_state();
  wifi_state = state;
  board.wifi_seen = seen;
  board.wifi_joined = joined;
  unlock_state();
  request_ui_refresh();
}

static void esp8266_reset_module(void)
{
  HAL_GPIO_WritePin(ESP8266_EN_GPIO_Port, ESP8266_EN_Pin, GPIO_PIN_SET);
  HAL_GPIO_WritePin(ESP8266_RST_GPIO_Port, ESP8266_RST_Pin, GPIO_PIN_RESET);
  vTaskDelay(pdMS_TO_TICKS(200U));
  HAL_GPIO_WritePin(ESP8266_RST_GPIO_Port, ESP8266_RST_Pin, GPIO_PIN_SET);
  vTaskDelay(pdMS_TO_TICKS(2000U));
  esp8266_rx_clear();
}

static uint8_t esp8266_probe(void)
{
  return esp8266_send_cmd("AT\r\n", "OK", 800U);
}

static uint8_t esp8266_is_joined(void)
{
  if (!esp8266_send_cmd("AT+CWJAP?\r\n", "OK", 4000U))
  {
    return 0U;
  }
  if (strstr(esp_rx_buffer, "+CWJAP:") == NULL)
  {
    return 0U;
  }
  if (strstr(esp_rx_buffer, ESP8266_WIFI_SSID) == NULL)
  {
    return 0U;
  }
  return 1U;
}

static void esp8266_connect_wifi(void)
{
  if (ESP8266_WIFI_SSID[0] == '\0')
  {
    esp8266_set_state(WIFI_STATE_NO_SSID, esp8266_probe(), 0U);
    return;
  }

  esp8266_set_state(WIFI_STATE_JOINING, 0U, 0U);
  if (esp_booted == 0U)
  {
    esp8266_reset_module();
    esp_booted = 1U;
  }

  if (!esp8266_probe())
  {
    esp8266_reset_module();
    if (!esp8266_probe())
    {
      esp8266_set_state(WIFI_STATE_AT_FAIL, 0U, 0U);
      esp_booted = 0U;
      return;
    }
  }

  esp8266_set_state(WIFI_STATE_JOINING, 1U, 0U);
  if (!esp8266_send_cmd("ATE0\r\n", "OK", 1000U))
  {
    esp8266_set_state(WIFI_STATE_AT_FAIL, 1U, 0U);
    return;
  }
  if (!esp8266_send_cmd("AT+CWMODE=1\r\n", "OK", 2000U))
  {
    esp8266_set_state(WIFI_STATE_FAIL, 1U, 0U);
    return;
  }
  (void)esp8266_send_cmd("AT+CWAUTOCONN=1\r\n", "OK", 1000U);
  if (!esp8266_build_join_cmd())
  {
    esp8266_set_state(WIFI_STATE_FAIL, 1U, 0U);
    return;
  }
  if (!esp8266_send_cmd(esp_cmd_buffer, "OK", 20000U))
  {
    esp8266_set_state(WIFI_STATE_FAIL, 1U, 0U);
    return;
  }
  if (!esp8266_send_cmd("AT+CIFSR\r\n", "OK", 3000U))
  {
    esp8266_set_state(WIFI_STATE_FAIL, 1U, 0U);
    return;
  }

  wifi_ready_miss_count = 0U;
  esp8266_set_state(WIFI_STATE_READY, 1U, 1U);
}

static void esp8266_check_wifi(void)
{
  if (esp8266_is_joined())
  {
    wifi_ready_miss_count = 0U;
    esp8266_set_state(WIFI_STATE_READY, 1U, 1U);
    return;
  }

  if (wifi_ready_miss_count < 255U)
  {
    ++wifi_ready_miss_count;
  }

  if (wifi_ready_miss_count < ESP8266_READY_MISS_LIMIT)
  {
    esp8266_set_state(WIFI_STATE_READY, 1U, 1U);
    return;
  }

  if (esp8266_probe())
  {
    esp8266_set_state(WIFI_STATE_FAIL, 1U, 0U);
    return;
  }

  esp8266_set_state(WIFI_STATE_AT_FAIL, 0U, 0U);
  esp_booted = 0U;
}

static void trace_set_upload_state(UploadState state, uint16_t http_status)
{
  lock_state();
  upload_state = state;
  last_http_status = http_status;
  unlock_state();
  request_ui_refresh();
}

static void trace_set_upload_fail_reason(UploadFailReason reason)
{
  lock_state();
  upload_fail_reason = reason;
  unlock_state();
}

static const char *upload_fail_reason_text(void)
{
  switch (upload_fail_reason)
  {
    case UPLOAD_FAIL_MUX:
      return "MUX";
    case UPLOAD_FAIL_AT:
      return "AT";
    case UPLOAD_FAIL_WIFI:
      return "WIFI";
    case UPLOAD_FAIL_START:
      return "START";
    case UPLOAD_FAIL_BUILD:
      return "BUILD";
    case UPLOAD_FAIL_PROMPT:
      return "PROMPT";
    case UPLOAD_FAIL_SEND:
      return "SEND";
    case UPLOAD_FAIL_SEND_OK:
      return "SENDOK";
    case UPLOAD_FAIL_RESP:
      return "RESP";
    case UPLOAD_FAIL_BUSY:
      return "BUSY";
    case UPLOAD_FAIL_CLOSED:
      return "CLOSED";
    case UPLOAD_FAIL_ERROR:
      return "ERROR";
    case UPLOAD_FAIL_NOLINK:
      return "NOLINK";
    case UPLOAD_FAIL_DNS:
      return "DNS";
    case UPLOAD_FAIL_STAT:
      return "STAT";
    default:
      return "";
  }
}

static UploadFailReason esp8266_classify_link_fail(void)
{
  if ((strstr(esp_rx_buffer, "DNS") != NULL) ||
      (strstr(esp_rx_buffer, "dns") != NULL))
  {
    return UPLOAD_FAIL_DNS;
  }
  if ((strstr(esp_rx_buffer, "link is not valid") != NULL) ||
      (strstr(esp_rx_buffer, "UNLINK") != NULL))
  {
    return UPLOAD_FAIL_NOLINK;
  }
  if ((strstr(esp_rx_buffer, "busy") != NULL) ||
      (strstr(esp_rx_buffer, "BUSY") != NULL))
  {
    return UPLOAD_FAIL_BUSY;
  }
  if (strstr(esp_rx_buffer, "CLOSED") != NULL)
  {
    return UPLOAD_FAIL_CLOSED;
  }
  if (strstr(esp_rx_buffer, "ERROR") != NULL)
  {
    return UPLOAD_FAIL_ERROR;
  }
  return UPLOAD_FAIL_START;
}

static UploadFailReason esp8266_classify_cipsend_prompt_fail(void)
{
  if ((strstr(esp_rx_buffer, "link is not valid") != NULL) ||
      (strstr(esp_rx_buffer, "UNLINK") != NULL))
  {
    return UPLOAD_FAIL_NOLINK;
  }
  if ((strstr(esp_rx_buffer, "busy") != NULL) ||
      (strstr(esp_rx_buffer, "BUSY") != NULL))
  {
    return UPLOAD_FAIL_BUSY;
  }
  if (strstr(esp_rx_buffer, "CLOSED") != NULL)
  {
    return UPLOAD_FAIL_CLOSED;
  }
  if (strstr(esp_rx_buffer, "ERROR") != NULL)
  {
    return UPLOAD_FAIL_ERROR;
  }
  return UPLOAD_FAIL_PROMPT;
}

static uint8_t esp8266_wait_link_connected(uint32_t timeout_ms)
{
  uint32_t start = HAL_GetTick();

  while ((uint32_t)(HAL_GetTick() - start) < timeout_ms)
  {
    if (esp8266_send_cmd("AT+CIPSTATUS\r\n", "OK", 2000U))
    {
      if (strstr(esp_rx_buffer, "STATUS:3") != NULL)
      {
        return 1U;
      }
      if ((strstr(esp_rx_buffer, "STATUS:4") != NULL) ||
          (strstr(esp_rx_buffer, "link is not valid") != NULL))
      {
        return 0U;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(500U));
  }

  return 0U;
}

static uint8_t esp8266_http_get_server_time(char iso_time[21])
{
  int request_len;

  last_http_status = 0U;
  if (!esp8266_prepare_single_connection())
  {
    return 0U;
  }

  request_len = snprintf(esp_cmd_buffer, ESP8266_CMD_BUFFER_SIZE,
                         "AT+CIPSTART=\"TCP\",\"%s\",%u\r\n",
                         TRACE_UPLOAD_HOST, (unsigned int)TRACE_UPLOAD_PORT);
  if ((request_len < 0) || (request_len >= (int)ESP8266_CMD_BUFFER_SIZE))
  {
    return 0U;
  }
  if (!esp8266_send_cmd(esp_cmd_buffer, "CONNECT", 20000U))
  {
    return 0U;
  }
  if (!esp8266_wait_link_connected(12000U))
  {
    return 0U;
  }

  request_len = snprintf(
      trace_http_buffer,
      TRACE_HTTP_BUFFER_SIZE,
      "HEAD /health HTTP/1.1\r\n"
      "Host: %s\r\n"
      "User-Agent: stm32f103-esp8266/1.0\r\n"
      "Connection: close\r\n"
      "\r\n",
      TRACE_UPLOAD_HOST);
  if ((request_len < 0) || (request_len >= (int)TRACE_HTTP_BUFFER_SIZE))
  {
    return 0U;
  }

  snprintf(esp_cmd_buffer, ESP8266_CMD_BUFFER_SIZE, "AT+CIPSEND=%d\r\n", request_len);
  esp8266_rx_clear();
  if (HAL_UART_Transmit(&huart3, (uint8_t *)esp_cmd_buffer, (uint16_t)strlen(esp_cmd_buffer), 200U) != HAL_OK)
  {
    esp8266_clear_uart_error();
    return 0U;
  }
  if (!esp8266_wait_for(">", 8000U))
  {
    return 0U;
  }
  if (!esp8266_send_bytes_chunked(trace_http_buffer, (uint16_t)request_len))
  {
    return 0U;
  }
  (void)esp8266_wait_for("CLOSED", 12000U);

  if (parse_http_date_time(iso_time))
  {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return 1U;
  }

  return 0U;
}

static const char *json_bool(uint8_t value)
{
  return value ? "true" : "false";
}

static int16_t trace_temperature_centi(const TraceSnapshot *snapshot)
{
  if (snapshot->ds18b20_ok)
  {
    return snapshot->ds18b20_temp_centi;
  }
  if (snapshot->dht_ok)
  {
    return (int16_t)snapshot->dht_temp * 100;
  }
  return 400;
}

static uint8_t trace_humidity_pct(const TraceSnapshot *snapshot)
{
  return snapshot->dht_ok ? snapshot->dht_hum : 75U;
}

static uint32_t trace_co2_ppm(const TraceSnapshot *snapshot)
{
  uint32_t co2 = 100000UL;
  if (snapshot->w25_ok)
  {
    co2 += 800UL;
  }
  if (snapshot->at24_ok)
  {
    co2 += 600UL;
  }
  return co2;
}

static uint16_t trace_vibration_milli_g(const TraceSnapshot *snapshot)
{
  uint16_t value = 20U;
  if (!snapshot->ds18b20_ok)
  {
    value = (uint16_t)(value + 30U);
  }
  if (!snapshot->dht_ok)
  {
    value = (uint16_t)(value + 40U);
  }
  return value;
}

static void trace_decimal_centi(char *buffer, uint8_t size, int16_t centi)
{
  int16_t whole = centi / 100;
  int16_t frac = centi % 100;
  const char *sign = "";

  if (frac < 0)
  {
    frac = (int16_t)-frac;
  }
  if ((centi < 0) && (whole == 0))
  {
    sign = "-";
  }

  if (frac == 0)
  {
    (void)snprintf(buffer, size, "%s%d.0", sign, whole);
  }
  else if ((frac % 10) == 0)
  {
    (void)snprintf(buffer, size, "%s%d.%u", sign, whole, (unsigned int)(frac / 10));
  }
  else
  {
    (void)snprintf(buffer, size, "%s%d.%02u", sign, whole, (unsigned int)frac);
  }
}

static void trace_decimal_milli(char *buffer, uint8_t size, uint16_t milli)
{
  uint16_t whole = (uint16_t)(milli / 1000U);
  uint16_t frac = (uint16_t)(milli % 1000U);

  if (frac == 0U)
  {
    (void)snprintf(buffer, size, "%u.0", (unsigned int)whole);
  }
  else if ((frac % 100U) == 0U)
  {
    (void)snprintf(buffer, size, "%u.%u",
                   (unsigned int)whole,
                   (unsigned int)(frac / 100U));
  }
  else if ((frac % 10U) == 0U)
  {
    (void)snprintf(buffer, size, "%u.%02u",
                   (unsigned int)whole,
                   (unsigned int)(frac / 10U));
  }
  else
  {
    (void)snprintf(buffer, size, "%u.%03u",
                   (unsigned int)whole,
                   (unsigned int)frac);
  }
}

static void trace_snapshot(TraceSnapshot *snapshot)
{
  lock_state();
  snapshot->sample = sample_id;
  snapshot->dht_temp = dht.temp_c;
  snapshot->dht_hum = dht.hum_pct;
  snapshot->dht_ok = dht.ok;
  snapshot->ds18b20_temp_centi = ds18b20.temp_centi;
  snapshot->ds18b20_ok = ds18b20.ok;
  snapshot->quality = quality_score;
  snapshot->w25_ok = board.w25_ok;
  snapshot->at24_ok = board.at24_ok;
  snapshot->wifi_joined = board.wifi_joined;
  unlock_state();
}

static uint8_t parse_uint_token(const char **cursor, uint16_t *out)
{
  uint16_t value = 0U;
  uint8_t digits = 0U;

  while ((**cursor >= '0') && (**cursor <= '9'))
  {
    value = (uint16_t)(value * 10U + (uint16_t)(**cursor - '0'));
    ++(*cursor);
    ++digits;
  }
  *out = value;
  return (digits != 0U) ? 1U : 0U;
}

static void skip_spaces(const char **cursor)
{
  while ((**cursor == ' ') || (**cursor == '\t'))
  {
    ++(*cursor);
  }
}

static uint8_t month_number(const char *month)
{
  static const char months[] = "JanFebMarAprMayJunJulAugSepOctNovDec";

  for (uint8_t i = 0U; i < 12U; ++i)
  {
    const char *candidate = &months[i * 3U];
    if ((month[0] == candidate[0]) && (month[1] == candidate[1]) && (month[2] == candidate[2]))
    {
      return (uint8_t)(i + 1U);
    }
  }
  return 0U;
}

static uint8_t days_in_month(uint16_t year, uint8_t month)
{
  static const uint8_t days[] = {31U, 28U, 31U, 30U, 31U, 30U, 31U, 31U, 30U, 31U, 30U, 31U};
  if ((month == 2U) && (((year % 4U) == 0U) && (((year % 100U) != 0U) || ((year % 400U) == 0U))))
  {
    return 29U;
  }
  return days[month - 1U];
}

static uint32_t date_to_epoch_seconds(uint16_t year, uint8_t month, uint8_t day,
                                      uint8_t hour, uint8_t minute, uint8_t second)
{
  uint32_t days = 0UL;

  for (uint16_t y = 1970U; y < year; ++y)
  {
    days += (uint32_t)((((y % 4U) == 0U) && (((y % 100U) != 0U) || ((y % 400U) == 0U))) ? 366U : 365U);
  }
  for (uint8_t m = 1U; m < month; ++m)
  {
    days += days_in_month(year, m);
  }
  days += (uint32_t)(day - 1U);

  return (((days * 24UL) + hour) * 60UL + minute) * 60UL + second;
}

static void epoch_seconds_to_iso(uint32_t epoch_seconds, char iso_time[21])
{
  uint32_t days = epoch_seconds / 86400UL;
  uint32_t day_seconds = epoch_seconds % 86400UL;
  uint16_t year = 1970U;
  uint8_t month = 1U;
  uint8_t day;
  uint16_t hour;
  uint16_t minute;
  uint16_t second;

  for (;;)
  {
    uint16_t year_days = (uint16_t)((((year % 4U) == 0U) && (((year % 100U) != 0U) || ((year % 400U) == 0U))) ? 366U : 365U);
    if (days < year_days)
    {
      break;
    }
    days -= year_days;
    ++year;
  }

  while (days >= days_in_month(year, month))
  {
    days -= days_in_month(year, month);
    ++month;
  }
  day = (uint8_t)(days + 1UL);
  hour = (uint16_t)(day_seconds / 3600UL);
  minute = (uint16_t)((day_seconds / 60UL) % 60UL);
  second = (uint16_t)(day_seconds % 60UL);

  iso_time[0] = (char)('0' + ((year / 1000U) % 10U));
  iso_time[1] = (char)('0' + ((year / 100U) % 10U));
  iso_time[2] = (char)('0' + ((year / 10U) % 10U));
  iso_time[3] = (char)('0' + (year % 10U));
  iso_time[4] = '-';
  iso_time[5] = (char)('0' + (month / 10U));
  iso_time[6] = (char)('0' + (month % 10U));
  iso_time[7] = '-';
  iso_time[8] = (char)('0' + (day / 10U));
  iso_time[9] = (char)('0' + (day % 10U));
  iso_time[10] = 'T';
  iso_time[11] = (char)('0' + (hour / 10U));
  iso_time[12] = (char)('0' + (hour % 10U));
  iso_time[13] = ':';
  iso_time[14] = (char)('0' + (minute / 10U));
  iso_time[15] = (char)('0' + (minute % 10U));
  iso_time[16] = ':';
  iso_time[17] = (char)('0' + (second / 10U));
  iso_time[18] = (char)('0' + (second % 10U));
  iso_time[19] = 'Z';
  iso_time[20] = '\0';
}

static uint8_t iso_to_epoch_seconds(const char *iso_time, uint32_t *epoch_seconds)
{
  uint16_t year;
  uint16_t month;
  uint16_t day;
  uint16_t hour;
  uint16_t minute;
  uint16_t second;
  const char *cursor = iso_time;

  if (!parse_uint_token(&cursor, &year) || (*cursor != '-'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &month) || (*cursor != '-'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &day) || (*cursor != 'T'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &hour) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &minute) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &second))
  {
    return 0U;
  }
  if ((year < 2026U) || (month == 0U) || (month > 12U) || (day == 0U) ||
      (day > days_in_month(year, (uint8_t)month)) || (hour > 23U) ||
      (minute > 59U) || (second > 59U))
  {
    return 0U;
  }

  *epoch_seconds = date_to_epoch_seconds(year, (uint8_t)month, (uint8_t)day,
                                         (uint8_t)hour, (uint8_t)minute, (uint8_t)second);
  return 1U;
}

static void trace_clock_set_from_iso(const char *iso_time)
{
  uint32_t epoch_seconds;
  if (iso_to_epoch_seconds(iso_time, &epoch_seconds))
  {
    trace_clock_epoch_seconds = epoch_seconds;
    trace_clock_synced_ms = HAL_GetTick();
    trace_clock_valid = 1U;
  }
}

static uint8_t trace_clock_now(char iso_time[21])
{
  uint32_t elapsed_seconds;

  if (!trace_clock_valid)
  {
    return 0U;
  }

  elapsed_seconds = (uint32_t)(HAL_GetTick() - trace_clock_synced_ms) / 1000UL;
  epoch_seconds_to_iso(trace_clock_epoch_seconds + elapsed_seconds, iso_time);
  return 1U;
}

static uint8_t parse_sntp_time(char iso_time[21])
{
  const char *cursor = strstr(esp_rx_buffer, "+CIPSNTPTIME:");
  char month_text[3];
  uint16_t day;
  uint16_t hour;
  uint16_t minute;
  uint16_t second;
  uint16_t year;
  uint8_t month;
  int written;

  if (cursor == NULL)
  {
    return 0U;
  }
  cursor += 13;
  skip_spaces(&cursor);

  while ((*cursor != '\0') && (*cursor != ' '))
  {
    ++cursor;
  }
  skip_spaces(&cursor);
  if ((cursor[0] == '\0') || (cursor[1] == '\0') || (cursor[2] == '\0'))
  {
    return 0U;
  }
  month_text[0] = cursor[0];
  month_text[1] = cursor[1];
  month_text[2] = cursor[2];
  month = month_number(month_text);
  if (month == 0U)
  {
    return 0U;
  }
  cursor += 3;
  skip_spaces(&cursor);
  if (!parse_uint_token(&cursor, &day))
  {
    return 0U;
  }
  skip_spaces(&cursor);
  if (!parse_uint_token(&cursor, &hour) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &minute) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &second))
  {
    return 0U;
  }
  skip_spaces(&cursor);
  if (!parse_uint_token(&cursor, &year))
  {
    return 0U;
  }
  if ((year < 2026U) || (day == 0U) || (day > 31U) || (hour > 23U) || (minute > 59U) || (second > 59U))
  {
    return 0U;
  }

  written = snprintf(iso_time, 21U, "%04u-%02u-%02uT%02u:%02u:%02uZ",
                     year, month, day, hour, minute, second);
  return (written == 20) ? 1U : 0U;
}

static uint8_t parse_http_date_time(char iso_time[21])
{
  const char *cursor = strstr(esp_rx_buffer, "\r\nDate:");
  uint8_t line_prefix_len = 7U;
  char month_text[3];
  uint16_t day;
  uint16_t hour;
  uint16_t minute;
  uint16_t second;
  uint16_t year;
  uint8_t month;
  int written;

  if (cursor == NULL)
  {
    cursor = strstr(esp_rx_buffer, "\nDate:");
    line_prefix_len = 6U;
  }
  if (cursor == NULL)
  {
    cursor = strstr(esp_rx_buffer, "\r\ndate:");
    line_prefix_len = 7U;
  }
  if (cursor == NULL)
  {
    cursor = strstr(esp_rx_buffer, "\ndate:");
    line_prefix_len = 6U;
  }
  if (cursor == NULL)
  {
    return 0U;
  }
  cursor += line_prefix_len;
  skip_spaces(&cursor);

  while ((*cursor != '\0') && (*cursor != ','))
  {
    ++cursor;
  }
  if (*cursor != ',')
  {
    return 0U;
  }
  ++cursor;
  skip_spaces(&cursor);

  if (!parse_uint_token(&cursor, &day))
  {
    return 0U;
  }
  skip_spaces(&cursor);
  if ((cursor[0] == '\0') || (cursor[1] == '\0') || (cursor[2] == '\0'))
  {
    return 0U;
  }
  month_text[0] = cursor[0];
  month_text[1] = cursor[1];
  month_text[2] = cursor[2];
  month = month_number(month_text);
  if (month == 0U)
  {
    return 0U;
  }
  cursor += 3;
  skip_spaces(&cursor);
  if (!parse_uint_token(&cursor, &year))
  {
    return 0U;
  }
  skip_spaces(&cursor);
  if (!parse_uint_token(&cursor, &hour) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &minute) || (*cursor != ':'))
  {
    return 0U;
  }
  ++cursor;
  if (!parse_uint_token(&cursor, &second))
  {
    return 0U;
  }
  if ((year < 2026U) || (day == 0U) || (day > 31U) || (hour > 23U) || (minute > 59U) || (second > 59U))
  {
    return 0U;
  }

  written = snprintf(iso_time, 21U, "%04u-%02u-%02uT%02u:%02u:%02uZ",
                     year, month, day, hour, minute, second);
  return (written == 20) ? 1U : 0U;
}

static uint8_t esp8266_get_network_time(char iso_time[21])
{
  (void)esp8266_send_cmd("AT+CIPSNTPCFG=1,0,\"cn.pool.ntp.org\",\"ntp.aliyun.com\",\"ntp.tencent.com\"\r\n", "OK", 3000U);

  for (uint8_t i = 0U; i < 5U; ++i)
  {
    if (esp8266_send_cmd("AT+CIPSNTPTIME?\r\n", "OK", 4000U) && parse_sntp_time(iso_time))
    {
      return 1U;
    }
    vTaskDelay(pdMS_TO_TICKS(1000U));
  }
  return 0U;
}

static uint8_t trace_build_fallback_time(char iso_time[21])
{
  uint32_t uptime_seconds = HAL_GetTick() / 1000UL;
  uint32_t day_seconds = uptime_seconds % 86400UL;
  uint32_t hour = ((uint32_t)TRACE_FALLBACK_START_HOUR_UTC + (day_seconds / 3600UL)) % 24UL;
  uint32_t minute = (day_seconds / 60UL) % 60UL;
  uint32_t second = day_seconds % 60UL;
  int written = snprintf(iso_time, 21U, "%sT%02lu:%02lu:%02luZ",
                         TRACE_FALLBACK_DATE,
                         (unsigned long)hour,
                         (unsigned long)minute,
                         (unsigned long)second);
  return (written == 20) ? 1U : 0U;
}

static uint8_t trace_sync_clock_if_needed(char iso_time[21])
{
  uint8_t need_sync = (trace_clock_valid == 0U);

  if (!need_sync)
  {
    uint32_t age_ms = (uint32_t)(HAL_GetTick() - trace_clock_synced_ms);
    need_sync = (age_ms >= 3600000UL) ? 1U : 0U;
  }

  if (!need_sync && trace_clock_now(iso_time))
  {
    return 1U;
  }

  if (esp8266_get_network_time(iso_time) || esp8266_http_get_server_time(iso_time))
  {
    trace_clock_set_from_iso(iso_time);
    return 1U;
  }

  return trace_clock_now(iso_time);
}

static uint8_t trace_build_batch_id(const char *iso_time, char *batch_id, uint8_t size)
{
  if ((iso_time[0] == '\0') || (iso_time[4] != '-') || (iso_time[7] != '-'))
  {
    return 0U;
  }

  int written = snprintf(batch_id, size, "%s-%.4s%.2s%.2s-001",
                         TRACE_BATCH_PREFIX,
                         iso_time,
                         &iso_time[5],
                         &iso_time[8]);
  return ((written > 0) && (written < (int)size)) ? 1U : 0U;
}

static uint8_t trace_build_payload(const TraceSnapshot *snapshot, const char *iso_time)
{
  int written;
  int16_t temp_centi = trace_temperature_centi(snapshot);
  uint8_t hum_pct = trace_humidity_pct(snapshot);
  uint32_t co2_ppm = trace_co2_ppm(snapshot);
  uint16_t vibration_milli_g = trace_vibration_milli_g(snapshot);
  char temp_text[10];
  char vibration_text[10];

  trace_decimal_centi(temp_text, (uint8_t)sizeof(temp_text), temp_centi);
  trace_decimal_milli(vibration_text, (uint8_t)sizeof(vibration_text), vibration_milli_g);
  if (!trace_build_batch_id(iso_time, trace_batch_buffer, (uint8_t)sizeof(trace_batch_buffer)))
  {
    return 0U;
  }

  written = snprintf(
      trace_canonical_buffer,
      TRACE_CANONICAL_BUFFER_SIZE,
      "{\"batch_id\":\"%s\",\"device_id\":\"%s\",\"sensor_payload\":"
      "{\"at24_ok\":%s,\"co2_ppm\":%lu,\"dht_ok\":%s,\"ds18b20_ok\":%s,"
      "\"humidity_pct\":%u,\"quality_score\":%u,\"sample_id\":%u,"
      "\"source\":\"stm32f103c8t6_lite\",\"supply_chain_stage\":\"%s\","
      "\"temperature_c\":%s,\"vibration_g\":%s,\"w25_ok\":%s,\"wifi_joined\":%s},"
      "\"signature_envelope\":{\"algorithm\":\"HMAC_SHA256\",\"key_id\":\"%s\"},"
      "\"timestamp\":\"%s\",\"version\":\"1.0.0\"}",
      trace_batch_buffer,
      TRACE_DEVICE_ID_JSON,
      json_bool(snapshot->at24_ok),
      (unsigned long)co2_ppm,
      json_bool(snapshot->dht_ok),
      json_bool(snapshot->ds18b20_ok),
      hum_pct,
      snapshot->quality,
      snapshot->sample,
      TRACE_SUPPLY_CHAIN_STAGE,
      temp_text,
      vibration_text,
      json_bool(snapshot->w25_ok),
      json_bool(snapshot->wifi_joined),
      TRACE_DEVICE_KEY_ID,
      iso_time);
  if ((written < 0) || (written >= (int)TRACE_CANONICAL_BUFFER_SIZE))
  {
    return 0U;
  }

  hmac_sha256_hex((const uint8_t *)TRACE_DEVICE_SECRET, strlen(TRACE_DEVICE_SECRET),
                  (const uint8_t *)trace_canonical_buffer, strlen(trace_canonical_buffer),
                  trace_signature_buffer);

  written = snprintf(
      trace_body_buffer,
      TRACE_BODY_BUFFER_SIZE,
      "{\"version\":\"1.0.0\",\"device_id\":\"%s\",\"batch_id\":\"%s\","
      "\"timestamp\":\"%s\",\"sensor_payload\":"
      "{\"temperature_c\":%s,\"humidity_pct\":%u,\"co2_ppm\":%lu,\"vibration_g\":%s,"
      "\"supply_chain_stage\":\"%s\",\"quality_score\":%u,\"sample_id\":%u,"
      "\"source\":\"stm32f103c8t6_lite\",\"dht_ok\":%s,\"ds18b20_ok\":%s,"
      "\"w25_ok\":%s,\"at24_ok\":%s,\"wifi_joined\":%s},"
      "\"supply_chain_stage\":\"%s\",\"co2_ppm\":%lu,\"vibration_g\":%s,"
      "\"signature_envelope\":{\"algorithm\":\"HMAC_SHA256\",\"signature\":\"%s\","
      "\"key_id\":\"%s\"}}",
      TRACE_DEVICE_ID_JSON,
      trace_batch_buffer,
      iso_time,
      temp_text,
      hum_pct,
      (unsigned long)co2_ppm,
      vibration_text,
      TRACE_SUPPLY_CHAIN_STAGE,
      snapshot->quality,
      snapshot->sample,
      json_bool(snapshot->dht_ok),
      json_bool(snapshot->ds18b20_ok),
      json_bool(snapshot->w25_ok),
      json_bool(snapshot->at24_ok),
      json_bool(snapshot->wifi_joined),
      TRACE_SUPPLY_CHAIN_STAGE,
      (unsigned long)co2_ppm,
      vibration_text,
      trace_signature_buffer,
      TRACE_DEVICE_KEY_ID);

  return ((written >= 0) && (written < (int)TRACE_BODY_BUFFER_SIZE)) ? 1U : 0U;
}

static uint16_t parse_http_status(void)
{
  const char *cursor = strstr(esp_rx_buffer, "HTTP/1.");
  uint16_t status = 0U;

  if (cursor == NULL)
  {
    return 0U;
  }
  while ((*cursor != '\0') && (*cursor != ' '))
  {
    ++cursor;
  }
  skip_spaces(&cursor);
  (void)parse_uint_token(&cursor, &status);
  return status;
}

static uint8_t esp8266_http_post_event(void)
{
  int body_len = (int)strlen(trace_body_buffer);
  int request_len;
  uint16_t parsed_status;

  last_http_status = 0U;
  trace_set_upload_fail_reason(UPLOAD_FAIL_NONE);
  if (!esp8266_prepare_single_connection())
  {
    if (upload_fail_reason == UPLOAD_FAIL_NONE)
    {
      trace_set_upload_fail_reason(UPLOAD_FAIL_MUX);
    }
    return 0U;
  }

#if TRACE_UPLOAD_USE_SSL
  (void)esp8266_send_cmd("AT+CIPSSLCCONF=0\r\n", "OK", 1000U);
  (void)esp8266_send_cmd("AT+CIPSSLSIZE=4096\r\n", "OK", 1000U);
  if (esp8266_build_ssl_sni_cmd())
  {
    (void)esp8266_send_cmd(esp_cmd_buffer, "OK", 1000U);
  }
#endif

  request_len = snprintf(esp_cmd_buffer, ESP8266_CMD_BUFFER_SIZE,
                         "AT+CIPSTART=\"%s\",\"%s\",%u\r\n",
                         esp8266_upload_link_type(), TRACE_UPLOAD_HOST,
                         (unsigned int)TRACE_UPLOAD_PORT);
  if ((request_len < 0) || (request_len >= (int)ESP8266_CMD_BUFFER_SIZE))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_BUILD);
    return 0U;
  }
  if (!esp8266_send_cmd(esp_cmd_buffer, TRACE_UPLOAD_USE_SSL ? "OK" : "CONNECT",
                        TRACE_UPLOAD_USE_SSL ? 45000U : 20000U))
  {
    trace_set_upload_fail_reason(esp8266_classify_link_fail());
    return 0U;
  }
  if (!esp8266_wait_link_connected(TRACE_UPLOAD_USE_SSL ? 20000U : 12000U))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_STAT);
    return 0U;
  }
  vTaskDelay(pdMS_TO_TICKS(TRACE_UPLOAD_USE_SSL ? 500U : 100U));

  request_len = snprintf(
      trace_http_buffer,
      TRACE_HTTP_BUFFER_SIZE,
      "POST /v1/events HTTP/1.1\r\n"
      "Host: %s\r\n"
      "Content-Type: application/json\r\n"
      "Idempotency-Key: stm32-lite-%u-%.8s\r\n"
      "User-Agent: stm32f103-esp8266/1.0\r\n"
      "Connection: close\r\n"
      "Content-Length: %d\r\n"
      "\r\n"
      "%s",
      TRACE_UPLOAD_HOST,
      upload_seq,
      trace_signature_buffer,
      body_len,
      trace_body_buffer);
  if ((request_len < 0) || (request_len >= (int)TRACE_HTTP_BUFFER_SIZE))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_BUILD);
    return 0U;
  }

  snprintf(esp_cmd_buffer, ESP8266_CMD_BUFFER_SIZE, "AT+CIPSEND=%d\r\n", request_len);
  esp8266_rx_clear();
  if (HAL_UART_Transmit(&huart3, (uint8_t *)esp_cmd_buffer, (uint16_t)strlen(esp_cmd_buffer), 200U) != HAL_OK)
  {
    esp8266_clear_uart_error();
    trace_set_upload_fail_reason(UPLOAD_FAIL_SEND);
    return 0U;
  }
  if (!esp8266_wait_for(">", TRACE_UPLOAD_USE_SSL ? 10000U : 8000U))
  {
    trace_set_upload_fail_reason(esp8266_classify_cipsend_prompt_fail());
    return 0U;
  }
  if (!esp8266_send_bytes_chunked(trace_http_buffer, (uint16_t)request_len))
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_SEND);
    return 0U;
  }
  (void)esp8266_wait_for("SEND OK", 12000U);
  if (last_http_status == 202U)
  {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return 1U;
  }
  if (!esp8266_wait_for("CLOSED", TRACE_UPLOAD_USE_SSL ? 20000U : 18000U))
  {
    parsed_status = parse_http_status();
    if (parsed_status != 0U)
    {
      last_http_status = parsed_status;
    }
    if (last_http_status == 202U)
    {
      (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
      return 1U;
    }
    trace_set_upload_fail_reason(UPLOAD_FAIL_RESP);
    return 0U;
  }

  parsed_status = parse_http_status();
  if (parsed_status != 0U)
  {
    last_http_status = parsed_status;
  }
  if (last_http_status != 202U)
  {
    trace_set_upload_fail_reason(UPLOAD_FAIL_RESP);
  }
  return (last_http_status == 202U) ? 1U : 0U;
}

static void trace_upload_once(void)
{
  TraceSnapshot snapshot;

  if (TRACE_UPLOAD_HOST[0] == '\0')
  {
    trace_set_upload_state(UPLOAD_STATE_NO_HOST, 0U);
    return;
  }
  if (TRACE_DEVICE_SECRET[0] == '\0')
  {
    trace_set_upload_state(UPLOAD_STATE_NO_KEY, 0U);
    return;
  }

  trace_set_upload_state(UPLOAD_STATE_SENDING, 0U);
  if (!trace_sync_clock_if_needed(trace_time_buffer))
  {
    if (!trace_build_fallback_time(trace_time_buffer))
    {
      ++upload_fail_count;
      trace_set_upload_state(UPLOAD_STATE_NO_TIME, 0U);
      return;
    }
    trace_clock_set_from_iso(trace_time_buffer);
  }

  trace_snapshot(&snapshot);
  if (!trace_build_payload(&snapshot, trace_time_buffer))
  {
    ++upload_fail_count;
    trace_set_upload_state(UPLOAD_STATE_FAIL, 0U);
    return;
  }

  if (esp8266_http_post_event())
  {
    ++upload_ok_count;
    ++upload_seq;
    trace_set_upload_state(UPLOAD_STATE_OK, last_http_status);
  }
  else
  {
    ++upload_fail_count;
    trace_set_upload_state(UPLOAD_STATE_FAIL, last_http_status);
  }
}

static void send_bt_status(void)
{
  static const uint8_t msg[] = "CHERRY TRACE NODE READY\r\n";
  (void)HAL_UART_Transmit(&huart1, (uint8_t *)msg, sizeof(msg) - 1U, 30U);
}

static uint32_t fnv1a_update(uint32_t hash, uint32_t value)
{
  for (uint8_t i = 0; i < 4U; ++i)
  {
    hash ^= (uint8_t)(value >> (i * 8U));
    hash *= 16777619UL;
  }
  return hash;
}

static void update_hash(void)
{
  uint32_t h = 2166136261UL;
  h = fnv1a_update(h, sample_id);
  h = fnv1a_update(h, dht.ok ? dht.temp_c : 0xEEU);
  h = fnv1a_update(h, dht.ok ? dht.hum_pct : 0xEEU);
  h = fnv1a_update(h, ds18b20.ok ? (uint16_t)ds18b20.temp_centi : 0xEEEEU);
  h = fnv1a_update(h, board.w25_ok ? board.w25_id[2] : 0U);
  batch_hash = h;
}

static void lock_state(void)
{
  if (state_mutex != NULL)
  {
    (void)xSemaphoreTake(state_mutex, portMAX_DELAY);
  }
}

static void unlock_state(void)
{
  if (state_mutex != NULL)
  {
    (void)xSemaphoreGive(state_mutex);
  }
}

static void request_ui_refresh(void)
{
  ui_dirty = 1U;
  if (ui_task_handle != NULL)
  {
    (void)xTaskNotifyGive(ui_task_handle);
  }
}

static uint8_t abs_diff_u8(uint8_t a, uint8_t b)
{
  return (a > b) ? (uint8_t)(a - b) : (uint8_t)(b - a);
}

static void update_quality_score(void)
{
  uint8_t temp = dht.ok ? dht.temp_c : 5U;
  uint8_t hum = dht.ok ? dht.hum_pct : 92U;
  int16_t score = 100;

  score -= (int16_t)abs_diff_u8(temp, 4U) * 3;
  score -= (int16_t)abs_diff_u8(hum, 90U) / 2;

  if (score < 0)
  {
    score = 0;
  }
  if (score > 100)
  {
    score = 100;
  }

  quality_score = (uint8_t)score;
}

static void self_test(void)
{
  board.oled_ok = 1U;
  board.at24_ok = (OLED_ProbeI2C(0x50U) == HAL_OK) ? 1U : 0U;
  board.w25_ok = w25q32_read_id(board.w25_id);
  board.bt_seen = 1U;
}

static char hex_digit(uint8_t value)
{
  value &= 0x0FU;
  return (value < 10U) ? (char)('0' + value) : (char)('A' + value - 10U);
}

static void draw_hex8(uint8_t x, uint8_t y, uint32_t value)
{
  char text[9];

  for (uint8_t i = 0; i < 8U; ++i)
  {
    text[i] = hex_digit((uint8_t)(value >> ((7U - i) * 4U)));
  }
  text[8] = '\0';
  OLED_DrawString(x, y, text);
}

static void draw_hex2(uint8_t x, uint8_t y, uint8_t value)
{
  char text[3];

  text[0] = hex_digit((uint8_t)(value >> 4));
  text[1] = hex_digit(value);
  text[2] = '\0';
  OLED_DrawString(x, y, text);
}

static void draw_uint(uint8_t x, uint8_t y, uint16_t value, uint8_t width)
{
  char text[6];

  if (width > 5U)
  {
    width = 5U;
  }

  for (int8_t i = (int8_t)width - 1; i >= 0; --i)
  {
    text[i] = (char)('0' + (value % 10U));
    value /= 10U;
  }
  text[width] = '\0';
  OLED_DrawString(x, y, text);
}

static void draw_signed_temp(uint8_t x, uint8_t y, int16_t centi)
{
  char text[8];
  uint16_t abs_value;
  uint16_t whole;
  uint16_t tenth;
  uint8_t pos = 0U;

  if (centi < 0)
  {
    text[pos++] = '-';
    abs_value = (uint16_t)(-centi);
  }
  else
  {
    abs_value = (uint16_t)centi;
  }

  whole = abs_value / 100U;
  tenth = (abs_value % 100U) / 10U;
  if (whole >= 100U)
  {
    whole = 99U;
  }

  if (whole >= 10U)
  {
    text[pos++] = (char)('0' + (whole / 10U));
  }
  text[pos++] = (char)('0' + (whole % 10U));
  text[pos++] = '.';
  text[pos++] = (char)('0' + tenth);
  text[pos++] = 'C';
  text[pos] = '\0';
  OLED_DrawString(x, y, text);
}

static void draw_header(const char *title)
{
  OLED_DrawUTF8(0, 0, title);
  OLED_DrawString(103, 4, "P");
  draw_uint(109, 4, (uint16_t)(current_page + 1U), 1U);
  OLED_DrawString(115, 4, "/");
  draw_uint(121, 4, PAGE_COUNT, 1U);
  OLED_DrawHLine(0, 17, 128, 1U);
}

static void draw_status_dot(uint8_t x, uint8_t y, uint8_t ok)
{
  OLED_DrawRect(x, y, 9U, 9U, 1U);
  if (ok)
  {
    OLED_FillRect((uint8_t)(x + 2U), (uint8_t)(y + 2U), 5U, 5U, 1U);
  }
}

static void draw_sensor_page(void)
{
  draw_header("樱桃溯源");

  OLED_DrawUTF8(0, 21, "温湿度");
  if (dht.ok)
  {
    draw_uint(58, 25, dht.temp_c, 2U);
    OLED_DrawString(70, 25, "C");
    draw_uint(88, 25, dht.hum_pct, 2U);
    OLED_DrawString(100, 25, "%");
  }
  else
  {
    OLED_DrawUTF8(58, 25, "等待");
    OLED_DrawString(92, 25, "DHT");
  }

  OLED_DrawUTF8(0, 39, "果温");
  if (ds18b20.ok)
  {
    draw_signed_temp(42, 43, ds18b20.temp_centi);
  }
  else
  {
    OLED_DrawUTF8(42, 43, "等待");
    OLED_DrawString(76, 43, "DS18");
  }

  OLED_DrawUTF8(84, 39, "质量");
  draw_uint(116, 43, quality_score, 2U);
  OLED_DrawBar(0, 57, 124, 7, quality_score, 100U);
}

static void draw_chain_page(void)
{
  draw_header("区块链");
  OLED_DrawUTF8(0, 22, "批次");
  OLED_DrawString(40, 26, "2026");
  OLED_DrawUTF8(74, 22, "样本");
  draw_uint(110, 26, sample_id, 3U);
  OLED_DrawUTF8(0, 40, "哈希");
  draw_hex8(40, 44, batch_hash);
  OLED_DrawUTF8(0, 56, "采样>签名>上传");
}

static void draw_storage_page(void)
{
  draw_header("存储状态");
  OLED_DrawUTF8(0, 22, "闪存");
  OLED_DrawString(40, 26, "W25Q32");
  draw_status_dot(88, 23, board.w25_ok);
  draw_hex2(104, 26, board.w25_id[0]);
  draw_hex2(116, 26, board.w25_id[1]);

  OLED_DrawUTF8(0, 40, "芯片");
  OLED_DrawString(40, 44, "AT24C08");
  draw_status_dot(88, 41, board.at24_ok);

  OLED_DrawString(0, 56, "REC");
  draw_uint(24, 56, sample_id, 4U);
  OLED_DrawString(58, 56, board.w25_ok ? "FLASH OK" : "FLASH WAIT");
}

static void draw_comm_page(void)
{
  draw_header("通信");

  OLED_DrawString(0, 23, "WIFI");
  switch (wifi_state)
  {
    case WIFI_STATE_NO_SSID:
      OLED_DrawString(36, 23, "NO SSID");
      break;
    case WIFI_STATE_AT_FAIL:
      OLED_DrawString(36, 23, "AT FAIL");
      break;
    case WIFI_STATE_JOINING:
      OLED_DrawString(36, 23, "JOIN");
      break;
    case WIFI_STATE_READY:
      OLED_DrawString(36, 23, "READY");
      break;
    case WIFI_STATE_FAIL:
      OLED_DrawString(36, 23, "FAIL");
      break;
    default:
      OLED_DrawString(36, 23, board.wifi_seen ? "OK" : "WAIT");
      break;
  }

  OLED_DrawString(86, 23, "BT");
  OLED_DrawString(104, 23, board.bt_seen ? "OK" : "NO");

  OLED_DrawString(0, 41, "UP");
  switch (upload_state)
  {
    case UPLOAD_STATE_NO_HOST:
      OLED_DrawString(18, 41, "NO HOST");
      break;
    case UPLOAD_STATE_NO_KEY:
      OLED_DrawString(18, 41, "NO KEY");
      break;
    case UPLOAD_STATE_NO_TIME:
      OLED_DrawString(18, 41, "NO TIME");
      break;
    case UPLOAD_STATE_SENDING:
      OLED_DrawString(18, 41, "SEND");
      break;
    case UPLOAD_STATE_OK:
      OLED_DrawString(18, 41, "OK");
      OLED_DrawString(38, 41, "HTTP");
      draw_uint(70, 41, last_http_status, 3U);
      break;
    case UPLOAD_STATE_FAIL:
      OLED_DrawString(18, 41, "FAIL");
      if (last_http_status != 0U)
      {
        OLED_DrawString(58, 41, "HTTP");
        draw_uint(90, 41, last_http_status, 3U);
      }
      else
      {
        OLED_DrawString(58, 41, upload_fail_reason_text());
      }
      break;
    default:
      OLED_DrawString(18, 41, "WAIT");
      break;
  }

  OLED_DrawString(0, 57, "SEQ");
  draw_uint(24, 57, upload_seq, 4U);
  OLED_DrawString(58, 57, "OK");
  draw_uint(76, 57, upload_ok_count, 3U);
  OLED_DrawString(100, 57, "F");
  draw_uint(112, 57, upload_fail_count, 2U);
}

static void draw_selftest_page(void)
{
  draw_header("SELF TEST");
  OLED_DrawString(0, 23, "OLED");
  draw_status_dot(36, 22, board.oled_ok);
  OLED_DrawString(64, 23, "IR");
  draw_status_dot(92, 22, last_ir_key != 0U);

  OLED_DrawString(0, 41, "DHT");
  draw_status_dot(36, 40, dht.ok);
  OLED_DrawString(64, 41, "DS18");
  draw_status_dot(92, 40, ds18b20.ok);

  OLED_DrawString(0, 57, "FLASH");
  draw_status_dot(42, 55, board.w25_ok);
  OLED_DrawString(64, 57, "EEP");
  draw_status_dot(94, 55, board.at24_ok);
}

static uint8_t trace_qr_module(uint8_t row, uint8_t col)
{
  return (trace_qr_bitmap[row][col / 8U] & (uint8_t)(0x80U >> (col % 8U))) ? 1U : 0U;
}

static void draw_trace_qr_page(void)
{
  uint8_t x;
  uint8_t y;

  OLED_FillRect(0, 0, 128, 64, 0U);
  OLED_FillRect(TRACE_QR_X, TRACE_QR_Y, TRACE_QR_SIZE * TRACE_QR_SCALE,
                TRACE_QR_SIZE * TRACE_QR_SCALE, 1U);

  for (uint8_t row = 0U; row < TRACE_QR_SIZE; ++row)
  {
    for (uint8_t col = 0U; col < TRACE_QR_SIZE; ++col)
    {
      if (trace_qr_module(row, col))
      {
        x = (uint8_t)(TRACE_QR_X + (col * TRACE_QR_SCALE));
        y = (uint8_t)(TRACE_QR_Y + (row * TRACE_QR_SCALE));
        OLED_FillRect(x, y, TRACE_QR_SCALE, TRACE_QR_SCALE, 0U);
      }
    }
  }

  OLED_DrawUTF8(70, 0, "扫码");
  OLED_DrawString(70, 17, "TRACE");
  OLED_DrawString(70, 31, "FIXED");
  OLED_DrawString(70, 45, "BATCH");
  OLED_DrawString(70, 56, "P6/6");
}

#if IR_LEARN_MODE
static void draw_ir_learn_page(void)
{
  OLED_DrawString(0, 0, "IR LEARN MODE");
  OLED_DrawHLine(0, 9, 128, 1U);

  if (ir_key_count == 0U)
  {
    OLED_DrawString(0, 17, "PRESS REMOTE KEY");
    OLED_DrawString(0, 33, "OLED SHOWS CODE");
    OLED_DrawString(0, 49, "SEND ME THE LIST");
    return;
  }

  OLED_DrawString(0, 15, "DEC");
  draw_uint(36, 15, last_ir_key, 3U);

  OLED_DrawString(0, 29, "HEX 0X");
  draw_hex2(42, 29, last_ir_key);

  OLED_DrawString(0, 43, "COUNT");
  draw_uint(42, 43, ir_key_count, 4U);

  OLED_DrawString(0, 56, last_ir_repeat ? "REPEAT" : "NEW KEY");
}
#endif

static void render_page(void)
{
  OLED_Clear();

#if IR_LEARN_MODE
  draw_ir_learn_page();
#else
  switch (current_page)
  {
    case 0: draw_sensor_page(); break;
    case 1: draw_chain_page(); break;
    case 2: draw_storage_page(); break;
    case 3: draw_comm_page(); break;
    case 4: draw_selftest_page(); break;
    default: draw_trace_qr_page(); break;
  }
#endif

  OLED_Update();
}

static void render_boot_page(const char *status)
{
  OLED_Clear();
  OLED_DrawString(0, 0, "CHERRY TRACE");
  OLED_DrawHLine(0, 9, 128, 1U);
  OLED_DrawString(0, 18, "FREERTOS BOOT");
  OLED_DrawString(0, 34, status);
  OLED_DrawString(0, 50, "UI TASK STARTING");
  OLED_Update();
}

static void beep(uint16_t ms)
{
  HAL_GPIO_WritePin(BUZZER_GPIO_Port, BUZZER_Pin, GPIO_PIN_SET);
  vTaskDelay(pdMS_TO_TICKS(ms));
  HAL_GPIO_WritePin(BUZZER_GPIO_Port, BUZZER_Pin, GPIO_PIN_RESET);
}

static void request_beep(uint16_t ms)
{
  if (ms == 0U)
  {
    return;
  }
  if (ms > 1000U)
  {
    ms = 1000U;
  }

  if (buzzer_task_handle != NULL)
  {
    (void)xTaskNotify(buzzer_task_handle, (uint32_t)ms, eSetValueWithOverwrite);
  }
}

static uint16_t beep_ms_for_key(uint8_t key)
{
  if (key == 22U)
  {
    return 250U;
  }
  if (key == 28U)
  {
    return 80U;
  }
  return 30U;
}

static uint8_t key_to_digit(uint8_t key)
{
  switch (key)
  {
    case 25U:
      return 0U;
    case 69U:
      return 1U;
    case 70U:
      return 2U;
    case 71U:
      return 3U;
    case 68U:
      return 4U;
    case 64U:
      return 5U;
    case 67U:
      return 6U;
    case 7U:
      return 7U;
    case 21U:
      return 8U;
    case 9U:
      return 9U;
    default:
      return 0xFFU;
  }
}

static uint8_t key_is_previous(uint8_t key)
{
  return ((key == 8U) || (key == 24U));
}

static uint8_t key_is_next(uint8_t key)
{
  return ((key == 90U) || (key == 82U));
}

static uint8_t key_is_sample(uint8_t key)
{
  return (key == 28U);
}

static uint8_t key_is_buzzer(uint8_t key)
{
  return (key == 22U);
}

static uint8_t key_is_auto(uint8_t key)
{
  return (key == 13U);
}

static uint8_t key_can_repeat(uint8_t key)
{
  return (uint8_t)(key_is_previous(key) || key_is_next(key));
}

static void next_page(void)
{
  current_page = (uint8_t)((current_page + 1U) % PAGE_COUNT);
}

static void previous_page(void)
{
  current_page = (current_page == 0U) ? (PAGE_COUNT - 1U) : (uint8_t)(current_page - 1U);
}

static void handle_key(uint8_t key)
{
  static const char *digit_action[] = {
    "HOME", "PAGE1", "PAGE2", "PAGE3", "PAGE4",
    "PAGE5", "NUM6", "NUM7", "NUM8", "NUM9"
  };
  uint8_t digit = key_to_digit(key);

  lock_state();
  last_ir_key = key;
  last_ir_action = "KEY";

  if (digit != 0xFFU)
  {
    if (digit == 0U)
    {
      current_page = 0U;
    }
    else if (digit <= PAGE_COUNT)
    {
      current_page = (uint8_t)(digit - 1U);
    }
    last_ir_action = digit_action[digit];
  }
  else if (key_is_next(key))
  {
    next_page();
    last_ir_action = "NEXT";
  }
  else if (key_is_previous(key))
  {
    previous_page();
    last_ir_action = "PREV";
  }
  else if (key_is_sample(key))
  {
      (void)dht11_read(&dht);
      if (!ds18b20.converting)
      {
        (void)ds18b20_start_conversion();
      }
      ++sample_id;
      update_quality_score();
      update_hash();
      last_ir_action = "SAMPLE";
  }
  else if (key_is_buzzer(key))
  {
    last_ir_action = "BUZZ";
  }
  else if (key_is_auto(key))
  {
    auto_rotate = auto_rotate ? 0U : 1U;
    last_ir_action = auto_rotate ? "AUTO ON" : "AUTO OFF";
  }
  else
  {
    last_ir_action = "UNKNOWN";
  }

  unlock_state();

  request_ui_refresh();
}

static void update_sensors(void)
{
  uint32_t now = HAL_GetTick();
  uint8_t changed = 0U;

  if ((uint32_t)(now - last_sensor_ms) >= 2000UL)
  {
    last_sensor_ms = now;
    lock_state();
    (void)dht11_read(&dht);
    if (!ds18b20.converting)
    {
      (void)ds18b20_start_conversion();
    }
    ++sample_id;
    update_quality_score();
    update_hash();
    unlock_state();
    changed = 1U;
  }

  if (ds18b20.converting && ((uint32_t)(now - ds18b20.convert_started_ms) >= 800UL))
  {
    lock_state();
    (void)ds18b20_finish_conversion();
    update_hash();
    unlock_state();
    changed = 1U;
  }

  if (changed != 0U)
  {
    request_ui_refresh();
  }
}

void TraceApp_Init(I2C_HandleTypeDef *hi2c, SPI_HandleTypeDef *hspi, TIM_HandleTypeDef *htim)
{
  app_i2c = hi2c;
  app_spi = hspi;
  app_tim = htim;
  current_page = 0U;
  auto_rotate = 0U;

  state_mutex = xSemaphoreCreateMutex();
  oled_mutex = xSemaphoreCreateMutex();
  ir_queue = xQueueCreate(8U, sizeof(IR_Event));

  if ((state_mutex == NULL) || (oled_mutex == NULL) || (ir_queue == NULL))
  {
    Error_Handler();
  }

  if (OLED_Init(app_i2c) != HAL_OK)
  {
    board.oled_ok = 0U;
  }
  else
  {
    board.oled_ok = 1U;
  }

  render_boot_page("OLED INIT DONE");
  send_bt_status();
  request_ui_refresh();
}

void TraceApp_StartScheduler(void)
{
#if IR_LEARN_MODE
  if ((xTaskCreate(IRTask, "IR", 160U, NULL, 5U, NULL) != pdPASS) ||
      (xTaskCreate(BuzzerTask, "Buzzer", 96U, NULL, 2U, &buzzer_task_handle) != pdPASS) ||
      (xTaskCreate(UITask, "UI", 256U, NULL, 3U, &ui_task_handle) != pdPASS))
  {
    Error_Handler();
  }
#else
  if ((xTaskCreate(SensorTask, "Sensor", 192U, NULL, 4U, NULL) != pdPASS) ||
      (xTaskCreate(IRTask, "IR", 160U, NULL, 5U, NULL) != pdPASS) ||
      (xTaskCreate(BuzzerTask, "Buzzer", 96U, NULL, 6U, &buzzer_task_handle) != pdPASS) ||
      (xTaskCreate(UITask, "UI", 256U, NULL, 3U, &ui_task_handle) != pdPASS) ||
      (xTaskCreate(SelfTestTask, "SelfTest", 192U, NULL, 2U, NULL) != pdPASS) ||
      (xTaskCreate(CommTask, "Comm", 384U, NULL, 1U, NULL) != pdPASS))
  {
    Error_Handler();
  }
#endif

  vTaskStartScheduler();
  Error_Handler();
}

static void SensorTask(void *argument)
{
  TickType_t last_wake = xTaskGetTickCount();
  (void)argument;

  for (;;)
  {
    update_sensors();
    vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(200U));
  }
}

static void UITask(void *argument)
{
  (void)argument;
  request_ui_refresh();

  for (;;)
  {
    uint8_t should_rotate = 0U;
    uint8_t should_render = 0U;

    (void)ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100U));

    lock_state();
    if (auto_rotate && ((uint32_t)(HAL_GetTick() - last_auto_ms) >= 3000UL))
    {
      last_auto_ms = HAL_GetTick();
      should_rotate = 1U;
    }
    if (should_rotate)
    {
      next_page();
    }
    if ((should_rotate != 0U) || (ui_dirty != 0U))
    {
      ui_dirty = 0U;
      should_render = 1U;
    }
    unlock_state();

    if (should_render != 0U)
    {
      if (oled_mutex != NULL)
      {
        (void)xSemaphoreTake(oled_mutex, portMAX_DELAY);
      }
      render_page();
      if (oled_mutex != NULL)
      {
        (void)xSemaphoreGive(oled_mutex);
      }
    }
  }
}

static void IRTask(void *argument)
{
  IR_Event event;
  uint8_t last_handled_key = 0U;
  uint32_t last_handled_ms = 0UL;
  (void)argument;

  for (;;)
  {
    if (xQueueReceive(ir_queue, &event, portMAX_DELAY) == pdPASS)
    {
      uint32_t now_ms = HAL_GetTick();

#if IR_LEARN_MODE
      lock_state();
      if (event.repeat == 0U)
      {
        last_ir_key = event.key;
        last_handled_key = event.key;
        ++ir_key_count;
      }
      else
      {
        last_ir_key = last_handled_key;
      }
      last_ir_repeat = event.repeat;
      last_ir_action = event.repeat ? "REPEAT" : "LEARN";
      unlock_state();
      request_beep(event.repeat ? 10U : 25U);
      request_ui_refresh();
      continue;
#else
      if (event.repeat != 0U)
      {
        if (key_can_repeat(last_handled_key) &&
            ((uint32_t)(now_ms - last_handled_ms) >= IR_NAV_REPEAT_MS))
        {
          last_handled_ms = now_ms;
          request_beep(beep_ms_for_key(last_handled_key));
          handle_key(last_handled_key);
        }
        continue;
      }

      uint8_t key = event.key;
      if ((uint32_t)(now_ms - last_handled_ms) < IR_KEY_DEBOUNCE_MS)
      {
        continue;
      }

      last_handled_key = key;
      last_handled_ms = now_ms;
      request_beep(beep_ms_for_key(key));
      handle_key(key);
#endif
    }
  }
}

static void SelfTestTask(void *argument)
{
  TickType_t last_wake = xTaskGetTickCount();
  (void)argument;

  for (;;)
  {
    lock_state();
    last_selftest_ms = HAL_GetTick();
    self_test();
    update_hash();
    unlock_state();
    request_ui_refresh();
    vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(8000U));
  }
}

static void BuzzerTask(void *argument)
{
  uint32_t notify_value = 0UL;
  TickType_t last_led = xTaskGetTickCount();
  (void)argument;

  beep(70U);

  for (;;)
  {
    if (xTaskNotifyWait(0UL, 0xFFFFFFFFUL, &notify_value, pdMS_TO_TICKS(1000U)) == pdTRUE)
    {
      if (notify_value > 0UL)
      {
        beep((uint16_t)notify_value);
      }
    }

    if ((xTaskGetTickCount() - last_led) >= pdMS_TO_TICKS(1000U))
    {
      last_led = xTaskGetTickCount();
      HAL_GPIO_TogglePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin);
    }
  }
}

static void CommTask(void *argument)
{
  (void)argument;

  for (;;)
  {
    uint32_t now_ms = HAL_GetTick();

    send_bt_status();
    lock_state();
    board.bt_seen = 1U;
    unlock_state();

    if ((wifi_state == WIFI_STATE_READY) &&
        ((uint32_t)(now_ms - last_wifi_try_ms) >= ESP8266_READY_CHECK_INTERVAL_MS))
    {
      last_wifi_try_ms = now_ms;
      esp8266_check_wifi();
    }
    else if ((wifi_state != WIFI_STATE_READY) &&
             ((last_wifi_try_ms == 0UL) ||
              ((uint32_t)(now_ms - last_wifi_try_ms) >= ESP8266_RETRY_INTERVAL_MS)))
    {
      last_wifi_try_ms = now_ms;
      wifi_ready_miss_count = 0U;
      esp8266_connect_wifi();
    }

    if ((wifi_state == WIFI_STATE_READY) &&
        ((last_upload_ms == 0UL) || ((uint32_t)(now_ms - last_upload_ms) >= TRACE_UPLOAD_INTERVAL_MS)))
    {
      last_upload_ms = HAL_GetTick();
      trace_upload_once();
    }

    vTaskDelay(pdMS_TO_TICKS(10000U));
  }
}

void TraceApp_IR_EdgeCallback(uint16_t gpio_pin)
{
  uint16_t now_us;
  uint16_t width_us;
  GPIO_PinState level;

  if ((gpio_pin != IR_RX_Pin) || (app_tim == 0))
  {
    return;
  }

  now_us = micros_now();
  width_us = micros_elapsed(ir_last_us, now_us);
  ir_last_us = now_us;
  level = HAL_GPIO_ReadPin(IR_RX_GPIO_Port, IR_RX_Pin);

  if (width_us > IR_FRAME_TIMEOUT_US)
  {
    ir_state = IR_WAIT_LEADER_LOW;
    ir_bits = 0UL;
    ir_bit_count = 0U;
  }

  if (level == GPIO_PIN_SET)
  {
    if (ir_state == IR_WAIT_LEADER_LOW)
    {
      if (in_range_u16(width_us, 8000U, 10000U))
      {
        ir_state = IR_WAIT_LEADER_HIGH;
      }
    }
    else if (ir_state == IR_READ_BITS)
    {
      if (!in_range_u16(width_us, 350U, 800U))
      {
        ir_state = IR_WAIT_LEADER_LOW;
        ir_bit_count = 0U;
      }
    }
  }
  else
  {
    if (ir_state == IR_WAIT_LEADER_HIGH)
    {
      if (in_range_u16(width_us, 4000U, 5000U))
      {
        ir_state = IR_READ_BITS;
        ir_bits = 0UL;
        ir_bit_count = 0U;
      }
      else if (in_range_u16(width_us, 1900U, 2600U))
      {
        IR_Event event = {0U, 1U};
        BaseType_t higher_priority_task_woken = pdFALSE;
        if (ir_queue != NULL)
        {
          (void)xQueueSendFromISR(ir_queue, &event, &higher_priority_task_woken);
          portYIELD_FROM_ISR(higher_priority_task_woken);
        }
        ir_state = IR_WAIT_LEADER_LOW;
      }
      else
      {
        ir_state = IR_WAIT_LEADER_LOW;
      }
    }
    else if (ir_state == IR_READ_BITS)
    {
      if (in_range_u16(width_us, 1000U, 2000U))
      {
        ir_bits |= (1UL << ir_bit_count);
      }
      else if (!in_range_u16(width_us, 350U, 900U))
      {
        ir_state = IR_WAIT_LEADER_LOW;
        ir_bit_count = 0U;
        return;
      }

      ++ir_bit_count;
      if (ir_bit_count >= 32U)
      {
        uint8_t cmd = (uint8_t)(ir_bits >> 16);
        uint8_t inv_cmd = (uint8_t)(ir_bits >> 24);

        if ((uint8_t)(cmd ^ inv_cmd) == 0xFFU)
        {
          IR_Event event = {cmd, 0U};
          BaseType_t higher_priority_task_woken = pdFALSE;
          if (ir_queue != NULL)
          {
            (void)xQueueSendFromISR(ir_queue, &event, &higher_priority_task_woken);
            portYIELD_FROM_ISR(higher_priority_task_woken);
          }
        }

        ir_state = IR_WAIT_LEADER_LOW;
        ir_bit_count = 0U;
      }
    }
  }
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
  TraceApp_IR_EdgeCallback(GPIO_Pin);
}

void vApplicationMallocFailedHook(void)
{
  Error_Handler();
}

void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName)
{
  (void)xTask;
  (void)pcTaskName;
  Error_Handler();
}
