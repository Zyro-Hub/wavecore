# WavCore v2.0.0 — User Manual

> **Everything you need to start recording, encoding, and reconstructing audio.**

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Core Concepts](#core-concepts)
4. [Recording Modes](#recording-modes)
5. [High-Level API](#high-level-api)
   - [wavcore.record()](#wavcore-record)
   - [wavcore.live_record()](#wavcore-live_record)
   - [wavcore.decode()](#wavcore-decode)
   - [wavcore.engine_info()](#wavcore-engine_info)
6. [Low-Level Frame API](#low-level-frame-api)
7. [Working with Stats Dicts](#working-with-stats-dicts)
8. [Integration Examples](#integration-examples)
9. [Running app.py](#running-apppy)
10. [Troubleshooting](#troubleshooting)
11. [Configuration Reference](#configuration-reference)

---

## Installation

### Standard Install

```bash
pip install wavcore==2.0.0
```

Automatically installs: `numpy`, `sounddevice`, `cffi`
The C engine compiles during install. No extra steps.

### Development Install (editable)

```bash
pip install -e .
```

Changes to `wavcore/` take effect immediately — no reinstall needed.

### Verify Installation

```python
import wavcore
print(wavcore.__version__)    # → 2.0.0
print(wavcore.engine_info())  # → C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast
```

---

## Quick Start

```python
import wavcore

# Option A — Normal mode: record full audio then encode
wavcore.record("audio.vtxt", "original.wav", duration=10)

# Option B — Live mode: write each frame to .vtxt in real-time while speaking
wavcore.live_record("audio.vtxt", "original.wav", max_duration=60)

# Convert any .vtxt file → WAV (works with both modes)
wavcore.decode("audio.vtxt", "reconstructed.wav", play=True)
```

---

## Core Concepts

### What is a .vtxt file?

A `.vtxt` file is WavCore's lossless audio text format. Audio is stored as **uppercase hexadecimal strings** — one 20ms frame per block.

- **Lossless:** Every bit of float32 audio is preserved exactly (IEEE-754)
- **Human-readable:** Open in Notepad and read the metadata and frame data
- **Portable:** Plain text — send over HTTP, WebSocket, store in any database
- **Live-writable:** In Live Mode, the file grows on disk frame-by-frame in real-time

### What is a Frame?

WavCore splits audio into **frames** of fixed duration (default: 20ms = 960 samples @ 48kHz).

Each frame contains:
- `FRAME_ID` — sequential integer (used for gap detection)
- `TIMESTAMP_MS` — wall-clock time of capture in milliseconds
- `ORIG_CRC32` — CRC-32 checksum for integrity verification
- `SAMPLES_HEX` — the actual audio data as hex string

### Why Lossless?

Normal codecs (MP3, AAC, Opus) discard audio data. WavCore never does. Every `float32` sample is encoded as its exact IEEE-754 byte pattern. Decoding gives back **identical bytes** — not an approximation.

```python
import numpy as np, wavcore

original = np.array([0.5, -0.25, 0.1234], dtype=np.float32)
hex_str  = wavcore.batch_encode(original, 3)[0]
back     = wavcore.batch_decode([hex_str], 3)

print(np.array_equal(original, back))   # → True  (bit-perfect)
```

---

## Recording Modes

WavCore 2.0.0 offers two recording modes:

| | Normal Mode | Live Mode |
|---|---|---|
| **Function** | `wavcore.record()` | `wavcore.live_record()` |
| **When is .vtxt written?** | After full capture | Every 20ms frame |
| **Can you stop early?** | No | Yes — press ENTER |
| **Duration** | Fixed (`duration=`) | Up to `max_duration=` |
| **File visible while recording?** | Only after done | Grows live on disk |
| **Best for** | Fixed-length clips | Open-ended recording |

---

## High-Level API

### `wavcore.record()`

Record a fixed duration from the microphone. All encoding happens **after** the full capture in one fast C batch call.

```python
stats = wavcore.record(
    vtxt_path   = "audio.vtxt",      # required — output .vtxt path
    orig_wav    = "original.wav",    # optional — ground-truth WAV (default "original.wav")
    duration    = 10,                # optional — seconds to record (default 10)
    sample_rate = 48_000,            # optional — Hz               (default 48000)
    frame_ms    = 20,                # optional — frame size in ms (default 20)
)
```

**Pipeline:**
```
Mic → sd.rec() (full capture) → C batch_encode() → C CRC-32 × N → write .vtxt
```

**Returns:**

```python
{
    "frames":        500,
    "duration_ms":   10000.0,
    "sample_rate":   48000,
    "channels":      1,
    "peak":          0.518646,       # 0.0 to 1.0
    "rms":           0.055205,
    "vtxt_path":     "audio.vtxt",
    "orig_wav_path": "original.wav",
    "created_unix":  1745123456,
    "vtxt_size":     3942506,        # bytes
    "encode_ms":     35.2,
}
```

**Example:**
```python
stats = wavcore.record("voice.vtxt", "voice_orig.wav", duration=5)
print(f"Recorded {stats['frames']} frames  ({stats['duration_ms']/1000:.1f}s)")
print(f"Peak={stats['peak']:.4f}  RMS={stats['rms']:.4f}")
```

---

### `wavcore.live_record()`

**New in v2.0.0** — Records from the microphone and writes each 20ms frame to `.vtxt` **in real-time** as audio arrives. The file grows visibly on disk while you speak. Press **ENTER** to stop early.

```python
stats = wavcore.live_record(
    vtxt_path    = "audio.vtxt",     # required — output .vtxt path
    orig_wav     = "original.wav",   # optional — ground-truth WAV (default "original.wav")
    max_duration = 60,               # optional — max seconds      (default 60)
    sample_rate  = 48_000,           # optional — Hz               (default 48000)
    frame_ms     = 20,               # optional — frame size in ms (default 20)
)
```

**Pipeline (runs every 20ms while recording):**
```
Mic callback → audio queue → C batch_encode() → C CRC-32 → write [FRAME] → f.flush()
                                                                  ↑
                                                           file grows live
```

**Live progress display:**
```
  [LIVE] Frame     94  |  1.9s  |  90.5 KB
```

You can open the `.vtxt` file in a text editor and watch frames appear in real-time.

**Returns:** Same dict shape as `record()`.

**Example:**
```python
# Record up to 2 minutes, stop anytime with ENTER
stats = wavcore.live_record(
    vtxt_path    = "live_voice.vtxt",
    orig_wav     = "live_orig.wav",
    max_duration = 120,
)
print(f"Captured {stats['frames']} frames  ({stats['duration_ms']/1000:.1f}s)")
```

---

### `wavcore.decode()`

Convert **any** `.vtxt` file into a WAV file with optional playback. Works with files from both `record()` and `live_record()`.

```python
stats = wavcore.decode(
    vtxt_path  = "audio.vtxt",          # required — input .vtxt file
    output_wav = "reconstructed.wav",   # optional — output WAV path
    play       = True,                  # optional — play after decode (default True)
)
```

**Pipeline:**
```
.vtxt → parse [FRAME] blocks → C batch_decode() → C CRC-32 verify
      → gap detection (silence for missing frames) → save WAV → play
```

**Returns:**

```python
{
    "ok_frames":     500,
    "bad_frames":    0,
    "integrity_pct": 100.0,             # 100.0 = perfect lossless
    "duration_s":    10.0,
    "peak":          0.518646,
    "rms":           0.055205,
    "output_wav":    "reconstructed.wav",
    "sample_rate":   48000,
    "total_ms":      35.8,
}
```

**Examples:**

```python
# Just convert, no playback (server use)
stats = wavcore.decode("voice.vtxt", "output.wav", play=False)
print(f"Integrity: {stats['integrity_pct']:.2f}%  |  Duration: {stats['duration_s']:.2f}s")

# Convert and play immediately
wavcore.decode("voice.vtxt", "output.wav", play=True)
```

---

### `wavcore.engine_info()`

Returns a string describing the active C engine tier.

```python
print(wavcore.engine_info())
```

Possible outputs:
```
C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast    ← best (after pip install)
C engine [ctypes DLL]  — fast                       ← DLL fallback
Pure-Python fallback  [run build_codec.py for C engine]
```

Always check this first when debugging performance.

---

## Low-Level Frame API

### `wavcore.batch_encode(audio, spf)`

```python
import wavcore, numpy as np

audio    = np.random.randn(10 * 960).astype(np.float32)
hex_list = wavcore.batch_encode(audio, spf=960)

print(len(hex_list))       # 10
print(len(hex_list[0]))    # 7680  (960 × 8 hex chars)
```

### `wavcore.batch_decode(hex_list, spf)`

```python
audio_back = wavcore.batch_decode(hex_list, spf=960)

print(audio_back.shape)                       # (9600,)
print(np.array_equal(audio, audio_back))      # True — bit-perfect
```

### `wavcore.compute_frame_crc()`

```python
payload = audio[:960].astype(np.float32).tobytes()

crc = wavcore.compute_frame_crc(
    version      = 1,
    frame_id     = 0,
    timestamp_ms = 1745123456789.0,
    sample_rate  = 48000,
    channels     = 1,
    bit_depth    = 32,
    payload      = payload,
)
print(f"CRC-32: {crc:08X}")   # e.g. BC5C582D
```

---

## Working with Stats Dicts

```python
import wavcore

# Normal mode
rec  = wavcore.record("audio.vtxt", "orig.wav", duration=10)

# OR Live mode
# rec = wavcore.live_record("audio.vtxt", "orig.wav", max_duration=60)

dec  = wavcore.decode("audio.vtxt", "recon.wav", play=False)

# Signal quality check
if rec["peak"] < 0.001:
    print("WARNING: Mic too quiet — check OS audio settings")
elif rec["peak"] > 0.95:
    print("WARNING: Clipping — move mic further away")
else:
    print(f"Good signal: peak={rec['peak']:.4f}  rms={rec['rms']:.4f}")

# Decode quality check
if dec["integrity_pct"] == 100.0:
    print("Perfect reconstruction — bit-identical")
elif dec["integrity_pct"] >= 95.0:
    print(f"Good: {dec['integrity_pct']:.1f}% valid")
else:
    print(f"Degraded: {dec['bad_frames']} frames corrupted/missing")

# Speed
print(f"Encode: {rec['encode_ms']:.1f} ms for {rec['frames']} frames")
print(f"Decode: {dec['total_ms']:.1f} ms for {dec['ok_frames']} frames")
```

---

## Integration Examples

### 1. Live Record → Immediate Decode

```python
import wavcore

# Record live (press ENTER to stop)
rec = wavcore.live_record("voice.vtxt", "orig.wav", max_duration=120)
print(f"Captured {rec['frames']} frames ({rec['duration_ms']/1000:.1f}s)")

# Decode and play immediately
dec = wavcore.decode("voice.vtxt", "reconstructed.wav", play=True)
print(f"Integrity: {dec['integrity_pct']:.2f}%")
```

### 2. Direct .vtxt → WAV (no recording needed)

```python
import wavcore

# You already have a .vtxt — just convert it
stats = wavcore.decode(
    vtxt_path  = "existing_voice.vtxt",
    output_wav = "output.wav",
    play       = False,
)
print(f"Done — {stats['duration_s']:.1f}s  |  {stats['integrity_pct']:.1f}% intact")
```

### 3. Voice Messaging (HTTP)

```python
import wavcore, requests

# SENDER
wavcore.record("message.vtxt", "send_orig.wav", duration=5)
with open("message.vtxt", "r") as f:
    payload = f.read()
requests.post("https://api.myapp.com/voice/send",
              data=payload.encode("utf-8"),
              headers={"Content-Type": "text/plain; charset=utf-8"})

# RECEIVER
response = requests.get("https://api.myapp.com/voice/recv/msg123")
with open("received.vtxt", "w", encoding="utf-8") as f:
    f.write(response.text)
result = wavcore.decode("received.vtxt", "playback.wav", play=True)
```

### 4. SQLite Storage

```python
import wavcore, sqlite3

conn = sqlite3.connect("voices.db")
conn.execute("""CREATE TABLE IF NOT EXISTS voice_messages
    (id INTEGER PRIMARY KEY, sender TEXT, vtxt_data TEXT, created_at REAL)""")

stats = wavcore.record("temp.vtxt", "temp_orig.wav", duration=5)
with open("temp.vtxt") as f:
    vtxt = f.read()
conn.execute("INSERT INTO voice_messages VALUES (NULL,?,?,?)",
             ("Alice", vtxt, stats["created_unix"]))
conn.commit()

row = conn.execute(
    "SELECT vtxt_data FROM voice_messages ORDER BY id DESC LIMIT 1"
).fetchone()
with open("playback.vtxt", "w") as f:
    f.write(row[0])
wavcore.decode("playback.vtxt", "playback.wav", play=True)
```

### 5. Server-Side — No Playback

```python
import wavcore

stats = wavcore.decode(
    vtxt_path  = "/uploads/voice_001.vtxt",
    output_wav = "/processed/voice_001.wav",
    play       = False,
)
print(f"Processed: {stats['integrity_pct']:.1f}%  time={stats['total_ms']:.1f}ms")
```

---

## Running app.py

```bash
python app.py
```

You will see:

```
  [1]  NORMAL MODE   — record full audio, then encode (batch)
  [2]  LIVE MODE     — encode each frame live while speaking

  Enter 1 or 2:
```

**Normal Mode** — records a fixed duration (default 60s), encodes all at once, then decodes and plays.

**Live Mode** — opens a real-time stream, writes frames to `.vtxt` in real-time. Press ENTER to stop, then decodes and plays.

Both modes produce the same three output files:
- `original_reference.wav` — raw mic capture
- `voice_data.vtxt` — text-encoded audio frames
- `reconstructed.wav` — rebuilt from vtxt

---

## Troubleshooting

### "Pure-Python fallback" instead of C engine

```bash
pip install --force-reinstall wavcore
# or from source:
pip install -e .
```

### No audio recorded (peak < 0.001)

```python
import sounddevice
print(sounddevice.query_devices())   # list devices
```

Check OS microphone permissions: Settings → Privacy → Microphone.

### `sounddevice` not found

```bash
pip install sounddevice
# Linux:
sudo apt install libportaudio2
```

### Live mode ENTER key not working

Press `Ctrl+C` as an alternative stop signal. This is also handled gracefully.

### CRC failures after local record+decode

Re-record to get a clean file. For network use, add retry logic per frame.

---

## Configuration Reference

| Parameter | Default | Range | Applies to |
|---|---|---|---|
| `duration` | `10` | 1–3600 s | `record()` only |
| `max_duration` | `60` | 1–3600 s | `live_record()` only |
| `sample_rate` | `48000` | 8000–192000 | Both |
| `frame_ms` | `20` | 10–100 | Both |
| `play` | `True` | True/False | `decode()` only |

### Sample Rate vs File Size (10 seconds)

| Sample Rate | Samples/Frame | File Size | Quality |
|---|---|---|---|
| 8,000 Hz | 160 → 1,280 chars | ~660 KB | Phone call |
| 16,000 Hz | 320 → 2,560 chars | ~1.3 MB | VoIP |
| 44,100 Hz | 882 → 7,056 chars | ~3.6 MB | CD quality |
| **48,000 Hz** | **960 → 7,680 chars** | **~3.9 MB** | **Default** |
| 96,000 Hz | 1,920 → 15,360 chars | ~7.8 MB | Professional |
