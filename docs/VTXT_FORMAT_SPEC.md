# VTXT Format Specification — v1.0 (WavCore 2.0.0)

> **Complete formal specification for the WavCore VTXT audio text format.**
> This document defines every field, value type, constraint, and encoding rule.

---

## Overview

VTXT (Voice Data Text) is a **line-based, plain-text audio serialization format** produced and consumed by the WavCore codec.

| Property | Value |
|---|---|
| File extension | `.vtxt` |
| Character encoding | **UTF-8** |
| Line endings | `LF` (`\n`) or `CRLF` (`\r\n`) — both accepted |
| Byte order mark | Not required, not recommended |
| Max line length | Unbounded (`SAMPLES_HEX` can be very long) |
| Format version | `1` (current) |
| WavCore version | 2.0.0+ |

---

## File Structure

A valid `.vtxt` file has exactly three sections in this order:

```
1. Comments (optional)         ← lines starting with  #
2. [FILE_HEADER] block         ← exactly one, required
3. N × [FRAME] blocks          ← N must equal TOTAL_FRAMES
```

No content is allowed outside these sections (except blank lines and `#` comments).

---

## Section 1 — Comments

Any line whose first non-whitespace character is `#` is a comment.
Comments may appear anywhere in the file and are **ignored** by the parser.

```
# ================================================================
# wavcore VTXT  v1.0
# Recorded : 2026-04-21 09:43:00 UTC
# Engine   : C engine [cffi / MSVC 64-bit .pyd]
# SAMPLES_HEX = raw IEEE-754 float32 bytes, uppercase hex
# Zero precision loss — no floating-point rounding
# MODE: LIVE (frames written frame-by-frame during capture)
# ================================================================
```

---

## Section 2 — `[FILE_HEADER]` Block

### Syntax

```
[FILE_HEADER]
KEY=VALUE
...
[/FILE_HEADER]
```

- Opening `[FILE_HEADER]` and closing `[/FILE_HEADER]` each on their own line
- Each field is `KEY=VALUE` — one per line, no spaces around `=`
- Unknown keys MUST be ignored (forward compatibility)

### Required Fields

| Field | Type | Description | Example |
|---|---|---|---|
| `CODEC_VERSION` | integer | WavCore codec format version | `1` |
| `FILE_VERSION` | integer | File format revision | `1` |
| `TOTAL_FRAMES` | integer ≥ 1 | Number of `[FRAME]` blocks | `500` |
| `SAMPLE_RATE` | integer | Samples per second (Hz) | `48000` |
| `CHANNELS` | integer | Audio channels (1=mono) | `1` |
| `BIT_DEPTH` | integer | Bits per sample (always 32) | `32` |
| `FRAME_MS` | integer | Frame duration in milliseconds | `20` |
| `DURATION_MS` | float | Total audio duration in ms | `10000.000000` |
| `CREATED_UNIX` | integer | Unix timestamp of recording start | `1745123456` |
| `CREATED_UTC` | string | Human-readable UTC datetime | `2026-04-21 09:43:00 UTC` |

### Optional Fields (v2.0.0+)

| Field | Type | Description | Example |
|---|---|---|---|
| `RECORD_MODE` | string | Recording mode used | `LIVE` or `NORMAL` |

> **Note:** `RECORD_MODE=LIVE` is written by `live_record()`. Normal `record()` files do not include this field. Parsers must ignore it if not present.

### Live Mode Header Note

In Live Mode, `TOTAL_FRAMES` and `DURATION_MS` are written as padded placeholders during recording and patched with final values when recording stops:

```
# During recording:
TOTAL_FRAMES=0000000000   ← placeholder
DURATION_MS=            0.000000   ← placeholder

# After recording stops (header is rewritten):
TOTAL_FRAMES=94
DURATION_MS=1880.000000
```

### Computed Constraints

```
SAMPLES_COUNT_PER_FRAME = SAMPLE_RATE × FRAME_MS / 1000
                        = 48000 × 20 / 1000 = 960

PAYLOAD_LEN_PER_FRAME   = SAMPLES_COUNT × 4   (4 bytes per float32)
                        = 960 × 4 = 3840

SAMPLES_HEX_LEN         = SAMPLES_COUNT × 8   (8 hex chars per float32)
                        = 960 × 8 = 7680
```

### Example `[FILE_HEADER]` — Normal Mode

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
[/FILE_HEADER]
```

### Example `[FILE_HEADER]` — Live Mode

```
[FILE_HEADER]
CODEC_VERSION=1
FILE_VERSION=1
TOTAL_FRAMES=94
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
FRAME_MS=20
DURATION_MS=1880.000000
CREATED_UNIX=1745123456
CREATED_UTC=2026-04-21 09:43:00 UTC
RECORD_MODE=LIVE
[/FILE_HEADER]
```

---

## Section 3 — `[FRAME]` Blocks

### Syntax

```
[FRAME]
KEY=VALUE
...
SAMPLES_HEX=<hex_string>
[/FRAME]
```

- `SAMPLES_HEX` **must be the last field** before `[/FRAME]`
- Frames **must appear in ascending `FRAME_ID` order**
- Gaps in `FRAME_ID` are valid — decoders insert silence for missing IDs

### Required Fields

| Field | Type | Constraint | Description |
|---|---|---|---|
| `FRAME_ID` | integer ≥ 0 | Sequential, ascending | Frame sequence number |
| `FRAME_VERSION` | integer | Currently `1` | Frame format version |
| `TIMESTAMP_MS` | float | Wall-clock ms since Unix epoch | Absolute capture time |
| `SAMPLE_RATE` | integer | Must match `[FILE_HEADER]` | Hz |
| `CHANNELS` | integer | Must match `[FILE_HEADER]` | Audio channels |
| `BIT_DEPTH` | integer | Always `32` | Bits per sample |
| `PAYLOAD_LEN` | integer | `= SAMPLES_COUNT × 4` | Raw payload bytes |
| `SAMPLES_COUNT` | integer | `= SAMPLE_RATE × FRAME_MS / 1000` | Samples in this frame |
| `ORIG_CRC32` | hex string | 8 uppercase hex chars, no `0x` | CRC-32 of header + payload |
| `SAMPLES_HEX` | hex string | `SAMPLES_COUNT × 8` uppercase hex chars | IEEE-754 float32 samples |

### Field Details

#### `FRAME_ID`

Starts at `0` for the first frame, increments by 1.
If a frame is missing, decoders detect the gap via non-consecutive IDs and insert silence:

```
[FRAME] FRAME_ID=0 ... [/FRAME]
[FRAME] FRAME_ID=1 ... [/FRAME]
                            ← Frame 2 missing: 960 silent samples inserted
[FRAME] FRAME_ID=3 ... [/FRAME]
```

#### `TIMESTAMP_MS`

Wall-clock milliseconds since Unix epoch:

```
TIMESTAMP_MS = recording_start_unix_time * 1000.0 + frame_id * FRAME_MS
```

Always written with 6 decimal places.

#### `ORIG_CRC32`

CRC-32 over packed header fields + raw payload:

```
CRC-32 input = struct.pack(">BIdIBBI",
    FRAME_VERSION,   # B  uint8
    FRAME_ID,        # I  uint32
    TIMESTAMP_MS,    # d  double
    SAMPLE_RATE,     # I  uint32
    CHANNELS,        # B  uint8
    BIT_DEPTH,       # B  uint8
    PAYLOAD_LEN,     # I  uint32
) + PAYLOAD_BYTES    # raw IEEE-754 float32 bytes
```

Written as 8 uppercase hex chars without `0x` prefix: `BC5C582D`

#### `SAMPLES_HEX`

IEEE-754 float32 samples as uppercase hex. Encoding:

```
float32: 0.518646
IEEE-754: 3F 04 9B 51
Hex:      3F049B51
```

For `SAMPLES_COUNT=960`: always exactly **7,680 characters**.

### Example `[FRAME]` Block

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
SAMPLES_HEX=00000000000000003F049B51BE800000...  (7680 chars total)
[/FRAME]
```

---

## Complete File Example (2 frames, truncated hex)

```
# ================================================================
# wavcore VTXT  v1.0
# Recorded : 2026-04-21 09:43:00 UTC
# Engine   : C engine [cffi / MSVC 64-bit .pyd]
# SAMPLES_HEX = raw IEEE-754 float32 bytes, uppercase hex
# Zero precision loss — no floating-point rounding
# ================================================================

[FILE_HEADER]
CODEC_VERSION=1
FILE_VERSION=1
TOTAL_FRAMES=2
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
FRAME_MS=20
DURATION_MS=40.000000
CREATED_UNIX=1745123456
CREATED_UTC=2026-04-21 09:43:00 UTC
[/FILE_HEADER]

[FRAME]
FRAME_ID=0
FRAME_VERSION=1
TIMESTAMP_MS=1745123456000.000000
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
PAYLOAD_LEN=3840
SAMPLES_COUNT=960
ORIG_CRC32=BC5C582D
SAMPLES_HEX=3D4CCCCD3E4CCCCD3F000000BF000000...  (7680 chars)
[/FRAME]

[FRAME]
FRAME_ID=1
FRAME_VERSION=1
TIMESTAMP_MS=1745123456020.000000
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
PAYLOAD_LEN=3840
SAMPLES_COUNT=960
ORIG_CRC32=D8ED9E12
SAMPLES_HEX=BE800000BE4CCCCD3EC000003E200000...  (7680 chars)
[/FRAME]
```

---

## Parser Implementation Guide

```python
def parse_vtxt(path: str):
    file_hdr = {}
    frames   = []
    in_fh = in_fr = False
    cur_fr = {}

    REQUIRED_HDR = {
        "CODEC_VERSION", "FILE_VERSION", "TOTAL_FRAMES",
        "SAMPLE_RATE", "CHANNELS", "BIT_DEPTH", "FRAME_MS",
        "DURATION_MS", "CREATED_UNIX", "CREATED_UTC",
    }
    REQUIRED_FR = {
        "FRAME_ID", "FRAME_VERSION", "TIMESTAMP_MS",
        "SAMPLE_RATE", "CHANNELS", "BIT_DEPTH",
        "PAYLOAD_LEN", "SAMPLES_COUNT", "ORIG_CRC32", "SAMPLES_HEX",
    }

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "[FILE_HEADER]":   in_fh = True;          continue
            if line == "[/FILE_HEADER]":  in_fh = False
                missing = REQUIRED_HDR - set(file_hdr)
                if missing:
                    raise ValueError(f"FILE_HEADER missing: {missing}")
                continue
            if line == "[FRAME]":         in_fr = True; cur_fr = {}; continue
            if line == "[/FRAME]":
                missing = REQUIRED_FR - set(cur_fr)
                if missing:
                    raise ValueError(f"Frame {cur_fr.get('FRAME_ID','?')} missing: {missing}")
                frames.append(cur_fr)
                in_fr = False; continue
            if "=" not in line:
                raise ValueError(f"Line {lineno}: unexpected: {line!r}")
            k, _, v = line.partition("=")
            (file_hdr if in_fh else cur_fr)[k.strip()] = v.strip()

    return file_hdr, frames
```

---

## Validation Rules

A VTXT file is **valid** if and only if:

1. File is UTF-8 encoded
2. Exactly one `[FILE_HEADER]` block is present
3. All required `[FILE_HEADER]` fields are present
4. `TOTAL_FRAMES` equals the actual number of `[FRAME]` blocks
5. All required `[FRAME]` fields are present in every frame
6. `FRAME_ID` values are non-negative integers in ascending order
7. `SAMPLES_HEX` length equals `SAMPLES_COUNT × 8` for every frame
8. `SAMPLES_HEX` contains only uppercase hex characters `[0-9A-F]`
9. `ORIG_CRC32` is exactly 8 uppercase hex characters
10. CRC computed from packed header + raw bytes matches `ORIG_CRC32`

Rules 9–10 are **integrity checks** — parsers SHOULD validate and report bad frames.

> **Live mode note:** During active recording, `TOTAL_FRAMES` in the header is a padded placeholder and will not yet match the frame count. After recording stops, the header is patched with the correct value. Parsers reading a file mid-recording should handle this gracefully.

---

## Versioning

| CODEC_VERSION | Changes |
|---|---|
| `1` | Initial release — mono/stereo, 32-bit float, CRC-32 |

Future versions will increment `CODEC_VERSION`.
Parsers MUST reject unknown `CODEC_VERSION` values.
Parsers MUST ignore unknown fields within known versions.

---

## File Size Estimates

| Sample Rate | Frame MS | Duration | Frames | Approx VTXT Size |
|---|---|---|---|---|
| 48,000 Hz | 20 ms | 5 s | 250 | ~1.9 MB |
| 48,000 Hz | 20 ms | **10 s** | **500** | **~3.9 MB** |
| 48,000 Hz | 20 ms | 60 s | 3,000 | ~23 MB |
| 48,000 Hz | 20 ms | 120 s | 6,000 | ~46 MB |
| 16,000 Hz | 20 ms | 10 s | 500 | ~1.3 MB |
| 44,100 Hz | 20 ms | 10 s | 500 | ~3.6 MB |

The dominant cost is `SAMPLES_HEX` — always `SAMPLES_COUNT × 8` characters per frame.
In Live Mode, the file grows by approximately **7.9 KB every 20ms** at 48kHz.
