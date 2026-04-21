# WavCore — Architecture & Technical Reference

> **How WavCore is built, how it works internally, and what technologies power it.**

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [The VTXT Format — Detailed Specification](#the-vtxt-format)
5. [The C Engine — codec_core.c](#the-c-engine)
6. [Pipeline Workflow](#pipeline-workflow)
7. [Engine Tier System](#engine-tier-system)
8. [CRC-32 Frame Integrity](#crc-32-frame-integrity)
9. [Build System](#build-system)
10. [Data Flow Diagrams](#data-flow-diagrams)

---

## Overview

WavCore is a **lossless, real-time voice codec** built using:

- A **C language core** (`codec_core.c`) compiled via **cffi / MSVC** into a 64-bit Python extension
- A **Python bridge layer** (`codec.py`) that wraps the C engine with a clean Python API
- A **VTXT text format** — a human-readable, line-based audio serialization format
- A **tri-tier fallback engine** — if C is unavailable, Python internally uses C-backed functions

The system was designed with three non-negotiable requirements:

| Requirement | How it is met |
|---|---|
| **Zero data loss** | IEEE-754 hex encoding — no decimal rounding ever |
| **Real-time speed** | C batch functions process 500 frames in one call |
| **Frame integrity** | CRC-32 per frame, computed and verified in C |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        wavcore package                       │
│                                                             │
│  ┌──────────────┐        ┌─────────────────────────────┐  │
│  │  recorder.py │        │       converter.py           │  │
│  │              │        │                              │  │
│  │  Microphone  │        │  voice_data.vtxt  (input)   │  │
│  │      |       │        │         |                    │  │
│  │  sounddevice │        │   _parse_vtxt()              │  │
│  │      |       │        │         |                    │  │
│  │  float32[]   │        │   batch_decode() [C]         │  │
│  │      |       │        │         |                    │  │
│  │  batch_encode│        │   CRC verify [C]             │  │
│  │     [C]      │        │         |                    │  │
│  │      |       │        │   float32[] → WAV            │  │
│  │  CRC-32 [C]  │        │         |                    │  │
│  │      |       │        │   sounddevice playback       │  │
│  │  .vtxt file  │        └─────────────────────────────┘  │
│  └──────────────┘                                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   _codec/codec.py                    │   │
│  │                                                      │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │  Tier 1: wavcore._codec._codec_core (cffi)    │  │   │
│  │  │  MSVC 64-bit .pyd — compiled during pip       │  │   │
│  │  │  install — fastest (~9 µs/frame decode)       │  │   │
│  │  └───────────────────────┬───────────────────────┘  │   │
│  │                          │ fallback                  │   │
│  │  ┌───────────────────────▼───────────────────────┐  │   │
│  │  │  Tier 2: _codec_cffi (local cffi .pyd)        │  │   │
│  │  │  Built manually via build_codec.py            │  │   │
│  │  └───────────────────────┬───────────────────────┘  │   │
│  │                          │ fallback                  │   │
│  │  ┌───────────────────────▼───────────────────────┐  │   │
│  │  │  Tier 3: Pure Python (binascii + numpy)       │  │   │
│  │  │  Python .hex()/.fromhex() are C-backed        │  │   │
│  │  │  ~5.4ms / 500 frames — still real-time fast   │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Audio capture | `sounddevice` (PortAudio) | Cross-platform, low-latency mic access |
| Array math | `numpy` | C-backed float32 array operations |
| C compilation | `cffi` + MSVC/GCC | Compiles C into Python extension (.pyd/.so) |
| C interop | `ctypes` | Fallback DLL loader if cffi .pyd unavailable |
| Hex encoding | `binascii.hexlify` | C-implemented inside CPython |
| Integrity | CRC-32 (table-driven C) | 8× faster than Python `zlib.crc32` |
| Packaging | `setuptools` + `pyproject.toml` | Standard pip-installable wheel |
| Format | Plain-text `.vtxt` | Human-readable, versionable, transmittable |

---

## The VTXT Format

VTXT (Voice Data Text) is WavCore's audio serialization format.
Each `.vtxt` file contains one `[FILE_HEADER]` block followed by `N` `[FRAME]` blocks.

### File Header

```
[FILE_HEADER]
CODEC_VERSION=1          ← format version
FILE_VERSION=1
TOTAL_FRAMES=500         ← number of audio frames
SAMPLE_RATE=48000        ← Hz
CHANNELS=1               ← mono=1, stereo=2
BIT_DEPTH=32             ← IEEE-754 float32
FRAME_MS=20              ← frame duration in milliseconds
DURATION_MS=10000.000000 ← total audio length
CREATED_UNIX=1745123456  ← Unix timestamp of recording
CREATED_UTC=2026-04-21 09:43:00 UTC
[/FILE_HEADER]
```

### Frame Block

```
[FRAME]
FRAME_ID=0               ← sequential frame number (used for gap detection)
FRAME_VERSION=1
TIMESTAMP_MS=1745123456789.000000  ← absolute wall-clock time in ms
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
PAYLOAD_LEN=3840         ← bytes = SAMPLES_COUNT × 4
SAMPLES_COUNT=960        ← samples per frame (= SAMPLE_RATE × FRAME_MS / 1000)
ORIG_CRC32=BC5C582D      ← CRC-32 of header fields + payload bytes
SAMPLES_HEX=3C8B43963D...  ← IEEE-754 float32 bytes as uppercase hex
[/FRAME]
```

### Why VTXT?

| Property | Value |
|---|---|
| Human-readable | Open in Notepad — every sample is inspectable |
| Versionable | `git diff` shows which frames changed |
| Transmittable | Send via HTTP, WebSocket, SMS — no binary encoding needed |
| Self-describing | All metadata is embedded per frame |
| Lossless | Hex encoding preserves exact IEEE-754 bit pattern |

### Hex Encoding

Each `float32` sample occupies exactly **8 hex characters** (4 bytes × 2 hex chars/byte).

```
float32 value: 0.518646
IEEE-754 bytes: 3F04 9B51  (big-endian)
Hex string:    3F049B51
```

The encoder writes all samples of one frame as a single hex string:
```
SAMPLES_COUNT=960  →  SAMPLES_HEX=  (960 × 8 = 7,680 characters)
```

---

## The C Engine

`codec_core.c` contains five high-performance functions:

### 1. `float32_array_to_hex` — O(N) single-call encoding

```c
// Precomputed lookup table: index → 2 hex chars
static const char HEX_TABLE[256][2] = {
    {'0','0'}, {'0','1'}, ..., {'F','F'}
};

void float32_array_to_hex(const float *samples, int n, char *out) {
    const uint8_t *bytes = (const uint8_t*)samples;
    for (int i = 0; i < n * 4; i++) {
        *out++ = HEX_TABLE[bytes[i]][0];
        *out++ = HEX_TABLE[bytes[i]][1];
    }
    *out = '\0';
}
```

**Why it's fast:** O(1) table lookup per byte — no branching, no division, cache-friendly.

### 2. `hex_to_float32_array` — O(N) single-call decoding

```c
int hex_to_float32_array(const char *hex, int n, float *out) {
    uint8_t *bytes = (uint8_t*)out;
    for (int i = 0; i < n * 8; i += 2) {
        int hi = HEX_VAL[(uint8_t)hex[i]];
        int lo = HEX_VAL[(uint8_t)hex[i+1]];
        if (hi < 0 || lo < 0) return i/8 + 1;  // error: bad char
        *bytes++ = (uint8_t)((hi << 4) | lo);
    }
    return 0;
}
```

### 3. `frame_crc32` — CRC-32 with table acceleration

```c
uint32_t frame_crc32(uint8_t ver, uint32_t fid, double ts,
                     uint32_t sr, uint8_t ch, uint8_t bd,
                     uint32_t plen, const uint8_t *payload, uint32_t psz)
{
    // Pack the 7-field header (matches Python struct.pack(">BIdIBBI", ...))
    struct { uint8_t ver; uint32_t fid; double ts; uint32_t sr;
             uint8_t ch; uint8_t bd; uint32_t plen; } hdr;
    //  ... fill hdr ...
    uint32_t crc = crc32_compute((uint8_t*)&hdr, sizeof(hdr));
    return crc32_extend(crc, payload, psz);
}
```

The CRC table is a 256-entry `uint32_t` array pre-computed at module load.
Each byte costs one table lookup + one XOR.

### 4. `batch_hex_encode` — All frames in one C call

```c
void batch_hex_encode(const float *audio, int n_frames, int spf,
                      char *out_hex, int stride) {
    for (int i = 0; i < n_frames; i++) {
        float32_array_to_hex(audio + i * spf, spf, out_hex + i * stride);
    }
}
```

**Key insight:** One Python→C call for ALL frames. Eliminates the per-frame Python overhead.

### 5. `batch_hex_decode` — All frames in one C call

```c
int batch_hex_decode(const char *in_hex, int n_frames, int spf,
                     float *out, int stride) {
    for (int i = 0; i < n_frames; i++) {
        int err = hex_to_float32_array(in_hex + i*stride, spf, out + i*spf);
        if (err) return i + 1;
    }
    return 0;
}
```

---

## Pipeline Workflow

### Recording Pipeline

```
[Microphone Input]
        │
        ▼  sounddevice.rec(  )  — PortAudio, blocking, float32
[float32 numpy array]  480,000 samples @ 48kHz, 10 seconds
        │
        ▼  Pad to exact multiple of SPF (960)
[Padded float32 array]
        │
        ├──────────────────────────────────────────────┐
        │                                              │
        ▼  C batch_hex_encode( )                       ▼  wave.open( )
[hex_list]  500 hex strings                     [original_reference.wav]
   7,680 chars each                             16-bit PCM, ground-truth
        │
        ▼  C frame_crc32( ) × 500 frames
[crcs]  list of 500 CRC-32 hex strings
        │
        ▼  write [FRAME] blocks to file
[voice_data.vtxt]  ~3.9 MB  (3.85 KB / frame)
```

### Decode Pipeline

```
[voice_data.vtxt]
        │
        ▼  _parse_vtxt( )  — line-by-line parser
[file_hdr dict]  +  [frame_list]  500 dicts
        │
        ▼  batch_decode( C )  — all in ONE C call
[audio_flat float32]  480,000 samples
        │
        ▼  per-frame CRC verify  ( C frame_crc32 )
[ok_frames=500  bad_frames=0]
        │
        ├──────────────────────────────────────────────┐
        │                                              │
        ▼  np.concatenate( segments )           Gap silence inserted
[audio float32]                               for any missing FRAME_ID
        │
        ▼  wave.open( ) write 16-bit PCM
[reconstructed.wav]  960,044 bytes
        │
        ▼  sounddevice.play( )
[Speaker output]
```

---

## Engine Tier System

`codec.py` loads engines in priority order at import time:

```python
_ENGINE = "pure-python"

# Tier 1 — installed package (best)
try:
    from wavcore._codec._codec_core import ffi, lib
    _ENGINE = "cffi-installed"
except ImportError: pass

# Tier 2 — local dev build
try:
    from _codec_cffi import ffi, lib
    _ENGINE = "cffi-local"
except ImportError: pass

# Tier 3 — ctypes DLL
# Tier 4 — pure Python (binascii, already C-backed in CPython)
```

All four tiers produce **bit-identical output** — the only difference is speed.

---

## CRC-32 Frame Integrity

CRC-32 is computed over:
```
struct.pack(">BIdIBBI",
    FRAME_VERSION,      # B — uint8
    FRAME_ID,           # I — uint32
    TIMESTAMP_MS,       # d — double
    SAMPLE_RATE,        # I — uint32
    CHANNELS,           # B — uint8
    BIT_DEPTH,          # B — uint8
    PAYLOAD_LEN,        # I — uint32
) + payload_bytes       # raw IEEE-754 float32 bytes
```

The `>` (big-endian) prefix ensures the same byte order on all platforms.

If a frame is received with a mismatched CRC:
- The frame is **marked bad** but not discarded
- Its position is tracked by `FRAME_ID` for gap detection
- A silence segment is inserted at that position

---

## Build System

```
pip install wavcore
│
├── pip reads pyproject.toml
│     requires = ["setuptools", "cffi", "wheel"]
│
├── pip reads setup.py
│     cffi_modules = ["wavcore/_codec/_build_ffi.py:ffi"]
│
├── cffi reads _build_ffi.py
│     ffi.set_source("wavcore._codec._codec_core", <codec_core.c source>)
│
├── MSVC  (Windows) / GCC (Linux) / clang (macOS)
│     compiles codec_core.c → _codec_core.cp312-win_amd64.pyd
│
└── pip installs wavcore into site-packages
      wavcore/_codec/_codec_core.cp312-win_amd64.pyd  ← ready to import
```

The C compilation happens **once** during `pip install`.
After that, importing `wavcore` is instant and the C engine is always active.
