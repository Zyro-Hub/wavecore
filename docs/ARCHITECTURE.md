# WavCore v2.0.0 — Architecture & Technical Reference

> **How WavCore is built, how it works internally, and what technologies power it.**

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Recording Modes](#recording-modes)
5. [The VTXT Format](#the-vtxt-format)
6. [The C Engine](#the-c-engine)
7. [Pipeline Workflow](#pipeline-workflow)
8. [Engine Tier System](#engine-tier-system)
9. [CRC-32 Frame Integrity](#crc-32-frame-integrity)
10. [Build System](#build-system)

---

## Overview

WavCore is a **lossless, real-time voice codec** built from:

- A **C language core** (`codec_core.c`) compiled via cffi/MSVC into a 64-bit Python extension
- A **Python bridge** (`codec.py`) wrapping the C engine with a clean API
- A **VTXT text format** — human-readable, line-based audio serialization
- A **tri-tier fallback engine** — C cffi → C ctypes DLL → Pure Python

| Requirement | How it is met |
|---|---|
| **Zero data loss** | IEEE-754 hex encoding — no decimal rounding ever |
| **Real-time speed** | C batch functions process 500 frames in one call |
| **Frame integrity** | CRC-32 per frame, computed and verified in C |
| **Live writing** | New in v2.0.0: `f.flush()` after every frame write |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     wavcore v2.0.0                          │
│                                                             │
│  ┌──────────────────────┐   ┌────────────────────────────┐  │
│  │  recorder.py         │   │  converter.py              │  │
│  │                      │   │                            │  │
│  │  record_to_vtxt()    │   │  voice_data.vtxt (input)   │  │
│  │  ─────────────────   │   │         |                  │  │
│  │  Mic → sd.rec()      │   │  _parse_vtxt()             │  │
│  │  float32[] batch     │   │         |                  │  │
│  │  C batch_encode()    │   │  C batch_decode()          │  │
│  │  C CRC-32 × N        │   │         |                  │  │
│  │  write .vtxt (once)  │   │  C CRC verify × N          │  │
│  │                      │   │         |                  │  │
│  │  live_record_to_vtxt │   │  float32[] → WAV           │  │
│  │  ─────────────────   │   │         |                  │  │
│  │  Mic → InputStream   │   │  sd.play() (optional)      │  │
│  │  callback → queue    │   └────────────────────────────┘  │
│  │  per frame:          │                                   │
│  │    C encode          │   ┌────────────────────────────┐  │
│  │    C CRC             │   │    _codec/codec.py          │  │
│  │    write [FRAME]     │   │                            │  │
│  │    f.flush() ← LIVE  │   │  Tier 1: cffi .pyd (best)  │  │
│  └──────────────────────┘   │  Tier 2: ctypes DLL        │  │
│                             │  Tier 3: Pure Python        │  │
│                             └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Audio capture | `sounddevice` (PortAudio) | Cross-platform, low-latency mic access |
| Live streaming | `sd.InputStream` + `queue` | Non-blocking callback → queue → encode |
| Array math | `numpy` | C-backed float32 array operations |
| C compilation | `cffi` + MSVC/GCC | Compiles C into Python extension (.pyd/.so) |
| C interop | `ctypes` | Fallback DLL loader if cffi .pyd unavailable |
| Hex encoding | `binascii.hexlify` | C-implemented inside CPython |
| Integrity | CRC-32 (table-driven C) | Fast per-frame integrity |
| Packaging | `setuptools` + `pyproject.toml` | Standard pip-installable wheel |
| Format | Plain-text `.vtxt` | Human-readable, transmittable, live-writable |

---

## Recording Modes

### Normal Mode — `record_to_vtxt()`

```
Mic ──> sd.rec() [blocking, full duration]
           │
           ▼ all frames at once
        C batch_encode()
        C CRC-32 × N frames
           │
           ▼
        write full .vtxt (one pass)
        save original.wav
```

### Live Mode — `live_record_to_vtxt()` ← New in v2.0.0

```
Mic ──> sd.InputStream [callback, non-blocking]
           │ every 20ms
           ▼
        audio_queue.put(frame)
           │
           ▼ main loop
        C batch_encode(frame)      ← 14 µs
        C compute_frame_crc()      ← 3 µs
        write [FRAME] to .vtxt
        f.flush()                  ← LIVE: visible on disk now
           │
           ▼
        (repeat until ENTER or max_duration)
           │
           ▼
        patch header (TOTAL_FRAMES, DURATION_MS)
        save original.wav
```

Key design choices for Live Mode:
- **`sd.InputStream`** with fixed `blocksize=spf` — PortAudio delivers exactly one frame per callback
- **`queue.Queue`** — decouples callback (must be fast) from encode+write (slightly slower)
- **`threading.Event`** + daemon thread — listens for ENTER without blocking the audio loop
- **`f.flush()`** — forces OS write buffer to disk after every frame so the file is readable live
- **Padded placeholder** — `TOTAL_FRAMES=0000000000` written at header time, overwritten at end

---

## The VTXT Format

### File Header

```
[FILE_HEADER]
CODEC_VERSION=1
FILE_VERSION=1
TOTAL_FRAMES=500
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
FRAME_MS=20
DURATION_MS=10000.000000
CREATED_UNIX=1745123456
CREATED_UTC=2026-04-21 09:43:00 UTC
RECORD_MODE=LIVE         ← only present in live_record() output
[/FILE_HEADER]
```

### Frame Block

```
[FRAME]
FRAME_ID=0
FRAME_VERSION=1
TIMESTAMP_MS=1745123456789.000000
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
PAYLOAD_LEN=3840
SAMPLES_COUNT=960
ORIG_CRC32=BC5C582D
SAMPLES_HEX=3C8B43963D...   (7,680 characters = 960 samples × 8 hex chars)
[/FRAME]
```

### Hex Encoding

Each `float32` sample → 4 raw bytes → 8 uppercase hex characters.

```
float32: 0.518646 → IEEE-754: 3F 04 9B 51 → Hex: 3F049B51
```

960 samples × 8 chars = **7,680 characters per frame**. Lossless — no rounding ever.

---

## The C Engine

`codec_core.c` contains five high-performance functions:

### 1. `float32_array_to_hex` — O(N) encoding with lookup table

```c
static const char HEX_TABLE[256][2] = { {'0','0'}, ... {'F','F'} };

void float32_array_to_hex(const float *samples, int n, char *out) {
    const uint8_t *bytes = (const uint8_t*)samples;
    for (int i = 0; i < n * 4; i++) {
        *out++ = HEX_TABLE[bytes[i]][0];
        *out++ = HEX_TABLE[bytes[i]][1];
    }
    *out = '\0';
}
```

O(1) table lookup per byte — no branching, cache-friendly.

### 2. `hex_to_float32_array` — O(N) decoding

```c
int hex_to_float32_array(const char *hex, int n, float *out) {
    uint8_t *bytes = (uint8_t*)out;
    for (int i = 0; i < n * 8; i += 2) {
        int hi = HEX_VAL[(uint8_t)hex[i]];
        int lo = HEX_VAL[(uint8_t)hex[i+1]];
        if (hi < 0 || lo < 0) return i/8 + 1;
        *bytes++ = (uint8_t)((hi << 4) | lo);
    }
    return 0;
}
```

### 3. `frame_crc32` — table-driven CRC-32

```c
uint32_t frame_crc32(uint8_t ver, uint32_t fid, double ts,
                     uint32_t sr, uint8_t ch, uint8_t bd,
                     uint32_t plen, const uint8_t *payload, uint32_t psz)
{
    // Packs header struct matching struct.pack(">BIdIBBI", ...)
    // Then CRC-32 over header + payload bytes
}
```

### 4. `batch_hex_encode` — all frames in one C call

```c
void batch_hex_encode(const float *audio, int n_frames, int spf,
                      char *out_hex, int stride) {
    for (int i = 0; i < n_frames; i++)
        float32_array_to_hex(audio + i*spf, spf, out_hex + i*stride);
}
```

**One Python→C transition for ALL frames** — eliminates per-frame Python overhead.

### 5. `batch_hex_decode` — all frames in one C call

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

### Normal Mode Recording Pipeline

```
[Microphone]
      │
      ▼  sd.rec() — blocking, full duration
[float32 array]  480,000 samples @ 48kHz, 10s
      │
      ├──────────────────────┐
      │                      ▼  wave.open()
      ▼  C batch_hex_encode  [original_reference.wav]  16-bit PCM
[hex_list] 500 strings
      │
      ▼  C frame_crc32() × 500
[crcs] 500 CRC-32 values
      │
      ▼  write [FRAME] blocks
[voice_data.vtxt]  ~3.9 MB
```

### Live Mode Recording Pipeline

```
[Microphone]
      │
      ▼  sd.InputStream callback (every 20ms)
[audio_queue]
      │
      ▼  main loop dequeues frame
[960 float32 samples]
      │
      ├── C batch_encode() → hex_str    (~14 µs)
      ├── C compute_frame_crc() → crc   (~3 µs)
      │
      ▼  write [FRAME] + f.flush()      (file grows live)
[voice_data.vtxt]  grows by ~7.9 KB every 20ms
      │
      ▼  on ENTER (or max_duration reached)
      │
      ├── patch TOTAL_FRAMES + DURATION_MS in header
      └── save original_reference.wav
```

### Decode Pipeline (same for both modes)

```
[voice_data.vtxt]
      │
      ▼  _parse_vtxt() — line-by-line
[file_hdr] + [frame_list] 500 dicts
      │
      ▼  C batch_decode() — ONE call
[audio_flat]  480,000 float32 samples
      │
      ▼  C frame_crc32() × 500 — verify
[ok=500  bad=0]
      │
      ▼  gap detection: silence for missing FRAME_IDs
      │
      ├──────────────────────┐
      │                      ▼  sounddevice.play()
      ▼  wave.open()       [Speaker]
[reconstructed.wav]
```

---

## Engine Tier System

```python
_ENGINE = "pure-python"

# Tier 1 — installed package (best)
try:
    from wavcore._codec._codec_core import ffi, lib
    _ENGINE = "cffi"
except ImportError: pass

# Tier 2 — ctypes DLL fallback
try:
    _L = ctypes.CDLL("codec_core.dll")
    _ENGINE = "ctypes"
except (OSError, AttributeError): pass

# Tier 3 — Pure Python (binascii, already C-backed in CPython)
```

All tiers produce **bit-identical output**. Only speed differs.

---

## CRC-32 Frame Integrity

CRC-32 is computed over:

```
struct.pack(">BIdIBBI",
    FRAME_VERSION,   # B  uint8
    FRAME_ID,        # I  uint32
    TIMESTAMP_MS,    # d  double
    SAMPLE_RATE,     # I  uint32
    CHANNELS,        # B  uint8
    BIT_DEPTH,       # B  uint8
    PAYLOAD_LEN,     # I  uint32
) + payload_bytes    # raw IEEE-754 float32 bytes
```

`>` (big-endian) ensures identical byte order on all platforms.

If CRC mismatches on decode:
- Frame is **marked bad** — not silently used
- Position tracked by `FRAME_ID` for gap detection
- **Silence** inserted at that position in the reconstructed audio

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
│     ffi.set_source("wavcore._codec._codec_core", <codec_core.c>)
│
├── MSVC (Windows) / GCC (Linux) / clang (macOS)
│     compiles codec_core.c → _codec_core.cp312-win_amd64.pyd
│
└── pip installs to site-packages
      wavcore/_codec/_codec_core.cp312-win_amd64.pyd ← active
```

C compilation happens **once** during `pip install`. After that, `wavcore` imports instantly with the C engine always active.
