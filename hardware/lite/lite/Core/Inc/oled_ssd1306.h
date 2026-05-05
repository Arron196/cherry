#ifndef OLED_SSD1306_H
#define OLED_SSD1306_H

#include "stm32f1xx_hal.h"
#include <stdint.h>

#define OLED_WIDTH 128U
#define OLED_HEIGHT 64U

HAL_StatusTypeDef OLED_Init(I2C_HandleTypeDef *hi2c);
HAL_StatusTypeDef OLED_ProbeI2C(uint8_t address7);
void OLED_Clear(void);
void OLED_Fill(uint8_t pattern);
void OLED_Update(void);
void OLED_DrawPixel(uint8_t x, uint8_t y, uint8_t color);
void OLED_DrawChar(uint8_t x, uint8_t y, char ch);
void OLED_DrawString(uint8_t x, uint8_t y, const char *str);
void OLED_DrawHanzi16(uint8_t x, uint8_t y, uint32_t codepoint);
void OLED_DrawUTF8(uint8_t x, uint8_t y, const char *str);
void OLED_DrawHLine(uint8_t x, uint8_t y, uint8_t w, uint8_t color);
void OLED_DrawVLine(uint8_t x, uint8_t y, uint8_t h, uint8_t color);
void OLED_DrawRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t color);
void OLED_FillRect(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t color);
void OLED_DrawBar(uint8_t x, uint8_t y, uint8_t w, uint8_t h, uint8_t value, uint8_t max_value);

#endif /* OLED_SSD1306_H */
