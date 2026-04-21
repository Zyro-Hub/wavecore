# VTXT Format Specification — v1.0

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
| Max line length | Unbounded (SAMPLES_HEX can be very long) |
| Format version | `1` (current) |

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
Comments may appear anywhere in the file.  
Comments are **ignored** by the parser.

```
# This is a comment
# ================================================================
# wavcore VTXT  v1.0
# Recorded : 2026-04-21 09:43:00 UTC
# Engine   : C engine [cffi / MSVC 64-bit .pyd]
# ================================================================
```

---

## Section 2 — `[FILE_HEADER]` Block

### Syntax

```
[FILE_HEADER]
KEY=VALUE
KEY=VALUE
...
[/FILE_HEADER]
```

- The opening tag `[FILE_HEADER]` and closing tag `[/FILE_HEADER]` must each be on their own line.
- Each field is a single `KEY=VALUE` pair — one per line. No spaces around `=`.
- Unknown keys MUST be ignored by parsers (forward compatibility).

### Required Fields

| Field | Type | Description | Example |
|---|---|---|---|
| `CODEC_VERSION` | integer | WavCore codec format version | `1` |
| `FILE_VERSION` | integer | File format revision | `1` |
| `TOTAL_FRAMES` | integer ≥ 1 | Number of `[FRAME]` blocks in this file | `500` |
| `SAMPLE_RATE` | integer | Samples per second (Hz) | `48000` |
| `CHANNELS` | integer | Audio channels (1=mono, 2=stereo) | `1` |
| `BIT_DEPTH` | integer | Bits per sample (always 32 for float32) | `32` |
| `FRAME_MS` | integer | Frame duration in milliseconds | `20` |
| `DURATION_MS` | float | Total audio duration in milliseconds | `10000.000000` |
| `CREATED_UNIX` | integer | Unix timestamp of recording start | `1745123456` |
| `CREATED_UTC` | string | Human-readable UTC datetime | `2026-04-21 09:43:00 UTC` |

### Computed Constraints

These relationships must hold in a valid file:

```
SAMPLES_COUNT_PER_FRAME = SAMPLE_RATE × FRAME_MS / 1000
                        = 48000 × 20 / 1000
                        = 960

PAYLOAD_LEN_PER_FRAME   = SAMPLES_COUNT_PER_FRAME × 4   (4 bytes per float32)
                        = 960 × 4 = 3840

SAMPLES_HEX_LEN         = SAMPLES_COUNT_PER_FRAME × 8   (8 hex chars per float32)
                        = 960 × 8 = 7680

TOTAL_FRAMES ≥ ⌈DURATION_MS / FRAME_MS⌉
```

### Example `[FILE_HEADER]`

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

---

## Section 3 — `[FRAME]` Blocks

### Syntax

```
[FRAME]
KEY=VALUE
KEY=VALUE
...
SAMPLES_HEX=<hex_string>
[/FRAME]
```

- `[FRAME]` opens, `[/FRAME]` closes — each on its own line.
- `SAMPLES_HEX` **must be the last field** before `[/FRAME]`.
- Frames **must appear in ascending `FRAME_ID` order**.
- Gaps in `FRAME_ID` are valid — decoders insert silence for missing IDs.

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
| `ORIG_CRC32` | hex string | 8 uppercase hex chars, no `0x` prefix | CRC-32 of header + payload |
| `SAMPLES_HEX` | hex string | `SAMPLES_COUNT × 8` hex chars | IEEE-754 float32 samples |

### Field Details

#### `FRAME_ID`

- Starts at `0` for the first frame.
- Increments by `1` for each consecutive frame.
- If a frame is missing (e.g., dropped during transmission), decoders detect the gap  
  and insert `(missing_count × SAMPLES_COUNT)` samples of **silence (0.0)**.

```
# Example: frames 0, 1, 3 are present; frame 2 is missing
[FRAME] FRAME_ID=0 ... [/FRAME]
[FRAME] FRAME_ID=1 ... [/FRAME]
                            ← Frame 2: decoder inserts 960 silent samples here
[FRAME] FRAME_ID=3 ... [/FRAME]
```

#### `TIMESTAMP_MS`

Wall-clock time in **milliseconds since the Unix epoch** (Jan 1 1970 00:00:00 UTC).

```
TIMESTAMP_MS=1745123456789.000000
```

Computed as:
```python
TIMESTAMP_MS = recording_start_unix_time * 1000.0 + frame_id * FRAME_MS
```

Always written with 6 decimal places.

#### `ORIG_CRC32`

CRC-32 computed over the **packed header fields + raw payload bytes**:

```
CRC-32 input = struct.pack(">BIdIBBI",
    FRAME_VERSION,   # B  — uint8,  big-endian
    FRAME_ID,        # I  — uint32, big-endian
    TIMESTAMP_MS,    # d  — double, big-endian
    SAMPLE_RATE,     # I  — uint32, big-endian
    CHANNELS,        # B  — uint8
    BIT_DEPTH,       # B  — uint8
    PAYLOAD_LEN,     # I  — uint32, big-endian
) + PAYLOAD_BYTES    # raw IEEE-754 float32 bytes (little-endian on x86)
```

Result written as **8 uppercase hex characters without `0x` prefix**:

```
ORIG_CRC32=BC5C582D
```

Parsers recompute this CRC to verify frame integrity.  
A mismatched CRC means the frame data was corrupted or tampered.

#### `SAMPLES_HEX`

The raw audio samples encoded as uppercase hexadecimal.

**Encoding algorithm:**
1. Take the `float32` numpy array for this frame
2. Interpret each `float32` as 4 raw bytes (IEEE-754, native byte order)
3. For each byte, write 2 uppercase hex characters: `HEX_TABLE[byte]`
4. Concatenate all hex pairs into one continuous string

```
Example encoding of 3 samples:

  float32 value   IEEE-754 bytes     Hex chars
  ─────────────   ──────────────     ─────────
  0.00000000      00 00 00 00        00000000
  0.51864624      3F 04 9B 51        3F049B51   (varies by CPU byte order)
  -0.25000000     BE 80 00 00        BE800000

Result: 000000003F049B51BE800000  (24 chars for 3 samples)
```

For `SAMPLES_COUNT=960`:  
→ `SAMPLES_HEX` is always exactly **7,680 characters** long.

**Decoding algorithm (reverse):**
1. Split the hex string into chunks of 8 characters
2. Convert each chunk back to 4 bytes using `bytes.fromhex(chunk)`
3. Reinterpret 4 bytes as a `float32` using `struct.unpack("f", b)`
4. Collect all float32 values into the frame's sample array

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
SAMPLES_HEX=00000000000000003F049B51BE8000003C8B43963D...  (7680 chars total)
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

A minimal compliant parser:

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
            if line == "[/FILE_HEADER]":  in_fh = False;
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

    # Validate frame count
    expected = int(file_hdr["TOTAL_FRAMES"])
    if len(frames) != expected:
        raise ValueError(f"Expected {expected} frames, got {len(frames)}")

    return file_hdr, frames
```

---

## Validation Rules

A VTXT file is **valid** if and only if:

1. File is UTF-8 encoded
2. Exactly one `[FILE_HEADER]` block is present
3. All required `[FILE_HEADER]` fields are present (see table above)
4. `TOTAL_FRAMES` equals the actual number of `[FRAME]` blocks
5. All required `[FRAME]` fields are present in every frame
6. `FRAME_ID` values are non-negative integers in ascending order
7. `SAMPLES_HEX` length equals `SAMPLES_COUNT × 8` for every frame
8. `SAMPLES_HEX` contains only uppercase hex characters `[0-9A-F]`
9. `ORIG_CRC32` is exactly 8 uppercase hex characters
10. Per-frame CRC computed from packed header + raw bytes matches `ORIG_CRC32`

Rules 9–10 are **integrity checks** — a parser SHOULD validate them and report
bad frames rather than silently using corrupt data.

---

## Versioning

| CODEC_VERSION | Changes |
|---|---|
| `1` | Initial release — mono/stereo, 32-bit float, CRC-32 |

Future versions will increment `CODEC_VERSION` and add new fields.  
Parsers MUST reject files with `CODEC_VERSION` values they do not recognize.  
Parsers MUST ignore unknown fields within known versions.

---

## File Size Estimates

| Sample Rate | Frame MS | Duration | Frames | Approx VTXT Size |
|---|---|---|---|---|
| 48,000 Hz | 20 ms | 5 s | 250 | ~1.9 MB |
| 48,000 Hz | 20 ms | **10 s** | **500** | **~3.9 MB** |
| 48,000 Hz | 20 ms | 60 s | 3,000 | ~23 MB |
| 16,000 Hz | 20 ms | 10 s | 500 | ~1.3 MB |
| 44,100 Hz | 20 ms | 10 s | 500 | ~3.6 MB |

The dominant cost is `SAMPLES_HEX` — always `SAMPLES_COUNT × 8` characters per frame.
