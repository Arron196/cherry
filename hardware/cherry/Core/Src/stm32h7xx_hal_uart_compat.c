#include "stm32h7xx_hal.h"

static uint32_t uart_get_clock(UART_HandleTypeDef *huart) {
  if (huart->Instance == USART1 || huart->Instance == USART6) {
    return HAL_RCC_GetPCLK2Freq();
  }
  return HAL_RCC_GetPCLK1Freq();
}

HAL_StatusTypeDef HAL_UART_Init(UART_HandleTypeDef *huart) {
  if (huart == NULL || huart->Instance == NULL || huart->Init.BaudRate == 0U) {
    return HAL_ERROR;
  }

  HAL_UART_MspInit(huart);

  huart->Instance->CR1 &= ~USART_CR1_UE;
  huart->Instance->CR1 = 0U;
  huart->Instance->CR2 = 0U;
  huart->Instance->CR3 = 0U;

  huart->Instance->BRR = uart_get_clock(huart) / huart->Init.BaudRate;
  huart->Instance->CR1 |= USART_CR1_TE | USART_CR1_RE;
  huart->Instance->CR1 |= USART_CR1_UE;

  huart->gState = HAL_UART_STATE_READY;
  huart->RxState = HAL_UART_STATE_READY;
  huart->ErrorCode = HAL_UART_ERROR_NONE;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_UART_DeInit(UART_HandleTypeDef *huart) {
  if (huart == NULL || huart->Instance == NULL) {
    return HAL_ERROR;
  }
  huart->Instance->CR1 &= ~USART_CR1_UE;
  HAL_UART_MspDeInit(huart);
  huart->gState = HAL_UART_STATE_RESET;
  huart->RxState = HAL_UART_STATE_RESET;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_UART_Transmit(UART_HandleTypeDef *huart, uint8_t *pData,
                                    uint16_t Size, uint32_t Timeout) {
  uint32_t start = HAL_GetTick();
  if (huart == NULL || pData == NULL) {
    return HAL_ERROR;
  }

  for (uint16_t i = 0U; i < Size; ++i) {
    while ((huart->Instance->ISR & USART_ISR_TXE_TXFNF) == 0U) {
      if ((HAL_GetTick() - start) > Timeout) {
        return HAL_TIMEOUT;
      }
    }
    huart->Instance->TDR = pData[i];
  }

  while ((huart->Instance->ISR & USART_ISR_TC) == 0U) {
    if ((HAL_GetTick() - start) > Timeout) {
      return HAL_TIMEOUT;
    }
  }

  return HAL_OK;
}

HAL_StatusTypeDef HAL_UART_Receive(UART_HandleTypeDef *huart, uint8_t *pData,
                                   uint16_t Size, uint32_t Timeout) {
  uint32_t start = HAL_GetTick();
  if (huart == NULL || pData == NULL) {
    return HAL_ERROR;
  }

  for (uint16_t i = 0U; i < Size; ++i) {
    while ((huart->Instance->ISR & USART_ISR_RXNE_RXFNE) == 0U) {
      if ((HAL_GetTick() - start) > Timeout) {
        return HAL_TIMEOUT;
      }
    }
    pData[i] = (uint8_t)(huart->Instance->RDR & 0xFFU);
  }

  return HAL_OK;
}

void HAL_UART_IRQHandler(UART_HandleTypeDef *huart) {
  if (huart == NULL || huart->Instance == NULL) {
    return;
  }
  if ((huart->Instance->ISR & USART_ISR_ORE) != 0U) {
    huart->Instance->ICR = USART_ICR_ORECF;
  }
}

HAL_StatusTypeDef HAL_UARTEx_SetTxFifoThreshold(UART_HandleTypeDef *huart,
                                                uint32_t Threshold) {
  (void)huart;
  (void)Threshold;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_UARTEx_SetRxFifoThreshold(UART_HandleTypeDef *huart,
                                                uint32_t Threshold) {
  (void)huart;
  (void)Threshold;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_UARTEx_DisableFifoMode(UART_HandleTypeDef *huart) {
  (void)huart;
  return HAL_OK;
}
