/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32h7xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

#include <stdint.h>

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

extern I2C_HandleTypeDef hi2c1;
extern UART_HandleTypeDef huart4;
extern UART_HandleTypeDef huart1;
extern SPI_HandleTypeDef hspi1;

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/

#define LORA_DIO0_Pin GPIO_PIN_4
#define LORA_DIO0_GPIO_Port GPIOB
#define LORA_RESET_Pin GPIO_PIN_5
#define LORA_RESET_GPIO_Port GPIOB
#define LORA_NSS_Pin GPIO_PIN_6
#define LORA_NSS_GPIO_Port GPIOB
#define STATUS_LED_Pin GPIO_PIN_0
#define STATUS_LED_GPIO_Port GPIOB

#define SHT31_I2C_ADDR (0x44U << 1)
#define ATECC608A_I2C_ADDR (0x60U << 1)
#define DS3231_I2C_ADDR (0x68U << 1)

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
