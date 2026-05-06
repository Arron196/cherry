#include "oled_ssd1306.h"
#include "main.h"
#include <stddef.h>

#define OLED_ADDR_3C (0x3CU << 1)
#define OLED_ADDR_3D (0x3DU << 1)
#define OLED_PAGES   (OLED_HEIGHT / 8U)
#define SOFT_I2C_DELAY_LOOPS 40U
#define OLED_WRITE_CHUNK OLED_WIDTH

static uint16_t oled_addr = OLED_ADDR_3C;
static uint8_t oled_dual_address;
static uint8_t oled_buffer[OLED_WIDTH * OLED_PAGES];

#include "oled_hanzi16.inc"

static const uint8_t font_blank[5] = {0x00, 0x00, 0x00, 0x00, 0x00};
static const uint8_t font_dash[5] = {0x08, 0x08, 0x08, 0x08, 0x08};
static const uint8_t font_colon[5] = {0x00, 0x36, 0x36, 0x00, 0x00};
static const uint8_t font_0[5] = {0x3E, 0x51, 0x49, 0x45, 0x3E};
static const uint8_t font_1[5] = {0x00, 0x42, 0x7F, 0x40, 0x00};
static const uint8_t font_2[5] = {0x42, 0x61, 0x51, 0x49, 0x46};
static const uint8_t font_3[5] = {0x21, 0x41, 0x45, 0x4B, 0x31};
static const uint8_t font_4[5] = {0x18, 0x14, 0x12, 0x7F, 0x10};
static const uint8_t font_5[5] = {0x27, 0x45, 0x45, 0x45, 0x39};
static const uint8_t font_6[5] = {0x3C, 0x4A, 0x49, 0x49, 0x30};
static const uint8_t font_7[5] = {0x01, 0x71, 0x09, 0x05, 0x03};
static const uint8_t font_8[5] = {0x36, 0x49, 0x49, 0x49, 0x36};
static const uint8_t font_9[5] = {0x06, 0x49, 0x49, 0x29, 0x1E};
static const uint8_t font_a[5] = {0x7E, 0x11, 0x11, 0x11, 0x7E};
static const uint8_t font_b[5] = {0x7F, 0x49, 0x49, 0x49, 0x36};
static const uint8_t font_c[5] = {0x3E, 0x41, 0x41, 0x41, 0x22};
static const uint8_t font_d[5] = {0x7F, 0x41, 0x41, 0x22, 0x1C};
static const uint8_t font_e[5] = {0x7F, 0x49, 0x49, 0x49, 0x41};
static const uint8_t font_f[5] = {0x7F, 0x09, 0x09, 0x09, 0x01};
static const uint8_t font_g[5] = {0x3E, 0x41, 0x49, 0x49, 0x7A};
static const uint8_t font_h[5] = {0x7F, 0x08, 0x08, 0x08, 0x7F};
static const uint8_t font_i[5] = {0x00, 0x41, 0x7F, 0x41, 0x00};
static const uint8_t font_j[5] = {0x20, 0x40, 0x41, 0x3F, 0x01};
static const uint8_t font_k[5] = {0x7F, 0x08, 0x14, 0x22, 0x41};
static const uint8_t font_l[5] = {0x7F, 0x40, 0x40, 0x40, 0x40};
static const uint8_t font_m[5] = {0x7F, 0x02, 0x0C, 0x02, 0x7F};
static const uint8_t font_n[5] = {0x7F, 0x04, 0x08, 0x10, 0x7F};
static const uint8_t font_o[5] = {0x3E, 0x41, 0x41, 0x41, 0x3E};
static const uint8_t font_p[5] = {0x7F, 0x09, 0x09, 0x09, 0x06};
static const uint8_t font_q[5] = {0x3E, 0x41, 0x51, 0x21, 0x5E};
static const uint8_t font_r[5] = {0x7F, 0x09, 0x19, 0x29, 0x46};
static const uint8_t font_s[5] = {0x46, 0x49, 0x49, 0x49, 0x31};
static const uint8_t font_t[5] = {0x01, 0x01, 0x7F, 0x01, 0x01};
static const uint8_t font_u[5] = {0x3F, 0x40, 0x40, 0x40, 0x3F};
static const uint8_t font_v[5] = {0x1F, 0x20, 0x40, 0x20, 0x1F};
static const uint8_t font_w[5] = {0x7F, 0x20, 0x18, 0x20, 0x7F};
static const uint8_t font_x[5] = {0x63, 0x14, 0x08, 0x14, 0x63};
static const uint8_t font_y[5] = {0x07, 0x08, 0x70, 0x08, 0x07};
static const uint8_t font_z[5] = {0x61, 0x51, 0x49, 0x45, 0x43};
static const uint8_t font_dot[5] = {0x00, 0x60, 0x60, 0x00, 0x00};
static const uint8_t font_slash[5] = {0x20, 0x10, 0x08, 0x04, 0x02};
static const uint8_t font_percent[5] = {0x23, 0x13, 0x08, 0x64, 0x62};
static const uint8_t font_plus[5] = {0x08, 0x08, 0x3E, 0x08, 0x08};
static const uint8_t font_star[5] = {0x14, 0x08, 0x3E, 0x08, 0x14};
static const uint8_t font_hash[5] = {0x14, 0x7F, 0x14, 0x7F, 0x14};
static const uint8_t font_less[5] = {0x08, 0x14, 0x22, 0x41, 0x00};
static const uint8_t font_greater[5] = {0x00, 0x41, 0x22, 0x14, 0x08};
static const uint8_t font_caret[5] = {0x04, 0x02, 0x01, 0x02, 0x04};
static const uint8_t font_equal[5] = {0x14, 0x14, 0x14, 0x14, 0x14};

static void soft_i2c_delay(void)
{
  for (volatile uint16_t i = 0; i < SOFT_I2C_DELAY_LOOPS; ++i)
  {
    __NOP();
  }
}

static void oled_boot_delay_ms(uint16_t ms)
{
  while (ms-- != 0U)
  {
    for (volatile uint32_t i = 0; i < 7200UL; ++i)
    {
      __NOP();
    }
  }
}

static void soft_i2c_gpio_open_drain(uint16_t pin)
{
  uint32_t shift = 0U;

  if (pin == GPIO_PIN_6)
  {
    shift = 24U;
  }
  else if (pin == GPIO_PIN_7)
  {
    shift = 28U;
  }
  else if (pin == GPIO_PIN_10)
  {
    shift = 8U;
  }
  else if (pin == GPIO_PIN_11)
  {
    shift = 12U;
  }

  GPIOB->BSRR = pin;
  if (pin < GPIO_PIN_8)
  {
    GPIOB->CRL = (GPIOB->CRL & ~(0x0FUL << shift)) | (0x07UL << shift);
  }
  else
  {
    GPIOB->CRH = (GPIOB->CRH & ~(0x0FUL << shift)) | (0x07UL << shift);
  }
}

static void soft_i2c_gpio_high(uint16_t pin)
{
  GPIOB->BSRR = pin;
}

static void soft_i2c_gpio_low(uint16_t pin)
{
  GPIOB->BRR = pin;
}

static void soft_i2c_scl_high(void)
{
  soft_i2c_gpio_high(OLED_SCL_Pin);
  soft_i2c_delay();
}

static void soft_i2c_scl_low(void)
{
  soft_i2c_gpio_low(OLED_SCL_Pin);
  soft_i2c_delay();
}

static void soft_i2c_sda_high(void)
{
  soft_i2c_gpio_high(OLED_SDA_Pin);
  soft_i2c_delay();
}

static void soft_i2c_sda_low(void)
{
  soft_i2c_gpio_low(OLED_SDA_Pin);
  soft_i2c_delay();
}

static GPIO_PinState soft_i2c_sda_read(void)
{
  return HAL_GPIO_ReadPin(GPIOB, OLED_SDA_Pin);
}

static void soft_i2c_init_pins(void)
{
  __HAL_RCC_GPIOB_CLK_ENABLE();
  __HAL_RCC_I2C1_FORCE_RESET();
  __HAL_RCC_I2C1_RELEASE_RESET();
  __HAL_RCC_I2C1_CLK_DISABLE();
  soft_i2c_gpio_open_drain(OLED_SCL_Pin);
  soft_i2c_gpio_open_drain(OLED_SDA_Pin);
  soft_i2c_sda_high();
  soft_i2c_scl_high();
}

static void soft_i2c_start(void)
{
  soft_i2c_sda_high();
  soft_i2c_scl_high();
  soft_i2c_sda_low();
  soft_i2c_scl_low();
}

static void soft_i2c_stop(void)
{
  soft_i2c_sda_low();
  soft_i2c_scl_high();
  soft_i2c_sda_high();
}

static void soft_i2c_bus_recover(void)
{
  soft_i2c_sda_high();
  for (uint8_t i = 0; i < 9U; ++i)
  {
    soft_i2c_scl_low();
    soft_i2c_scl_high();
  }
  soft_i2c_stop();
}

static HAL_StatusTypeDef soft_i2c_write_byte_ex(uint8_t byte, uint8_t check_ack)
{
  for (uint8_t bit = 0; bit < 8U; ++bit)
  {
    if ((byte & 0x80U) != 0U)
    {
      soft_i2c_sda_high();
    }
    else
    {
      soft_i2c_sda_low();
    }

    soft_i2c_scl_high();
    soft_i2c_scl_low();
    byte <<= 1U;
  }

  soft_i2c_sda_high();
  soft_i2c_delay();
  soft_i2c_scl_high();
  GPIO_PinState ack = soft_i2c_sda_read();
  soft_i2c_scl_low();
  soft_i2c_sda_high();

  return ((check_ack == 0U) || (ack == GPIO_PIN_RESET)) ? HAL_OK : HAL_ERROR;
}

static HAL_StatusTypeDef soft_i2c_write_byte(uint8_t byte)
{
  return soft_i2c_write_byte_ex(byte, 1U);
}

static HAL_StatusTypeDef soft_i2c_probe(uint16_t addr)
{
  HAL_StatusTypeDef status;

  soft_i2c_start();
  status = soft_i2c_write_byte((uint8_t)addr);
  soft_i2c_stop();

  return status;
}

static HAL_StatusTypeDef oled_write_addr(uint16_t addr, uint8_t control, const uint8_t *data, uint16_t len)
{
  uint16_t offset = 0;

  if (data == NULL)
  {
    return HAL_ERROR;
  }

  while (offset < len)
  {
    uint16_t chunk = len - offset;
    if (chunk > OLED_WRITE_CHUNK)
    {
      chunk = OLED_WRITE_CHUNK;
    }

    soft_i2c_start();
    (void)soft_i2c_write_byte_ex((uint8_t)addr, 0U);
    (void)soft_i2c_write_byte_ex(control, 0U);

    for (uint16_t i = 0; i < chunk; ++i)
    {
      (void)soft_i2c_write_byte_ex(data[offset + i], 0U);
    }

    soft_i2c_stop();
    offset += chunk;
  }

  return HAL_OK;
}

static HAL_StatusTypeDef oled_write(uint8_t control, const uint8_t *data, uint16_t len)
{
  if (oled_dual_address != 0U)
  {
    (void)oled_write_addr(OLED_ADDR_3C, control, data, len);
    (void)oled_write_addr(OLED_ADDR_3D, control, data, len);
    return HAL_OK;
  }

  return oled_write_addr(oled_addr, control, data, len);
}

static HAL_StatusTypeDef oled_cmds(const uint8_t *cmds, uint16_t len)
{
  return oled_write(0x00U, cmds, len);
}

static const uint8_t *font_for_char(char ch)
{
  if ((ch >= 'a') && (ch <= 'z'))
  {
    ch = (char)(ch - ('a' - 'A'));
  }

  switch (ch)
  {
    case ' ': return font_blank;
    case '-': return font_dash;
    case ':': return font_colon;
    case '0': return font_0;
    case '1': return font_1;
    case '2': return font_2;
    case '3': return font_3;
    case '4': return font_4;
    case '5': return font_5;
    case '6': return font_6;
    case '7': return font_7;
    case '8': return font_8;
    case '9': return font_9;
    case 'A': return font_a;
    case 'B': return font_b;
    case 'C': return font_c;
    case 'D': return font_d;
    case 'E': return font_e;
    case 'F': return font_f;
    case 'G': return font_g;
    case 'H': return font_h;
    case 'I': return font_i;
    case 'J': return font_j;
    case 'K': return font_k;
    case 'L': return font_l;
    case 'M': return font_m;
    case 'N': return font_n;
    case 'O': return font_o;
    case 'P': return font_p;
    case 'Q': return font_q;
    case 'R': return font_r;
    case 'S': return font_s;
    case 'T': return font_t;
    case 'U': return font_u;
    case 'V': return font_v;
    case 'W': return font_w;
    case 'X': return font_x;
    case 'Y': return font_y;
    case 'Z': return font_z;
    case '.': return font_dot;
    case '/': return font_slash;
    case '%': return font_percent;
    case '+': return font_plus;
    case '*': return font_star;
    case '#': return font_hash;
    case '<': return font_less;
    case '>': return font_greater;
    case '^': return font_caret;
    case '=': return font_equal;
    default: return font_dash;
  }
}

HAL_StatusTypeDef OLED_Init(I2C_HandleTypeDef *hi2c)
{
  static const uint8_t init_cmds[] = {
    0xAE,       /* Display off */
    0x20, 0x00, /* Horizontal addressing mode */
    0xB0,
    0xC8,
    0x00,
    0x10,
    0x40,
    0x81, 0x7F,
    0xA1,
    0xA6,
    0xA8, 0x3F,
    0xA4,
    0xD3, 0x00,
    0xD5, 0x80,
    0xD9, 0xF1,
    0xDA, 0x12,
    0xDB, 0x40,
    0x8D, 0x14,
    0xAF        /* Display on */
  };

  (void)hi2c;
  oled_boot_delay_ms(120U);
  soft_i2c_init_pins();
  soft_i2c_bus_recover();
  oled_dual_address = 0U;

  if (soft_i2c_probe(OLED_ADDR_3C) == HAL_OK)
  {
    oled_addr = OLED_ADDR_3C;
  }
  else if (soft_i2c_probe(OLED_ADDR_3D) == HAL_OK)
  {
    oled_addr = OLED_ADDR_3D;
  }
  else
  {
    oled_addr = OLED_ADDR_3C;
    oled_dual_address = 1U;
  }

  if (oled_cmds(init_cmds, sizeof(init_cmds)) != HAL_OK)
  {
    return HAL_ERROR;
  }

  OLED_Clear();
  OLED_Update();
  return HAL_OK;
}

HAL_StatusTypeDef OLED_ProbeI2C(uint8_t address7)
{
  soft_i2c_init_pins();
  return soft_i2c_probe((uint16_t)address7 << 1);
}

void OLED_Clear(void)
{
  OLED_Fill(0x00U);
}

void OLED_Fill(uint8_t pattern)
{
  for (uint16_t i = 0; i < sizeof(oled_buffer); ++i)
  {
    oled_buffer[i] = pattern;
  }
}

void OLED_Update(void)
{
  for (uint8_t page = 0; page < OLED_PAGES; ++page)
  {
    uint8_t cmds[] = {
      (uint8_t)(0xB0U + page),
      0x00U,
      0x10U
    };

    if (oled_cmds(cmds, sizeof(cmds)) != HAL_OK)
    {
      return;
    }

    (void)oled_write(0x40U, &oled_buffer[OLED_WIDTH * page], OLED_WIDTH);
  }
}

void OLED_DrawPixel(uint8_t x, uint8_t y, uint8_t color)
{
  uint16_t index;

  if ((x >= OLED_WIDTH) || (y >= OLED_HEIGHT))
  {
    return;
  }

  index = (uint16_t)x + (uint16_t)(y / 8U) * OLED_WIDTH;
  if (color)
  {
    oled_buffer[index] |= (uint8_t)(1U << (y & 0x07U));
  }
  else
  {
    oled_buffer[index] &= (uint8_t)~(1U << (y & 0x07U));
  }
}

void OLED_DrawChar(uint8_t x, uint8_t y, char ch)
{
  const uint8_t *glyph = font_for_char(ch);

  for (uint8_t col = 0; col < 5U; ++col)
  {
    uint8_t bits = glyph[col];
    for (uint8_t row = 0; row < 7U; ++row)
    {
      OLED_DrawPixel((uint8_t)(x + col), (uint8_t)(y + row), (bits >> row) & 0x01U);
    }
  }

  for (uint8_t row = 0; row < 7U; ++row)
  {
    OLED_DrawPixel((uint8_t)(x + 5U), (uint8_t)(y + row), 0U);
  }
}

void OLED_DrawString(uint8_t x, uint8_t y, const char *str)
{
  while ((str != NULL) && (*str != '\0'))
  {
    if (x > (OLED_WIDTH - 6U))
    {
      x = 0U;
      y = (uint8_t)(y + 8U);
    }

    if (y > (OLED_HEIGHT - 7U))
    {
      return;
    }

    OLED_DrawChar(x, y, *str);
    x = (uint8_t)(x + 6U);
    ++str;
  }
}

static const uint8_t *hanzi16_bitmap(uint32_t codepoint)
{
  for (uint16_t i = 0; i < (sizeof(oled_hanzi16_glyphs) / sizeof(oled_hanzi16_glyphs[0])); ++i)
  {
    if (oled_hanzi16_glyphs[i].codepoint == codepoint)
    {
      return oled_hanzi16_glyphs[i].bitmap;
    }
  }

  return NULL;
}

static uint32_t utf8_next_codepoint(const char **str)
{
  const uint8_t *s = (const uint8_t *)(*str);
  uint32_t cp;

  if (s[0] < 0x80U)
  {
    *str += 1;
    return s[0];
  }
  if (((s[0] & 0xE0U) == 0xC0U) && ((s[1] & 0xC0U) == 0x80U))
  {
    cp = ((uint32_t)(s[0] & 0x1FU) << 6) | (uint32_t)(s[1] & 0x3FU);
    *str += 2;
    return cp;
  }
  if (((s[0] & 0xF0U) == 0xE0U) &&
      ((s[1] & 0xC0U) == 0x80U) &&
      ((s[2] & 0xC0U) == 0x80U))
  {
    cp = ((uint32_t)(s[0] & 0x0FU) << 12) |
         ((uint32_t)(s[1] & 0x3FU) << 6) |
         (uint32_t)(s[2] & 0x3FU);
    *str += 3;
    return cp;
  }

  *str += 1;
  return '?';
}

void OLED_DrawHanzi16(uint8_t x, uint8_t y, uint32_t codepoint)
{
  const uint8_t *bitmap = hanzi16_bitmap(codepoint);

  if (bitmap == NULL)
  {
    OLED_DrawChar(x, y, '?');
    return;
  }

  for (uint8_t row = 0; row < 16U; ++row)
  {
    uint16_t bits = ((uint16_t)bitmap[row * 2U] << 8) | bitmap[row * 2U + 1U];
    for (uint8_t col = 0; col < 16U; ++col)
    {
      OLED_DrawPixel((uint8_t)(x + col), (uint8_t)(y + row), (bits & (uint16_t)(0x8000U >> col)) ? 1U : 0U);
    }
  }
}

void OLED_DrawUTF8(uint8_t x, uint8_t y, const char *str)
{
  while ((str != NULL) && (*str != '\0'))
  {
    const char *before = str;
    uint32_t cp = utf8_next_codepoint(&str);
    uint8_t width = (cp < 0x80U) ? 6U : 16U;
    uint8_t height = (cp < 0x80U) ? 7U : 16U;

    if (x > (OLED_WIDTH - width))
    {
      x = 0U;
      y = (uint8_t)(y + 16U);
    }
    if (y > (OLED_HEIGHT - height))
    {
      return;
    }

    if (cp < 0x80U)
    {
      OLED_DrawChar(x, y, (char)cp);
    }
    else if (str != before)
    {
      OLED_DrawHanzi16(x, y, cp);
    }

    x = (uint8_t)(x + width);
  }
}

void OLED_DrawHLine(uint8_t x, uint8_t y, uint8_t w, uint8_t color)
{
  for (uint8_t i = 0; i < w; ++i)
  {
    OLED_DrawPixel((uint8_t)(x + i), y, color);
  }
}

void OLED_DrawVLine(uint8_t x, uint8_t y, uint8_t h, uint8_t color)
{
  for (uint8_t i = 0; i < h; ++i)
  {
    OLED_DrawPixel(x, (uint8_t)(y + i), color);
  }
}

void OLED_DrawRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t color)
{
  if ((w == 0U) || (h == 0U))
  {
    return;
  }

  OLED_DrawHLine(x, y, w, color);
  OLED_DrawHLine(x, (uint8_t)(y + h - 1U), w, color);
  OLED_DrawVLine(x, y, h, color);
  OLED_DrawVLine((uint8_t)(x + w - 1U), y, h, color);
}

void OLED_FillRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t color)
{
  for (uint8_t row = 0; row < h; ++row)
  {
    OLED_DrawHLine(x, (uint8_t)(y + row), w, color);
  }
}

void OLED_DrawBar(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t value, uint8_t max_value)
{
  uint8_t fill_w;

  if (max_value == 0U)
  {
    max_value = 1U;
  }
  if (value > max_value)
  {
    value = max_value;
  }

  OLED_DrawRect(x, y, w, h, 1U);
  if ((w <= 2U) || (h <= 2U))
  {
    return;
  }

  fill_w = (uint8_t)(((uint16_t)(w - 2U) * value) / max_value);
  if (fill_w > 0U)
  {
    OLED_FillRect((uint8_t)(x + 1U), (uint8_t)(y + 1U), fill_w, (uint8_t)(h - 2U), 1U);
  }
}
