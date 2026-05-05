#ifndef TRACE_APP_H
#define TRACE_APP_H

#include "stm32f1xx_hal.h"

void TraceApp_Init(I2C_HandleTypeDef *hi2c, SPI_HandleTypeDef *hspi, TIM_HandleTypeDef *htim);
void TraceApp_StartScheduler(void);
void TraceApp_IR_EdgeCallback(uint16_t gpio_pin);

#endif /* TRACE_APP_H */
