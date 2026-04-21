/*
 * codec_core.c — Ultra-fast VDAT/VTXT Codec Engine
 * =============================================================
 * Compiled as a shared library (.dll/.so) and called from
 * Python via ctypes.
 *
 * Functions exported
 * ──────────────────
 *  fast_crc32            — CRC-32 via 256-entry lookup table
 *  float32_array_to_hex  — float32[] → uppercase hex string
 *  hex_to_float32_array  — uppercase/lowercase hex → float32[]
 *  frame_crc32           — CRC-32 over a packed .vdat frame
 *                          (big-endian struct BIdIBBI + payload)
 *  batch_hex_encode      — encode N frames payload in one call
 *  batch_hex_decode      — decode N frames hex in one call
 *
 * Build
 * ─────
 *  Windows (MinGW):   gcc -O3 -shared -o codec_core.dll codec_core.c
 *  Linux / macOS:     gcc -O3 -shared -fPIC -o codec_core.so codec_core.c
 *
 * Run  build_codec.py  — it auto-detects the compiler.
 * =============================================================
 */

#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* Windows DLL export */
#ifdef _WIN32
  #define EXPORT __declspec(dllexport)
#else
  #define EXPORT __attribute__((visibility("default")))
#endif

/* ─── CRC-32 (IEEE 802.3 / zlib polynomial) ─────────────────
 * Identical result to Python's:   zlib.crc32(data) & 0xFFFFFFFF
 * Uses a 256-entry table — fastest software CRC-32.
 */
static uint32_t CRC_TABLE[256];
static int      CRC_READY = 0;

static void _init_crc(void) {
    for (int i = 0; i < 256; i++) {
        uint32_t c = (uint32_t)i;
        for (int j = 0; j < 8; j++)
            c = (c & 1u) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        CRC_TABLE[i] = c;
    }
    CRC_READY = 1;
}

EXPORT uint32_t fast_crc32(const uint8_t *data, uint32_t len) {
    if (!CRC_READY) _init_crc();
    uint32_t crc = 0xFFFFFFFFu;
    for (uint32_t i = 0; i < len; i++)
        crc = CRC_TABLE[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

/* ─── Hex lookup tables ──────────────────────────────────────
 * Encode: 4-bit nibble → ASCII hex char  (O(1) per nibble)
 * Decode: ASCII hex char → 4-bit value   (O(1) per char)
 */
static const char HEX_ENC[16] = "0123456789ABCDEF";

static const int8_t HEX_DEC[256] = {
/*       0    1    2    3    4    5    6    7    8    9    A    B    C    D    E    F */
/* 00 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 10 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 20 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 30 */  0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  -1,  -1,  -1,  -1,  -1,  -1,
/* 40 */ -1,  10,  11,  12,  13,  14,  15,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 50 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 60 */ -1,  10,  11,  12,  13,  14,  15,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 70 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 80 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* 90 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* A0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* B0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* C0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* D0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* E0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
/* F0 */ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,
};

/* ─── float32 <─> hex (the main hot path) ────────────────────
 *
 * float32_array_to_hex
 *   samples   : float32 array (little-endian bytes as-is)
 *   n_floats  : number of float values
 *   out_hex   : caller buffer of at least n_floats*8 + 1 bytes
 *
 * hex_to_float32_array
 *   hex_str   : exactly n_floats*8 ASCII hex chars (upper or lower)
 *   n_floats  : number of float values to decode
 *   out_samples: caller buffer of at least n_floats floats
 *   Returns 0 on success, -1 if invalid hex char encountered
 */
EXPORT void float32_array_to_hex(
    const float *samples,
    int          n_floats,
    char        *out_hex
) {
    const uint8_t *b = (const uint8_t *)samples;
    int nb = n_floats * 4;
    char *p = out_hex;
    /* Unrolled 2-at-a-time for ~5% extra throughput */
    int i = 0;
    for (; i + 1 < nb; i += 2) {
        uint8_t b0 = b[i], b1 = b[i+1];
        *p++ = HEX_ENC[b0 >> 4];  *p++ = HEX_ENC[b0 & 0xF];
        *p++ = HEX_ENC[b1 >> 4];  *p++ = HEX_ENC[b1 & 0xF];
    }
    for (; i < nb; i++) {
        uint8_t b0 = b[i];
        *p++ = HEX_ENC[b0 >> 4];  *p++ = HEX_ENC[b0 & 0xF];
    }
    *p = '\0';
}

EXPORT int hex_to_float32_array(
    const char *hex_str,
    int         n_floats,
    float      *out_samples
) {
    uint8_t    *b  = (uint8_t *)out_samples;
    int         nb = n_floats * 4;
    const char *p  = hex_str;
    for (int i = 0; i < nb; i++) {
        int8_t hi = HEX_DEC[(uint8_t)*p++];
        int8_t lo = HEX_DEC[(uint8_t)*p++];
        if (hi < 0 || lo < 0) return -1;
        b[i] = (uint8_t)((hi << 4) | lo);
    }
    return 0;
}

/* ─── Frame CRC-32 ───────────────────────────────────────────
 * Reproduces exactly:
 *   struct.pack(">BIdIBBI", ver, fid, ts_ms, sr, ch, bd, plen)
 *   + payload_bytes
 * and runs fast_crc32 over the concatenation.
 *
 *  Struct layout  (23 bytes big-endian):
 *    B  version     1 byte
 *    I  frame_id    4 bytes  big-endian uint32
 *    d  timestamp   8 bytes  big-endian IEEE-754 double
 *    I  sample_rate 4 bytes  big-endian uint32
 *    B  channels    1 byte
 *    B  bit_depth   1 byte
 *    I  payload_len 4 bytes  big-endian uint32
 */
EXPORT uint32_t frame_crc32(
    uint8_t  version,
    uint32_t frame_id,
    double   timestamp_ms,
    uint32_t sample_rate,
    uint8_t  channels,
    uint8_t  bit_depth,
    uint32_t payload_len,
    const uint8_t *payload,
    uint32_t payload_size
) {
    uint8_t hdr[23];

    hdr[0] = version;

    hdr[1] = (frame_id >> 24) & 0xFF;
    hdr[2] = (frame_id >> 16) & 0xFF;
    hdr[3] = (frame_id >>  8) & 0xFF;
    hdr[4] =  frame_id        & 0xFF;

    uint64_t ts_u;
    memcpy(&ts_u, &timestamp_ms, 8);
    hdr[5]  = (uint8_t)((ts_u >> 56) & 0xFF);
    hdr[6]  = (uint8_t)((ts_u >> 48) & 0xFF);
    hdr[7]  = (uint8_t)((ts_u >> 40) & 0xFF);
    hdr[8]  = (uint8_t)((ts_u >> 32) & 0xFF);
    hdr[9]  = (uint8_t)((ts_u >> 24) & 0xFF);
    hdr[10] = (uint8_t)((ts_u >> 16) & 0xFF);
    hdr[11] = (uint8_t)((ts_u >>  8) & 0xFF);
    hdr[12] = (uint8_t)( ts_u        & 0xFF);

    hdr[13] = (sample_rate >> 24) & 0xFF;
    hdr[14] = (sample_rate >> 16) & 0xFF;
    hdr[15] = (sample_rate >>  8) & 0xFF;
    hdr[16] =  sample_rate        & 0xFF;

    hdr[17] = channels;
    hdr[18] = bit_depth;

    hdr[19] = (payload_len >> 24) & 0xFF;
    hdr[20] = (payload_len >> 16) & 0xFF;
    hdr[21] = (payload_len >>  8) & 0xFF;
    hdr[22] =  payload_len        & 0xFF;

    if (!CRC_READY) _init_crc();
    uint32_t crc = 0xFFFFFFFFu;
    for (int i = 0; i < 23; i++)
        crc = CRC_TABLE[(crc ^ hdr[i]) & 0xFF] ^ (crc >> 8);
    for (uint32_t i = 0; i < payload_size; i++)
        crc = CRC_TABLE[(crc ^ payload[i]) & 0xFF] ^ (crc >> 8);
    return crc ^ 0xFFFFFFFFu;
}

/* ─── Batch encode: float32 buffer → hex buffer ──────────────
 *
 * Encodes n_frames frames at once.
 * All frames assumed to have the same samples_per_frame.
 *
 * in_floats : contiguous float32 array of n_frames * samples_per_frame floats
 * n_frames  : number of frames
 * spf       : samples per frame
 * out_hex   : buffer of at least n_frames * (spf*8 + 1) bytes
 *              Row i starts at out_hex + i * (spf*8 + 1)
 *              Each row is a NUL-terminated hex string.
 * stride    : spf * 8 + 1  (pass this from Python for safety)
 */
EXPORT void batch_hex_encode(
    const float *in_floats,
    int          n_frames,
    int          spf,
    char        *out_hex,
    int          stride
) {
    int nb_frame = spf * 4;
    for (int f = 0; f < n_frames; f++) {
        const uint8_t *b = (const uint8_t *)(in_floats + f * spf);
        char          *p = out_hex + (size_t)f * stride;
        for (int i = 0; i < nb_frame; i++) {
            *p++ = HEX_ENC[b[i] >> 4];
            *p++ = HEX_ENC[b[i] & 0xF];
        }
        *p = '\0';
    }
}

/* ─── Batch decode: hex buffer → float32 buffer ──────────────
 *
 * Decodes n_frames hex rows into contiguous float32 array.
 * in_hex   : same layout as out_hex from batch_hex_encode
 * Returns 0 on success, frame index (1-based) of first error
 */
EXPORT int batch_hex_decode(
    const char *in_hex,
    int         n_frames,
    int         spf,
    float      *out_floats,
    int         stride
) {
    int nb_frame = spf * 4;
    for (int f = 0; f < n_frames; f++) {
        const char *p = in_hex + (size_t)f * stride;
        uint8_t   *b  = (uint8_t *)(out_floats + f * spf);
        for (int i = 0; i < nb_frame; i++) {
            int8_t hi = HEX_DEC[(uint8_t)*p++];
            int8_t lo = HEX_DEC[(uint8_t)*p++];
            if (hi < 0 || lo < 0) return f + 1;
            b[i] = (uint8_t)((hi << 4) | lo);
        }
    }
    return 0;
}
