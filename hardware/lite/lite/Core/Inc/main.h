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
#include "stm32f1xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

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

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define OLED_SCL_Pin GPIO_PIN_6
#define OLED_SCL_GPIO_Port GPIOB
#define AT24C08_SCL_Pin GPIO_PIN_6
#define AT24C08_SCL_GPIO_Port GPIOB
#define OLED_SDA_Pin GPIO_PIN_7
#define OLED_SDA_GPIO_Port GPIOB
#define AT24C08_SDA_Pin GPIO_PIN_7
#define AT24C08_SDA_GPIO_Port GPIOB
#define W25Q32_CS_Pin GPIO_PIN_4
#define W25Q32_CS_GPIO_Port GPIOA
#define W25Q32_SCK_Pin GPIO_PIN_5
#define W25Q32_SCK_GPIO_Port GPIOA
#define W25Q32_MISO_Pin GPIO_PIN_6
#define W25Q32_MISO_GPIO_Port GPIOA
#define W25Q32_MOSI_Pin GPIO_PIN_7
#define W25Q32_MOSI_GPIO_Port GPIOA
#define BT_TX_TO_MCU_RX_Pin GPIO_PIN_10
#define BT_TX_TO_MCU_RX_GPIO_Port GPIOA
#define BT_RX_TO_MCU_TX_Pin GPIO_PIN_9
#define BT_RX_TO_MCU_TX_GPIO_Port GPIOA
#define ESP8266_TX_TO_MCU_RX_Pin GPIO_PIN_11
#define ESP8266_TX_TO_MCU_RX_GPIO_Port GPIOB
#define ESP8266_RX_TO_MCU_TX_Pin GPIO_PIN_10
#define ESP8266_RX_TO_MCU_TX_GPIO_Port GPIOB
#define ESP8266_EN_Pin GPIO_PIN_12
#define ESP8266_EN_GPIO_Port GPIOB
#define ESP8266_RST_Pin GPIO_PIN_13
#define ESP8266_RST_GPIO_Port GPIOB
#define DHT11_DATA_Pin GPIO_PIN_0
#define DHT11_DATA_GPIO_Port GPIOB
#define DS18B20_DATA_Pin GPIO_PIN_1
#define DS18B20_DATA_GPIO_Port GPIOB
#define BUZZER_Pin GPIO_PIN_8
#define BUZZER_GPIO_Port GPIOA
#define IR_RX_Pin GPIO_PIN_0
#define IR_RX_GPIO_Port GPIOA
#define IR_RX_EXTI_IRQn EXTI0_IRQn
#define STATUS_LED_Pin GPIO_PIN_13
#define STATUS_LED_GPIO_Port GPIOC

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
