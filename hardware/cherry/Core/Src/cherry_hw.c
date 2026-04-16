#include "cherry_hw.h"

#include <stdio.h>
#include <string.h>

#ifndef CHERRY_WIFI_SSID
#define CHERRY_WIFI_SSID "YOUR_SSID"
#endif

#ifndef CHERRY_WIFI_PASSWORD
#define CHERRY_WIFI_PASSWORD "YOUR_PASSWORD"
#endif

#ifndef CHERRY_HTTP_HOST
#define CHERRY_HTTP_HOST "192.168.1.100"
#endif

#ifndef CHERRY_HTTP_PORT
#define CHERRY_HTTP_PORT 8080U
#endif

#define CHERRY_INGEST_MODE_COMPAT 0U
#define CHERRY_INGEST_MODE_CANONICAL 1U

#ifndef CHERRY_INGEST_MODE
#define CHERRY_INGEST_MODE CHERRY_INGEST_MODE_COMPAT
#endif

#if (CHERRY_INGEST_MODE != CHERRY_INGEST_MODE_COMPAT) && \
    (CHERRY_INGEST_MODE != CHERRY_INGEST_MODE_CANONICAL)
#error "CHERRY_INGEST_MODE must be CHERRY_INGEST_MODE_COMPAT or CHERRY_INGEST_MODE_CANONICAL"
#endif

#ifndef CHERRY_DEVICE_ID
#define CHERRY_DEVICE_ID "stm32-cherry-node"
#endif

#ifndef CHERRY_BATCH_ID
#define CHERRY_BATCH_ID "compat-batch"
#endif

#ifndef CHERRY_SIGNING_KEY_ID
#define CHERRY_SIGNING_KEY_ID "compat-gateway-key"
#endif

#ifndef CHERRY_SUPPLY_CHAIN_STAGE
#define CHERRY_SUPPLY_CHAIN_STAGE "transport"
#endif

#ifndef CHERRY_HTTP_PATH
#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
#define CHERRY_HTTP_PATH "/v1/events"
#else
#define CHERRY_HTTP_PATH "/api/cherry/telemetry"
#endif
#endif

static uint8_t g_wifi_ready;
static volatile uint8_t g_lora_tx_done;

typedef struct {
  uint32_t state[8];
  uint64_t bitlen;
  uint8_t data[64];
  uint32_t datalen;
} Sha256Ctx;

static const uint32_t kSha256[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU,
    0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U,
    0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U,
    0xc19bf174U, 0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU, 0x983e5152U,
    0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
    0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU,
    0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U,
    0xd6990624U, 0xf40e3585U, 0x106aa070U, 0x19a4c116U, 0x1e376c08U,
    0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU,
    0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};

static inline uint32_t rotr32(uint32_t x, uint32_t n) {
  return (x >> n) | (x << (32U - n));
}

static uint8_t sht31_crc(const uint8_t *data, uint8_t len) {
  uint8_t crc = 0xFFU;
  for (uint8_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (uint8_t b = 0; b < 8U; ++b) {
      if (crc & 0x80U) {
        crc = (uint8_t)((crc << 1U) ^ 0x31U);
      } else {
        crc <<= 1U;
      }
    }
  }
  return crc;
}

static uint8_t bcd_to_dec(uint8_t bcd) {
  return (uint8_t)(((bcd >> 4U) * 10U) + (bcd & 0x0FU));
}

static uint8_t is_leap(uint16_t year) {
  return (uint8_t)(((year % 4U == 0U) && (year % 100U != 0U)) ||
                   (year % 400U == 0U));
}

static uint32_t unix_from_ymdhms(uint16_t year, uint8_t month, uint8_t day,
                                 uint8_t hour, uint8_t minute,
                                 uint8_t second) {
  static const uint16_t days_before_month[12] = {
      0U, 31U, 59U,  90U, 120U, 151U,
      181U, 212U, 243U, 273U, 304U, 334U};
  uint32_t days = 0U;

  if (year < 1970U || month == 0U || month > 12U || day == 0U || day > 31U) {
    return 0U;
  }

  for (uint16_t y = 1970U; y < year; ++y) {
    days += is_leap(y) ? 366U : 365U;
  }

  days += days_before_month[month - 1U];
  if (month > 2U && is_leap(year)) {
    days += 1U;
  }
  days += (uint32_t)(day - 1U);

  return days * 86400U + (uint32_t)hour * 3600U + (uint32_t)minute * 60U +
         (uint32_t)second;
}

static void sha256_transform(Sha256Ctx *ctx, const uint8_t data[64]) {
  uint32_t m[64];
  for (uint32_t i = 0; i < 16U; ++i) {
    m[i] = ((uint32_t)data[i * 4U] << 24U) | ((uint32_t)data[i * 4U + 1U] << 16U) |
           ((uint32_t)data[i * 4U + 2U] << 8U) | ((uint32_t)data[i * 4U + 3U]);
  }
  for (uint32_t i = 16U; i < 64U; ++i) {
    uint32_t s0 = rotr32(m[i - 15U], 7U) ^ rotr32(m[i - 15U], 18U) ^
                  (m[i - 15U] >> 3U);
    uint32_t s1 = rotr32(m[i - 2U], 17U) ^ rotr32(m[i - 2U], 19U) ^
                  (m[i - 2U] >> 10U);
    m[i] = m[i - 16U] + s0 + m[i - 7U] + s1;
  }

  uint32_t a = ctx->state[0];
  uint32_t b = ctx->state[1];
  uint32_t c = ctx->state[2];
  uint32_t d = ctx->state[3];
  uint32_t e = ctx->state[4];
  uint32_t f = ctx->state[5];
  uint32_t g = ctx->state[6];
  uint32_t h = ctx->state[7];

  for (uint32_t i = 0; i < 64U; ++i) {
    uint32_t s1 = rotr32(e, 6U) ^ rotr32(e, 11U) ^ rotr32(e, 25U);
    uint32_t ch = (e & f) ^ ((~e) & g);
    uint32_t temp1 = h + s1 + ch + kSha256[i] + m[i];
    uint32_t s0 = rotr32(a, 2U) ^ rotr32(a, 13U) ^ rotr32(a, 22U);
    uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
    uint32_t temp2 = s0 + maj;

    h = g;
    g = f;
    f = e;
    e = d + temp1;
    d = c;
    c = b;
    b = a;
    a = temp1 + temp2;
  }

  ctx->state[0] += a;
  ctx->state[1] += b;
  ctx->state[2] += c;
  ctx->state[3] += d;
  ctx->state[4] += e;
  ctx->state[5] += f;
  ctx->state[6] += g;
  ctx->state[7] += h;
}

static void sha256_init(Sha256Ctx *ctx) {
  ctx->datalen = 0U;
  ctx->bitlen = 0U;
  ctx->state[0] = 0x6a09e667U;
  ctx->state[1] = 0xbb67ae85U;
  ctx->state[2] = 0x3c6ef372U;
  ctx->state[3] = 0xa54ff53aU;
  ctx->state[4] = 0x510e527fU;
  ctx->state[5] = 0x9b05688cU;
  ctx->state[6] = 0x1f83d9abU;
  ctx->state[7] = 0x5be0cd19U;
}

static void sha256_update(Sha256Ctx *ctx, const uint8_t *data, size_t len) {
  for (size_t i = 0; i < len; ++i) {
    ctx->data[ctx->datalen++] = data[i];
    if (ctx->datalen == 64U) {
      sha256_transform(ctx, ctx->data);
      ctx->bitlen += 512U;
      ctx->datalen = 0U;
    }
  }
}

static void sha256_final(Sha256Ctx *ctx, uint8_t hash[32]) {
  uint32_t i = ctx->datalen;

  if (ctx->datalen < 56U) {
    ctx->data[i++] = 0x80U;
    while (i < 56U) {
      ctx->data[i++] = 0x00U;
    }
  } else {
    ctx->data[i++] = 0x80U;
    while (i < 64U) {
      ctx->data[i++] = 0x00U;
    }
    sha256_transform(ctx, ctx->data);
    memset(ctx->data, 0, 56U);
  }

  ctx->bitlen += (uint64_t)ctx->datalen * 8ULL;
  ctx->data[63] = (uint8_t)(ctx->bitlen);
  ctx->data[62] = (uint8_t)(ctx->bitlen >> 8U);
  ctx->data[61] = (uint8_t)(ctx->bitlen >> 16U);
  ctx->data[60] = (uint8_t)(ctx->bitlen >> 24U);
  ctx->data[59] = (uint8_t)(ctx->bitlen >> 32U);
  ctx->data[58] = (uint8_t)(ctx->bitlen >> 40U);
  ctx->data[57] = (uint8_t)(ctx->bitlen >> 48U);
  ctx->data[56] = (uint8_t)(ctx->bitlen >> 56U);
  sha256_transform(ctx, ctx->data);

  for (i = 0U; i < 4U; ++i) {
    hash[i] = (uint8_t)((ctx->state[0] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 4U] = (uint8_t)((ctx->state[1] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 8U] = (uint8_t)((ctx->state[2] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 12U] = (uint8_t)((ctx->state[3] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 16U] = (uint8_t)((ctx->state[4] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 20U] = (uint8_t)((ctx->state[5] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 24U] = (uint8_t)((ctx->state[6] >> (24U - i * 8U)) & 0xFFU);
    hash[i + 28U] = (uint8_t)((ctx->state[7] >> (24U - i * 8U)) & 0xFFU);
  }
}

static void sha256_digest(const uint8_t *data, size_t len, uint8_t out[32]) {
  Sha256Ctx ctx;
  sha256_init(&ctx);
  sha256_update(&ctx, data, len);
  sha256_final(&ctx, out);
}

static uint16_t atecc_crc16(const uint8_t *data, uint8_t len) {
  uint16_t crc_register = 0U;
  for (uint8_t counter = 0U; counter < len; counter++) {
    crc_register ^= (uint16_t)data[counter];
    for (uint8_t shift = 0U; shift < 8U; shift++) {
      if ((crc_register & 0x0001U) != 0U) {
        crc_register >>= 1U;
        crc_register ^= 0x8408U;
      } else {
        crc_register >>= 1U;
      }
    }
  }
  return crc_register;
}

static HAL_StatusTypeDef atecc_validate_response(const uint8_t *response,
                                                 uint8_t response_len,
                                                 uint8_t allow_wake_status) {
  uint8_t count;
  uint16_t crc_calc;
  uint16_t crc_rx;

  if (response == NULL || response_len < 4U) {
    return HAL_ERROR;
  }

  count = response[0];
  if (count < 4U || count > response_len) {
    return HAL_ERROR;
  }

  crc_calc = atecc_crc16(response, (uint8_t)(count - 2U));
  crc_rx = (uint16_t)response[count - 2U] |
           ((uint16_t)response[count - 1U] << 8U);
  if (crc_calc != crc_rx) {
    return HAL_ERROR;
  }

  if (count == 4U) {
    if (response[1] == 0x00U) {
      return HAL_OK;
    }
    if (allow_wake_status != 0U && response[1] == 0x11U) {
      return HAL_OK;
    }
    return HAL_ERROR;
  }

  return HAL_OK;
}

static HAL_StatusTypeDef atecc_wake(void) {
  uint8_t wake_byte = 0x00U;
  uint8_t wake_resp[4] = {0};

  (void)HAL_I2C_Master_Transmit(&hi2c1, 0x00U, &wake_byte, 1U, 5U);
  HAL_Delay(3U);

  if (HAL_I2C_Master_Receive(&hi2c1, ATECC608A_I2C_ADDR, wake_resp,
                             sizeof(wake_resp), 20U) != HAL_OK) {
    return HAL_ERROR;
  }

  return atecc_validate_response(wake_resp, sizeof(wake_resp), 1U);
}

static HAL_StatusTypeDef atecc_sleep(void) {
  uint8_t sleep_cmd[2] = {0x01U, 0x01U};
  return HAL_I2C_Master_Transmit(&hi2c1, ATECC608A_I2C_ADDR, sleep_cmd,
                                 sizeof(sleep_cmd), 20U);
}

static HAL_StatusTypeDef atecc_exec(uint8_t opcode, uint8_t param1,
                                    uint16_t param2, const uint8_t *data,
                                    uint8_t data_len, uint8_t *response,
                                    uint8_t response_len, uint32_t delay_ms) {
  uint8_t packet[84] = {0};
  uint8_t tx[85] = {0};
  uint8_t count = (uint8_t)(7U + data_len);
  uint8_t rx_count;
  uint16_t crc;

  if ((uint32_t)count + 1U > sizeof(tx)) {
    return HAL_ERROR;
  }

  packet[0] = count;
  packet[1] = opcode;
  packet[2] = param1;
  packet[3] = (uint8_t)(param2 & 0xFFU);
  packet[4] = (uint8_t)((param2 >> 8U) & 0xFFU);

  if (data_len > 0U && data != NULL) {
    memcpy(&packet[5], data, data_len);
  }

  crc = atecc_crc16(packet, (uint8_t)(count - 2U));
  packet[count - 2U] = (uint8_t)(crc & 0xFFU);
  packet[count - 1U] = (uint8_t)((crc >> 8U) & 0xFFU);

  tx[0] = 0x03U;
  memcpy(&tx[1], packet, count);

  if (HAL_I2C_Master_Transmit(&hi2c1, ATECC608A_I2C_ADDR, tx,
                              (uint16_t)(count + 1U), 50U) != HAL_OK) {
    return HAL_ERROR;
  }

  HAL_Delay(delay_ms);

  if (response == NULL || response_len < 4U) {
    return HAL_ERROR;
  }

  if (HAL_I2C_Master_Receive(&hi2c1, ATECC608A_I2C_ADDR, response, response_len,
                             50U) != HAL_OK) {
    return HAL_ERROR;
  }

  rx_count = response[0];
  if (rx_count < 4U || rx_count > response_len) {
    return HAL_ERROR;
  }

  return atecc_validate_response(response, rx_count, 0U);
}

static HAL_StatusTypeDef atecc_sign_digest(const uint8_t digest[32],
                                           uint8_t signature[64]) {
  uint8_t nonce_resp[4] = {0};
  uint8_t sign_resp[67] = {0};

  if (atecc_wake() != HAL_OK) {
    return HAL_ERROR;
  }

  if (atecc_exec(0x16U, 0x03U, 0x0000U, digest, 32U, nonce_resp,
                 sizeof(nonce_resp), 20U) != HAL_OK) {
    atecc_sleep();
    return HAL_ERROR;
  }

  if (atecc_exec(0x41U, 0x80U, 0x0000U, NULL, 0U, sign_resp,
                 sizeof(sign_resp), 60U) != HAL_OK) {
    atecc_sleep();
    return HAL_ERROR;
  }

  atecc_sleep();

  if (sign_resp[0] != 67U) {
    return HAL_ERROR;
  }

  memcpy(signature, &sign_resp[1], 64U);
  return HAL_OK;
}

static void fallback_sign(const uint8_t digest[32], uint8_t signature[64]) {
  static const uint8_t salt_a[8] = {0x43U, 0x48U, 0x45U, 0x52U,
                                    0x52U, 0x59U, 0x2DU, 0x41U};
  static const uint8_t salt_b[8] = {0x43U, 0x48U, 0x45U, 0x52U,
                                    0x52U, 0x59U, 0x2DU, 0x42U};
  uint8_t input[40] = {0};

  memcpy(input, digest, 32U);
  memcpy(&input[32], salt_a, sizeof(salt_a));
  sha256_digest(input, sizeof(input), &signature[0]);

  memcpy(&input[32], salt_b, sizeof(salt_b));
  sha256_digest(input, sizeof(input), &signature[32]);
}

static HAL_StatusTypeDef lora_write_reg(uint8_t reg, uint8_t value) {
  uint8_t tx[2] = {(uint8_t)(reg | 0x80U), value};
  HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_RESET);
  HAL_StatusTypeDef status = HAL_SPI_Transmit(&hspi1, tx, sizeof(tx), 20U);
  HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_SET);
  return status;
}

static HAL_StatusTypeDef lora_clear_irq_flags(void) {
  return lora_write_reg(0x12U, 0xFFU);
}

static HAL_StatusTypeDef lora_write_burst(uint8_t reg, const uint8_t *data,
                                          uint8_t len) {
  uint8_t reg_addr = (uint8_t)(reg | 0x80U);
  HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_RESET);
  if (HAL_SPI_Transmit(&hspi1, &reg_addr, 1U, 20U) != HAL_OK) {
    HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_SET);
    return HAL_ERROR;
  }
  HAL_StatusTypeDef status = HAL_SPI_Transmit(&hspi1, (uint8_t *)data, len, 50U);
  HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_SET);
  return status;
}

static HAL_StatusTypeDef lora_init(void) {
  HAL_GPIO_WritePin(LORA_RESET_GPIO_Port, LORA_RESET_Pin, GPIO_PIN_RESET);
  HAL_Delay(2U);
  HAL_GPIO_WritePin(LORA_RESET_GPIO_Port, LORA_RESET_Pin, GPIO_PIN_SET);
  HAL_Delay(10U);

  if (lora_write_reg(0x01U, 0x80U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x06U, 0x6CU) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x07U, 0x80U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x08U, 0x00U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x0EU, 0x00U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x0FU, 0x00U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x09U, 0x8FU) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_clear_irq_flags() != HAL_OK) {
    return HAL_ERROR;
  }
  return lora_write_reg(0x01U, 0x81U);
}

static HAL_StatusTypeDef lora_wait_tx_done(uint32_t timeout_ms) {
  uint32_t start = HAL_GetTick();

  while ((HAL_GetTick() - start) < timeout_ms) {
    if (g_lora_tx_done != 0U) {
      g_lora_tx_done = 0U;
      (void)lora_clear_irq_flags();
      return lora_write_reg(0x01U, 0x81U);
    }
    HAL_Delay(1U);
  }

  (void)lora_write_reg(0x01U, 0x81U);
  (void)lora_clear_irq_flags();
  return HAL_TIMEOUT;
}

static HAL_StatusTypeDef ds3231_read_time(uint32_t *out_unix) {
  uint8_t regs[7] = {0};
  if (HAL_I2C_Mem_Read(&hi2c1, DS3231_I2C_ADDR, 0x00U, I2C_MEMADD_SIZE_8BIT,
                       regs, sizeof(regs), 100U) != HAL_OK) {
    return HAL_ERROR;
  }

  uint8_t second = bcd_to_dec(regs[0] & 0x7FU);
  uint8_t minute = bcd_to_dec(regs[1] & 0x7FU);
  uint8_t hour = bcd_to_dec(regs[2] & 0x3FU);
  uint8_t day = bcd_to_dec(regs[4] & 0x3FU);
  uint8_t month = bcd_to_dec(regs[5] & 0x1FU);
  uint16_t year = (uint16_t)(2000U + bcd_to_dec(regs[6]));

  *out_unix = unix_from_ymdhms(year, month, day, hour, minute, second);
  return HAL_OK;
}

static HAL_StatusTypeDef sht31_read(float *temperature, float *humidity) {
  uint8_t cmd[2] = {0x24U, 0x00U};
  uint8_t rx[6] = {0};

  if (HAL_I2C_Master_Transmit(&hi2c1, SHT31_I2C_ADDR, cmd, sizeof(cmd), 50U) !=
      HAL_OK) {
    return HAL_ERROR;
  }

  HAL_Delay(20U);

  if (HAL_I2C_Master_Receive(&hi2c1, SHT31_I2C_ADDR, rx, sizeof(rx), 50U) !=
      HAL_OK) {
    return HAL_ERROR;
  }

  if (sht31_crc(&rx[0], 2U) != rx[2] || sht31_crc(&rx[3], 2U) != rx[5]) {
    return HAL_ERROR;
  }

  uint16_t raw_t = (uint16_t)(((uint16_t)rx[0] << 8U) | rx[1]);
  uint16_t raw_h = (uint16_t)(((uint16_t)rx[3] << 8U) | rx[4]);

  *temperature = -45.0f + 175.0f * ((float)raw_t / 65535.0f);
  *humidity = 100.0f * ((float)raw_h / 65535.0f);
  return HAL_OK;
}

static HAL_StatusTypeDef mhz19b_read(uint16_t *co2_ppm) {
  uint8_t cmd[9] = {0xFFU, 0x01U, 0x86U, 0x00U, 0x00U,
                    0x00U, 0x00U, 0x00U, 0x79U};
  uint8_t rx[9] = {0};

  if (HAL_UART_Transmit(&huart4, cmd, sizeof(cmd), 100U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (HAL_UART_Receive(&huart4, rx, sizeof(rx), 200U) != HAL_OK) {
    return HAL_ERROR;
  }

  uint8_t checksum = 0U;
  for (uint8_t i = 1U; i < 8U; ++i) {
    checksum = (uint8_t)(checksum + rx[i]);
  }
  checksum = (uint8_t)(0xFFU - checksum + 1U);

  if (rx[0] != 0xFFU || rx[1] != 0x86U || checksum != rx[8]) {
    return HAL_ERROR;
  }

  *co2_ppm = (uint16_t)(((uint16_t)rx[2] << 8U) | rx[3]);
  return HAL_OK;
}

static void bytes_to_hex(const uint8_t *bytes, size_t length, char *out,
                         size_t out_len) {
  static const char kHex[] = "0123456789ABCDEF";
  size_t i;

  if (bytes == NULL || out == NULL || out_len < (length * 2U + 1U)) {
    if (out != NULL && out_len > 0U) {
      out[0] = '\0';
    }
    return;
  }

  for (i = 0U; i < length; ++i) {
    out[i * 2U] = kHex[(bytes[i] >> 4U) & 0x0FU];
    out[i * 2U + 1U] = kHex[bytes[i] & 0x0FU];
  }
  out[length * 2U] = '\0';
}

static void esp8266_flush_rx(void) {
  uint8_t ch;
  while (HAL_UART_Receive(&huart1, &ch, 1U, 5U) == HAL_OK) {
  }
}

static HAL_StatusTypeDef esp8266_wait_for_token(const char *token,
                                                uint32_t timeout_ms) {
  char window[192] = {0};
  size_t used = 0U;
  uint32_t start = HAL_GetTick();

  if (token == NULL) {
    return HAL_OK;
  }

  while ((HAL_GetTick() - start) < timeout_ms) {
    uint8_t ch;
    HAL_StatusTypeDef st = HAL_UART_Receive(&huart1, &ch, 1U, 20U);
    if (st == HAL_OK) {
      if (used < sizeof(window) - 1U) {
        window[used++] = (char)ch;
      } else {
        memmove(window, &window[1], sizeof(window) - 2U);
        window[sizeof(window) - 2U] = (char)ch;
        used = sizeof(window) - 1U;
      }
      window[used] = '\0';

      if (strstr(window, token) != NULL) {
        return HAL_OK;
      }
      if (strstr(window, "ERROR") != NULL || strstr(window, "FAIL") != NULL ||
          strstr(window, "busy") != NULL) {
        return HAL_ERROR;
      }
    }
  }

  return HAL_TIMEOUT;
}

static HAL_StatusTypeDef esp8266_wait_http_2xx(uint32_t timeout_ms) {
  char window[192] = {0};
  size_t used = 0U;
  uint32_t start = HAL_GetTick();

  while ((HAL_GetTick() - start) < timeout_ms) {
    uint8_t ch;
    HAL_StatusTypeDef st = HAL_UART_Receive(&huart1, &ch, 1U, 20U);
    if (st != HAL_OK) {
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

    if (strstr(window, "HTTP/1.1 2") != NULL ||
        strstr(window, "HTTP/1.0 2") != NULL) {
      return HAL_OK;
    }
    if (strstr(window, "HTTP/1.1 3") != NULL ||
        strstr(window, "HTTP/1.0 3") != NULL ||
        strstr(window, "HTTP/1.1 4") != NULL ||
        strstr(window, "HTTP/1.0 4") != NULL ||
        strstr(window, "HTTP/1.1 5") != NULL ||
        strstr(window, "HTTP/1.0 5") != NULL ||
        strstr(window, "ERROR") != NULL ||
        strstr(window, "FAIL") != NULL ||
        strstr(window, "CLOSED") != NULL) {
      return HAL_ERROR;
    }
  }

  return HAL_TIMEOUT;
}

static HAL_StatusTypeDef esp8266_send_cmd(const char *cmd, const char *expect,
                                          uint32_t timeout_ms) {
  size_t len;
  if (cmd == NULL) {
    return HAL_ERROR;
  }

  len = strlen(cmd);
  if (len == 0U || len > 65535U) {
    return HAL_ERROR;
  }

  esp8266_flush_rx();
  if (HAL_UART_Transmit(&huart1, (uint8_t *)cmd, (uint16_t)len, 400U) != HAL_OK) {
    return HAL_ERROR;
  }

  return esp8266_wait_for_token(expect, timeout_ms);
}

static HAL_StatusTypeDef esp8266_join_ap(void) {
  char cmd[192];
  int n;

  if (strcmp(CHERRY_WIFI_SSID, "YOUR_SSID") == 0 ||
      strcmp(CHERRY_WIFI_PASSWORD, "YOUR_PASSWORD") == 0) {
    return HAL_ERROR;
  }

  if (esp8266_send_cmd("AT\r\n", "OK", 600U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (esp8266_send_cmd("ATE0\r\n", "OK", 600U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (esp8266_send_cmd("AT+CWMODE=1\r\n", "OK", 800U) != HAL_OK) {
    return HAL_ERROR;
  }

  n = snprintf(cmd, sizeof(cmd), "AT+CWJAP=\"%s\",\"%s\"\r\n",
               CHERRY_WIFI_SSID, CHERRY_WIFI_PASSWORD);
  if (n <= 0 || (size_t)n >= sizeof(cmd)) {
    return HAL_ERROR;
  }
  if (esp8266_send_cmd(cmd, "OK", 25000U) != HAL_OK) {
    return HAL_ERROR;
  }

  if (esp8266_send_cmd("AT+CIPMUX=0\r\n", "OK", 1000U) != HAL_OK) {
    return HAL_ERROR;
  }

  return HAL_OK;
}

static HAL_StatusTypeDef esp8266_post_json(const char *json_body,
                                           const char *idempotency_key) {
  char start_cmd[160];
  char send_cmd[32];
  char request[1200];
  int n;

  if (json_body == NULL) {
    return HAL_ERROR;
  }

  n = snprintf(start_cmd, sizeof(start_cmd),
               "AT+CIPSTART=\"TCP\",\"%s\",%u\r\n", CHERRY_HTTP_HOST,
               (unsigned)CHERRY_HTTP_PORT);
  if (n <= 0 || (size_t)n >= sizeof(start_cmd)) {
    return HAL_ERROR;
  }

  if (esp8266_send_cmd(start_cmd, "OK", 10000U) != HAL_OK) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    if (esp8266_send_cmd(start_cmd, "OK", 10000U) != HAL_OK) {
      return HAL_ERROR;
    }
  }

  if (idempotency_key != NULL && idempotency_key[0] != '\0') {
    n = snprintf(request, sizeof(request),
                 "POST %s HTTP/1.1\r\n"
                 "Host: %s:%u\r\n"
                 "Connection: close\r\n"
                 "Content-Type: application/json\r\n"
                 "Idempotency-Key: %s\r\n"
                 "Content-Length: %u\r\n\r\n"
                 "%s",
                 CHERRY_HTTP_PATH, CHERRY_HTTP_HOST, (unsigned)CHERRY_HTTP_PORT,
                 idempotency_key, (unsigned)strlen(json_body), json_body);
  } else {
    n = snprintf(request, sizeof(request),
                 "POST %s HTTP/1.1\r\n"
                 "Host: %s:%u\r\n"
                 "Connection: close\r\n"
                 "Content-Type: application/json\r\n"
                 "Content-Length: %u\r\n\r\n"
                 "%s",
                 CHERRY_HTTP_PATH, CHERRY_HTTP_HOST, (unsigned)CHERRY_HTTP_PORT,
                 (unsigned)strlen(json_body), json_body);
  }
  if (n <= 0 || (size_t)n >= sizeof(request)) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  n = snprintf(send_cmd, sizeof(send_cmd), "AT+CIPSEND=%d\r\n", n);
  if (n <= 0 || (size_t)n >= sizeof(send_cmd)) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  if (esp8266_send_cmd(send_cmd, ">", 2000U) != HAL_OK) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  if (HAL_UART_Transmit(&huart1, (uint8_t *)request, (uint16_t)strlen(request),
                        1000U) != HAL_OK) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  if (esp8266_wait_for_token("SEND OK", 5000U) != HAL_OK) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  if (esp8266_wait_http_2xx(5000U) != HAL_OK) {
    (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
    return HAL_ERROR;
  }

  (void)esp8266_send_cmd("AT+CIPCLOSE\r\n", "OK", 1000U);
  return HAL_OK;
}

HAL_StatusTypeDef CherryHw_Init(void) {
  HAL_GPIO_WritePin(LORA_NSS_GPIO_Port, LORA_NSS_Pin, GPIO_PIN_SET);
  HAL_GPIO_WritePin(LORA_RESET_GPIO_Port, LORA_RESET_Pin, GPIO_PIN_SET);
  g_lora_tx_done = 0U;
  if (lora_init() != HAL_OK) {
    return HAL_ERROR;
  }

  g_wifi_ready = (esp8266_join_ap() == HAL_OK) ? 1U : 0U;

  return HAL_OK;
}

HAL_StatusTypeDef CherryHw_ReadSensors(CherrySensorSnapshot *out) {
  HAL_StatusTypeDef status = HAL_OK;
  uint32_t rtc_unix = 0U;

  if (out == NULL) {
    return HAL_ERROR;
  }

  out->rtc_valid = true;
  out->env_valid = true;
  out->co2_valid = true;

  if (ds3231_read_time(&rtc_unix) == HAL_OK && rtc_unix > 0U) {
    out->unix_time = rtc_unix;
  } else {
    out->unix_time = HAL_GetTick() / 1000U;
    out->rtc_valid = false;
    status = HAL_ERROR;
  }

  if (sht31_read(&out->temperature_c, &out->humidity_rh) != HAL_OK) {
    out->temperature_c = -100.0f;
    out->humidity_rh = -1.0f;
    out->env_valid = false;
    status = HAL_ERROR;
  }

  if (mhz19b_read(&out->co2_ppm) != HAL_OK) {
    out->co2_ppm = 0U;
    out->co2_valid = false;
    status = HAL_ERROR;
  }

  /* No dedicated vibration sensor is currently wired in this firmware build. */
  out->vibration_alarm = false;

  return status;
}

HAL_StatusTypeDef CherryHw_SignSnapshot(const CherrySensorSnapshot *in,
                                        uint32_t sequence,
                                        CherrySignedPacket *out) {
  uint8_t packed[32] = {0};
  if (in == NULL || out == NULL) {
    return HAL_ERROR;
  }

  memcpy(&packed[0], &in->unix_time, sizeof(in->unix_time));
  memcpy(&packed[4], &in->temperature_c, sizeof(in->temperature_c));
  memcpy(&packed[8], &in->humidity_rh, sizeof(in->humidity_rh));
  memcpy(&packed[12], &in->co2_ppm, sizeof(in->co2_ppm));
  packed[14] = (uint8_t)(in->vibration_alarm ? 1U : 0U);
  memcpy(&packed[16], &sequence, sizeof(sequence));

  out->snapshot = *in;
  out->sequence = sequence;

  sha256_digest(packed, sizeof(packed), out->digest);

  if (atecc_sign_digest(out->digest, out->signature) == HAL_OK) {
    out->signature_len = 64U;
    out->signature_from_secure_element = true;
    return HAL_OK;
  }

  fallback_sign(out->digest, out->signature);
  out->signature_len = 64U;
  out->signature_from_secure_element = false;
  return HAL_ERROR;
}

HAL_StatusTypeDef CherryHw_SendViaWiFi(const CherrySignedPacket *packet) {
  char digest_hex[65];
  char signature_hex[129];
  char body[950];
#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
  char idempotency_key[96];
#endif
  int n;
  if (packet == NULL) {
    return HAL_ERROR;
  }

#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
  if (!packet->signature_from_secure_element) {
    return HAL_ERROR;
  }
#endif

  if (g_wifi_ready == 0U) {
    if (esp8266_join_ap() != HAL_OK) {
      return HAL_ERROR;
    }
    g_wifi_ready = 1U;
  }

  bytes_to_hex(packet->digest, sizeof(packet->digest), digest_hex,
               sizeof(digest_hex));
  bytes_to_hex(packet->signature, packet->signature_len, signature_hex,
               sizeof(signature_hex));

#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
  n = snprintf(idempotency_key, sizeof(idempotency_key),
               "hw:canonical:%s:%lu",
               CHERRY_DEVICE_ID,
               (unsigned long)packet->sequence);
  if (n <= 0 || (size_t)n >= sizeof(idempotency_key)) {
    g_wifi_ready = 0U;
    return HAL_ERROR;
  }

  n = snprintf(body, sizeof(body),
               "{\"version\":\"1.0.0\",\"device_id\":\"%s\",\"batch_id\":\"%s\","
               "\"timestamp\":%lu,\"sensor_payload\":{\"temperature_c\":%.2f,"
               "\"humidity_pct\":%.2f,\"seq\":%lu,\"co2_ppm\":%u,\"vibration\":%s,"
               "\"digest\":\"%s\"},\"signature_envelope\":{\"algorithm\":\"ECDSA\","
               "\"signature\":\"%s\",\"key_id\":\"%s\"},\"co2_ppm\":%u,"
               "\"vibration_g\":%.2f,\"supply_chain_stage\":\"%s\"}",
               CHERRY_DEVICE_ID,
               CHERRY_BATCH_ID,
               (unsigned long)packet->snapshot.unix_time,
               packet->snapshot.temperature_c,
               packet->snapshot.humidity_rh,
               (unsigned long)packet->sequence,
               packet->snapshot.co2_ppm,
               packet->snapshot.vibration_alarm ? "true" : "false",
               digest_hex,
               signature_hex,
               CHERRY_SIGNING_KEY_ID,
               packet->snapshot.co2_ppm,
               packet->snapshot.vibration_alarm ? 1.0f : 0.0f,
               CHERRY_SUPPLY_CHAIN_STAGE);
#else
  n = snprintf(body, sizeof(body),
               "{\"seq\":%lu,\"ts\":%lu,\"temp_c\":%.2f,\"hum_rh\":%.2f,"
               "\"co2\":%u,\"vibration\":%u,\"digest\":\"%s\","
               "\"signature\":\"%s\"}",
               (unsigned long)packet->sequence,
               (unsigned long)packet->snapshot.unix_time,
               packet->snapshot.temperature_c, packet->snapshot.humidity_rh,
               packet->snapshot.co2_ppm,
               (unsigned)packet->snapshot.vibration_alarm,
               digest_hex, signature_hex);
#endif

  if (n <= 0 || (size_t)n >= sizeof(body)) {
    g_wifi_ready = 0U;
    return HAL_ERROR;
  }

  if (esp8266_post_json(
          body,
#if CHERRY_INGEST_MODE == CHERRY_INGEST_MODE_CANONICAL
          idempotency_key
#else
          NULL
#endif
          ) != HAL_OK) {
    g_wifi_ready = 0U;
    return HAL_ERROR;
  }

  return HAL_OK;
}

HAL_StatusTypeDef CherryHw_SendViaLoRa(const CherrySignedPacket *packet) {
  uint8_t payload[64] = {0};
  uint8_t len = 0U;

  if (packet == NULL) {
    return HAL_ERROR;
  }

  payload[len++] = (uint8_t)(packet->sequence & 0xFFU);
  payload[len++] = (uint8_t)((packet->sequence >> 8U) & 0xFFU);
  payload[len++] = (uint8_t)(packet->snapshot.co2_ppm & 0xFFU);
  payload[len++] = (uint8_t)((packet->snapshot.co2_ppm >> 8U) & 0xFFU);
  memcpy(&payload[len], packet->digest, 16U);
  len += 16U;

  if (lora_write_reg(0x40U, 0x40U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_clear_irq_flags() != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x01U, 0x81U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x0DU, 0x00U) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_burst(0x00U, payload, len) != HAL_OK) {
    return HAL_ERROR;
  }
  if (lora_write_reg(0x22U, len) != HAL_OK) {
    return HAL_ERROR;
  }
  g_lora_tx_done = 0U;
  if (lora_write_reg(0x01U, 0x83U) != HAL_OK) {
    return HAL_ERROR;
  }

  return lora_wait_tx_done(1000U);
}

void CherryHw_OnLoRaDio0Rise(void) {
  g_lora_tx_done = 1U;
}
