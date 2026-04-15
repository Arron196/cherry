#ifndef CHERRY_HW_H
#define CHERRY_HW_H

#include <stdbool.h>
#include <stdint.h>

#include "main.h"

typedef struct {
  uint32_t unix_time;
  float temperature_c;
  float humidity_rh;
  uint16_t co2_ppm;
  bool vibration_alarm;
  bool rtc_valid;
  bool env_valid;
  bool co2_valid;
} CherrySensorSnapshot;

typedef struct {
  CherrySensorSnapshot snapshot;
  uint8_t digest[32];
  uint8_t signature[64];
  uint8_t signature_len;
  uint32_t sequence;
  bool signature_from_secure_element;
} CherrySignedPacket;

HAL_StatusTypeDef CherryHw_Init(void);
HAL_StatusTypeDef CherryHw_ReadSensors(CherrySensorSnapshot *out);
HAL_StatusTypeDef CherryHw_SignSnapshot(const CherrySensorSnapshot *in,
                                        uint32_t sequence,
                                        CherrySignedPacket *out);
HAL_StatusTypeDef CherryHw_SendViaWiFi(const CherrySignedPacket *packet);
HAL_StatusTypeDef CherryHw_SendViaLoRa(const CherrySignedPacket *packet);
void CherryHw_OnLoRaDio0Rise(void);

#endif
