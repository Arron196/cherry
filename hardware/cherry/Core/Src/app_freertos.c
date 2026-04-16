#include "app_freertos.h"

#include "cherry_hw.h"

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

typedef struct {
  CherrySignedPacket packet;
  uint8_t retry_count;
} TxEnvelope;

static QueueHandle_t g_sensor_queue;
static QueueHandle_t g_tx_queue;
static QueueHandle_t g_retry_queue;
static uint32_t g_sequence;

static void SensorTask(void *argument);
static void SignTask(void *argument);
static void TransportTask(void *argument);
static void RetryTask(void *argument);

void MX_FREERTOS_Init(void) {
  g_sensor_queue = xQueueCreate(8U, sizeof(CherrySensorSnapshot));
  g_tx_queue = xQueueCreate(8U, sizeof(TxEnvelope));
  g_retry_queue = xQueueCreate(8U, sizeof(TxEnvelope));

  (void)CherryHw_Init();

  xTaskCreate(SensorTask, "sensor", 512U, NULL, 3U, NULL);
  xTaskCreate(SignTask, "sign", 768U, NULL, 4U, NULL);
  xTaskCreate(TransportTask, "tx", 768U, NULL, 2U, NULL);
  xTaskCreate(RetryTask, "retry", 512U, NULL, 1U, NULL);
}

static void SensorTask(void *argument) {
  (void)argument;
  TickType_t last_wake = xTaskGetTickCount();

  for (;;) {
    CherrySensorSnapshot snapshot;
    (void)CherryHw_ReadSensors(&snapshot);
    (void)xQueueSend(g_sensor_queue, &snapshot, 0U);
    vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(5000U));
  }
}

static void SignTask(void *argument) {
  (void)argument;

  for (;;) {
    CherrySensorSnapshot snapshot;
    if (xQueueReceive(g_sensor_queue, &snapshot, portMAX_DELAY) == pdPASS) {
      TxEnvelope envelope;
      envelope.retry_count = 0U;
      (void)CherryHw_SignSnapshot(&snapshot, g_sequence++, &envelope.packet);
      (void)xQueueSend(g_tx_queue, &envelope, portMAX_DELAY);
    }
  }
}

static void TransportTask(void *argument) {
  (void)argument;

  for (;;) {
    TxEnvelope envelope;
    if (xQueueReceive(g_tx_queue, &envelope, portMAX_DELAY) == pdPASS) {
      HAL_StatusTypeDef wifi = CherryHw_SendViaWiFi(&envelope.packet);
      HAL_StatusTypeDef lora = CherryHw_SendViaLoRa(&envelope.packet);

      if (wifi == HAL_OK && lora == HAL_OK) {
        HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin, GPIO_PIN_SET);
      } else {
        HAL_GPIO_WritePin(STATUS_LED_GPIO_Port, STATUS_LED_Pin, GPIO_PIN_RESET);
        if (envelope.retry_count < 3U) {
          envelope.retry_count++;
          (void)xQueueSend(g_retry_queue, &envelope, 0U);
        }
      }
    }
  }
}

static void RetryTask(void *argument) {
  (void)argument;

  for (;;) {
    TxEnvelope envelope;
    if (xQueueReceive(g_retry_queue, &envelope, portMAX_DELAY) == pdPASS) {
      vTaskDelay(pdMS_TO_TICKS(2000U));
      (void)xQueueSend(g_tx_queue, &envelope, portMAX_DELAY);
    }
  }
}

void vApplicationStackOverflowHook(TaskHandle_t xTask,
                                   char *pcTaskName) {
  (void)xTask;
  (void)pcTaskName;
  taskDISABLE_INTERRUPTS();
  for (;;) {
  }
}
