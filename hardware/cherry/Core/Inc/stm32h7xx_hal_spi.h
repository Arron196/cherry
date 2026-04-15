#ifndef STM32H7XX_HAL_SPI_H
#define STM32H7XX_HAL_SPI_H

#include "stm32h7xx_hal_def.h"

typedef struct {
  uint32_t Mode;
  uint32_t Direction;
  uint32_t DataSize;
  uint32_t CLKPolarity;
  uint32_t CLKPhase;
  uint32_t NSS;
  uint32_t BaudRatePrescaler;
  uint32_t FirstBit;
  uint32_t TIMode;
  uint32_t CRCCalculation;
  uint32_t CRCPolynomial;
  uint32_t NSSPMode;
  uint32_t NSSPolarity;
  uint32_t FifoThreshold;
  uint32_t TxCRCInitializationPattern;
  uint32_t RxCRCInitializationPattern;
  uint32_t MasterSSIdleness;
  uint32_t MasterInterDataIdleness;
  uint32_t MasterReceiverAutoSusp;
  uint32_t MasterKeepIOState;
  uint32_t IOSwap;
} SPI_InitTypeDef;

typedef struct {
  SPI_TypeDef *Instance;
  SPI_InitTypeDef Init;
  HAL_LockTypeDef Lock;
  __IO uint32_t State;
} SPI_HandleTypeDef;

#define SPI_MODE_MASTER 0x00000001U
#define SPI_DIRECTION_2LINES 0x00000000U
#define SPI_DATASIZE_8BIT 0x00000007U
#define SPI_POLARITY_LOW 0x00000000U
#define SPI_PHASE_1EDGE 0x00000000U
#define SPI_NSS_SOFT 0x00000000U
#define SPI_BAUDRATEPRESCALER_32 0x00000004U
#define SPI_FIRSTBIT_MSB 0x00000000U
#define SPI_TIMODE_DISABLE 0x00000000U
#define SPI_CRCCALCULATION_DISABLE 0x00000000U
#define SPI_NSS_PULSE_DISABLE 0x00000000U
#define SPI_NSS_POLARITY_LOW 0x00000000U
#define SPI_FIFO_THRESHOLD_01DATA 0x00000000U
#define SPI_CRC_INITIALIZATION_ALL_ZERO_PATTERN 0x00000000U
#define SPI_MASTER_SS_IDLENESS_00CYCLE 0x00000000U
#define SPI_MASTER_INTERDATA_IDLENESS_00CYCLE 0x00000000U
#define SPI_MASTER_RX_AUTOSUSP_DISABLE 0x00000000U
#define SPI_MASTER_KEEP_IO_STATE_DISABLE 0x00000000U
#define SPI_IO_SWAP_DISABLE 0x00000000U

HAL_StatusTypeDef HAL_SPI_Init(SPI_HandleTypeDef *hspi);
HAL_StatusTypeDef HAL_SPI_DeInit(SPI_HandleTypeDef *hspi);
HAL_StatusTypeDef HAL_SPI_Transmit(SPI_HandleTypeDef *hspi, uint8_t *pData,
                                   uint16_t Size, uint32_t Timeout);

void HAL_SPI_MspInit(SPI_HandleTypeDef *hspi);
void HAL_SPI_MspDeInit(SPI_HandleTypeDef *hspi);

#endif
