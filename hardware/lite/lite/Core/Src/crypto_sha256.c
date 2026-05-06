#include "crypto_sha256.h"
#include <string.h>

typedef struct
{
  uint8_t data[64];
  uint32_t datalen;
  uint64_t bitlen;
  uint32_t state[8];
} Sha256Ctx;

static const uint32_t k[64] = {
  0x428a2f98UL, 0x71374491UL, 0xb5c0fbcfUL, 0xe9b5dba5UL,
  0x3956c25bUL, 0x59f111f1UL, 0x923f82a4UL, 0xab1c5ed5UL,
  0xd807aa98UL, 0x12835b01UL, 0x243185beUL, 0x550c7dc3UL,
  0x72be5d74UL, 0x80deb1feUL, 0x9bdc06a7UL, 0xc19bf174UL,
  0xe49b69c1UL, 0xefbe4786UL, 0x0fc19dc6UL, 0x240ca1ccUL,
  0x2de92c6fUL, 0x4a7484aaUL, 0x5cb0a9dcUL, 0x76f988daUL,
  0x983e5152UL, 0xa831c66dUL, 0xb00327c8UL, 0xbf597fc7UL,
  0xc6e00bf3UL, 0xd5a79147UL, 0x06ca6351UL, 0x14292967UL,
  0x27b70a85UL, 0x2e1b2138UL, 0x4d2c6dfcUL, 0x53380d13UL,
  0x650a7354UL, 0x766a0abbUL, 0x81c2c92eUL, 0x92722c85UL,
  0xa2bfe8a1UL, 0xa81a664bUL, 0xc24b8b70UL, 0xc76c51a3UL,
  0xd192e819UL, 0xd6990624UL, 0xf40e3585UL, 0x106aa070UL,
  0x19a4c116UL, 0x1e376c08UL, 0x2748774cUL, 0x34b0bcb5UL,
  0x391c0cb3UL, 0x4ed8aa4aUL, 0x5b9cca4fUL, 0x682e6ff3UL,
  0x748f82eeUL, 0x78a5636fUL, 0x84c87814UL, 0x8cc70208UL,
  0x90befffaUL, 0xa4506cebUL, 0xbef9a3f7UL, 0xc67178f2UL
};

static uint32_t rotr(uint32_t value, uint32_t bits)
{
  return (value >> bits) | (value << (32U - bits));
}

static void sha256_transform(Sha256Ctx *ctx, const uint8_t data[64])
{
  uint32_t a, b, c, d, e, f, g, h;
  uint32_t m[64];

  for (uint32_t i = 0; i < 16U; ++i)
  {
    m[i] = ((uint32_t)data[i * 4U] << 24) |
           ((uint32_t)data[i * 4U + 1U] << 16) |
           ((uint32_t)data[i * 4U + 2U] << 8) |
           ((uint32_t)data[i * 4U + 3U]);
  }
  for (uint32_t i = 16U; i < 64U; ++i)
  {
    uint32_t s0 = rotr(m[i - 15U], 7U) ^ rotr(m[i - 15U], 18U) ^ (m[i - 15U] >> 3);
    uint32_t s1 = rotr(m[i - 2U], 17U) ^ rotr(m[i - 2U], 19U) ^ (m[i - 2U] >> 10);
    m[i] = m[i - 16U] + s0 + m[i - 7U] + s1;
  }

  a = ctx->state[0];
  b = ctx->state[1];
  c = ctx->state[2];
  d = ctx->state[3];
  e = ctx->state[4];
  f = ctx->state[5];
  g = ctx->state[6];
  h = ctx->state[7];

  for (uint32_t i = 0; i < 64U; ++i)
  {
    uint32_t s1 = rotr(e, 6U) ^ rotr(e, 11U) ^ rotr(e, 25U);
    uint32_t ch = (e & f) ^ ((~e) & g);
    uint32_t temp1 = h + s1 + ch + k[i] + m[i];
    uint32_t s0 = rotr(a, 2U) ^ rotr(a, 13U) ^ rotr(a, 22U);
    uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
    uint32_t temp2 = s0 + maj;

    h = g;
    g = f;
    f = e;
    e = d + temp1;
    d = c;
    c = b;
    b = a;
    a = temp1 + temp2;
  }

  ctx->state[0] += a;
  ctx->state[1] += b;
  ctx->state[2] += c;
  ctx->state[3] += d;
  ctx->state[4] += e;
  ctx->state[5] += f;
  ctx->state[6] += g;
  ctx->state[7] += h;
}

static void sha256_init(Sha256Ctx *ctx)
{
  ctx->datalen = 0U;
  ctx->bitlen = 0ULL;
  ctx->state[0] = 0x6a09e667UL;
  ctx->state[1] = 0xbb67ae85UL;
  ctx->state[2] = 0x3c6ef372UL;
  ctx->state[3] = 0xa54ff53aUL;
  ctx->state[4] = 0x510e527fUL;
  ctx->state[5] = 0x9b05688cUL;
  ctx->state[6] = 0x1f83d9abUL;
  ctx->state[7] = 0x5be0cd19UL;
}

static void sha256_update(Sha256Ctx *ctx, const uint8_t *data, size_t len)
{
  for (size_t i = 0; i < len; ++i)
  {
    ctx->data[ctx->datalen] = data[i];
    ++ctx->datalen;
    if (ctx->datalen == 64U)
    {
      sha256_transform(ctx, ctx->data);
      ctx->bitlen += 512ULL;
      ctx->datalen = 0U;
    }
  }
}

static void sha256_final(Sha256Ctx *ctx, uint8_t hash[32])
{
  uint32_t i = ctx->datalen;

  ctx->data[i++] = 0x80U;
  if (ctx->datalen < 56U)
  {
    while (i < 56U)
    {
      ctx->data[i++] = 0x00U;
    }
  }
  else
  {
    while (i < 64U)
    {
      ctx->data[i++] = 0x00U;
    }
    sha256_transform(ctx, ctx->data);
    memset(ctx->data, 0, 56U);
  }

  ctx->bitlen += (uint64_t)ctx->datalen * 8ULL;
  ctx->data[63] = (uint8_t)(ctx->bitlen);
  ctx->data[62] = (uint8_t)(ctx->bitlen >> 8);
  ctx->data[61] = (uint8_t)(ctx->bitlen >> 16);
  ctx->data[60] = (uint8_t)(ctx->bitlen >> 24);
  ctx->data[59] = (uint8_t)(ctx->bitlen >> 32);
  ctx->data[58] = (uint8_t)(ctx->bitlen >> 40);
  ctx->data[57] = (uint8_t)(ctx->bitlen >> 48);
  ctx->data[56] = (uint8_t)(ctx->bitlen >> 56);
  sha256_transform(ctx, ctx->data);

  for (i = 0; i < 4U; ++i)
  {
    hash[i] = (uint8_t)(ctx->state[0] >> (24U - i * 8U));
    hash[i + 4U] = (uint8_t)(ctx->state[1] >> (24U - i * 8U));
    hash[i + 8U] = (uint8_t)(ctx->state[2] >> (24U - i * 8U));
    hash[i + 12U] = (uint8_t)(ctx->state[3] >> (24U - i * 8U));
    hash[i + 16U] = (uint8_t)(ctx->state[4] >> (24U - i * 8U));
    hash[i + 20U] = (uint8_t)(ctx->state[5] >> (24U - i * 8U));
    hash[i + 24U] = (uint8_t)(ctx->state[6] >> (24U - i * 8U));
    hash[i + 28U] = (uint8_t)(ctx->state[7] >> (24U - i * 8U));
  }
}

static char sha_hex_digit(uint8_t value)
{
  value &= 0x0FU;
  return (value < 10U) ? (char)('0' + value) : (char)('a' + value - 10U);
}

void hmac_sha256_hex(const uint8_t *key, size_t key_len,
                     const uint8_t *data, size_t data_len,
                     char out_hex[65])
{
  uint8_t key_block[64];
  uint8_t inner_hash[32];
  uint8_t digest[32];
  Sha256Ctx ctx;

  memset(key_block, 0, sizeof(key_block));
  if (key_len > sizeof(key_block))
  {
    sha256_init(&ctx);
    sha256_update(&ctx, key, key_len);
    sha256_final(&ctx, key_block);
  }
  else
  {
    memcpy(key_block, key, key_len);
  }

  for (uint32_t i = 0; i < sizeof(key_block); ++i)
  {
    key_block[i] ^= 0x36U;
  }
  sha256_init(&ctx);
  sha256_update(&ctx, key_block, sizeof(key_block));
  sha256_update(&ctx, data, data_len);
  sha256_final(&ctx, inner_hash);

  for (uint32_t i = 0; i < sizeof(key_block); ++i)
  {
    key_block[i] ^= (uint8_t)(0x36U ^ 0x5cU);
  }
  sha256_init(&ctx);
  sha256_update(&ctx, key_block, sizeof(key_block));
  sha256_update(&ctx, inner_hash, sizeof(inner_hash));
  sha256_final(&ctx, digest);

  for (uint32_t i = 0; i < sizeof(digest); ++i)
  {
    out_hex[i * 2U] = sha_hex_digit((uint8_t)(digest[i] >> 4));
    out_hex[i * 2U + 1U] = sha_hex_digit(digest[i]);
  }
  out_hex[64] = '\0';
}
