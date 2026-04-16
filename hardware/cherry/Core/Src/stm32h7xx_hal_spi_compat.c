#include "stm32h7xx_hal.h"

HAL_StatusTypeDef HAL_SPI_Init(SPI_HandleTypeDef *hspi) {
  if (hspi == NULL || hspi->Instance == NULL) {
    return HAL_ERROR;
  }
  HAL_SPI_MspInit(hspi);
  hspi->State = 0U;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_SPI_DeInit(SPI_HandleTypeDef *hspi) {
  if (hspi == NULL || hspi->Instance == NULL) {
    return HAL_ERROR;
  }
  HAL_SPI_MspDeInit(hspi);
  hspi->State = 0U;
  return HAL_OK;
}

HAL_StatusTypeDef HAL_SPI_Transmit(SPI_HandleTypeDef *hspi, uint8_t *pData,
                                   uint16_t Size, uint32_t Timeout) {
  uint32_t start = HAL_GetTick();
  if (hspi == NULL || pData == NULL || Size == 0U) {
    return HAL_ERROR;
  }

  for (uint16_t i = 0U; i < Size; ++i) {
    uint8_t data = pData[i];
    for (uint8_t b = 0U; b < 8U; ++b) {
      HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7,
                        (data & 0x80U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
      HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
      HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
      data <<= 1U;
    }

    if ((HAL_GetTick() - start) > Timeout) {
      return HAL_TIMEOUT;
    }
  }

  return HAL_OK;
}
