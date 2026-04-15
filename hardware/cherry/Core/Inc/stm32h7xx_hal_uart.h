#ifndef STM32H7XX_HAL_UART_H
#define STM32H7XX_HAL_UART_H

#include "stm32h7xx_hal_def.h"

typedef struct {
  uint32_t BaudRate;
  uint32_t WordLength;
  uint32_t StopBits;
  uint32_t Parity;
  uint32_t Mode;
  uint32_t HwFlowCtl;
  uint32_t OverSampling;
  uint32_t OneBitSampling;
  uint32_t ClockPrescaler;
} UART_InitTypeDef;

typedef struct {
  uint32_t AdvFeatureInit;
} UART_AdvFeatureInitTypeDef;

typedef enum {
  HAL_UART_STATE_RESET = 0x00U,
  HAL_UART_STATE_READY = 0x20U,
  HAL_UART_STATE_BUSY = 0x24U,
  HAL_UART_STATE_BUSY_TX = 0x21U,
  HAL_UART_STATE_BUSY_RX = 0x22U,
  HAL_UART_STATE_TIMEOUT = 0xA0U,
  HAL_UART_STATE_ERROR = 0xE0U
} HAL_UART_StateTypeDef;

typedef struct {
  USART_TypeDef *Instance;
  UART_InitTypeDef Init;
  UART_AdvFeatureInitTypeDef AdvancedInit;
  HAL_LockTypeDef Lock;
  __IO HAL_UART_StateTypeDef gState;
  __IO HAL_UART_StateTypeDef RxState;
  uint32_t ErrorCode;
} UART_HandleTypeDef;

#define HAL_UART_ERROR_NONE 0x00000000U

#define UART_WORDLENGTH_8B 0x00000000U
#define UART_STOPBITS_1 0x00000000U
#define UART_PARITY_NONE 0x00000000U
#define UART_MODE_TX_RX 0x0000000CU
#define UART_HWCONTROL_NONE 0x00000000U
#define UART_OVERSAMPLING_16 0x00000000U
#define UART_ONE_BIT_SAMPLE_DISABLE 0x00000000U
#define UART_PRESCALER_DIV1 0x00000000U
#define UART_ADVFEATURE_NO_INIT 0x00000000U
#define UART_TXFIFO_THRESHOLD_1_8 0x00000000U
#define UART_RXFIFO_THRESHOLD_1_8 0x00000000U

HAL_StatusTypeDef HAL_UART_Init(UART_HandleTypeDef *huart);
HAL_StatusTypeDef HAL_UART_DeInit(UART_HandleTypeDef *huart);
HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart, uint8_t *pData,
                                    uint16_t Size, uint32_t Timeout);
HAL_StatusTypeDef HAL_UART_Receive(UART_HandleTypeDef *huart, uint8_t *pData,
                                   uint16_t Size, uint32_t Timeout);
void HAL_UART_IRQHandler(UART_HandleTypeDef *huart);
HAL_StatusTypeDef HAL_UARTEx_SetTxFifoThreshold(UART_HandleTypeDef *huart,
                                                uint32_t Threshold);
HAL_StatusTypeDef HAL_UARTEx_SetRxFifoThreshold(UART_HandleTypeDef *huart,
                                                uint32_t Threshold);
HAL_StatusTypeDef HAL_UARTEx_DisableFifoMode(UART_HandleTypeDef *huart);

void HAL_UART_MspInit(UART_HandleTypeDef *huart);
void HAL_UART_MspDeInit(UART_HandleTypeDef *huart);

#endif
