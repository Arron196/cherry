#ifndef CRYPTO_SHA256_H
#define CRYPTO_SHA256_H

#include <stddef.h>
#include <stdint.h>

void hmac_sha256_hex(const uint8_t *key, size_t key_len,
                     const uint8_t *data, size_t data_len,
                     char out_hex[65]);

#endif /* CRYPTO_SHA256_H */
