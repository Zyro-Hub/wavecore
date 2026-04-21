# WavCore

> **Ultra-fast, lossless real-time voice codec powered by a C engine**

**WavCore** is a Python package for recording, serializing, transmitting, and reconstructing voice audio with **bit-perfect precision**. It converts microphone audio into a human-readable text format called **VTXT** (`.vtxt`), making voice easy to store, inspect, sync, and send through any text-friendly system.

Created by **Prashant Pandey**
Repository: https://github.com/Zyro-Hub/wavecore
PyPI: https://pypi.org/project/wavcore/

---

## What's New in 2.0.0

- **Live Mode** (`wavcore.live_record`) — encodes and writes each frame to `.vtxt` in real-time while you speak. The file grows on disk live. Press ENTER to stop.
- **Normal Mode** (`wavcore.record`) — records full audio first, then encodes all at once (existing batch behaviour).
- `app.py` now shows a mode selection menu on startup.

---

## What WavCore Does

WavCore captures microphone audio, splits it into small 20ms frames, converts each frame into hexadecimal text with a CRC-32 checksum, and stores everything as a `.vtxt` file.

That means you can:

- Record voice locally and replay it perfectly
- Send voice over HTTP, WebSocket, Firebase, or any database
- Reconstruct the original audio anywhere, anytime
- Verify every frame for corruption with CRC-32

---

## Key Features

| Feature | Detail |
|---|---|
| **Lossless** | IEEE-754 hex encoding — zero float precision loss |
| **C engine** | `cffi`-compiled .pyd — 1326× faster than real-time |
| **Live mode** | Writes `.vtxt` frame-by-frame while speaking |
| **Normal mode** | Batch encode after full capture |
| **CRC-32** | Per-frame integrity check |
| **Gap handling** | Missing frames → silence during decode |
| **Pure-Python fallback** | Works without native build |
| **Text transport** | Works with Firebase, SQLite, HTTP, WebSocket |

---

## Installation

```bash
pip install wavcore
```

Auto-installs: `numpy`, `sounddevice`, `cffi`
The C engine is compiled during install. No extra steps.

### Development (editable) Install

```bash
pip install wavecore==2.0.0 .
```

### Verify

```python
import wavcore
print(wavcore.__version__)    # 2.0.0
print(wavcore.engine_info())  # C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast
```

---

## Quick Start

```python
import wavcore

# Normal mode — record 10s, then encode
wavcore.record("audio.vtxt", "original.wav", duration=10)

# Live mode — write frames to .vtxt in real-time while speaking
wavcore.live_record("audio.vtxt", "original.wav", max_duration=60)

# Convert any .vtxt file → WAV (+ optional playback)
wavcore.decode("audio.vtxt", "reconstructed.wav", play=True)

# Check active engine
print(wavcore.engine_info())
```

---

## Running the Demo

```bash
python app.py
```

```
  [1]  NORMAL MODE   — record full audio, then encode (batch)
  [2]  LIVE MODE     — encode each frame live while speaking

  Enter 1 or 2:
```

Both modes produce identical output files and feed into the same decode + playback step.

---

## Full Public API Reference

### Summary Table

| Function | Mode | Description |
|---|---|---|
| `wavcore.record()` | Normal | Record full audio, encode to `.vtxt` in one batch |
| `wavcore.live_record()` | **Live** | Encode + write each frame live while speaking |
| `wavcore.decode()` | Decode | Convert any `.vtxt` → WAV + optional playback |
| `wavcore.engine_info()` | Info | Show active C engine tier |
| `wavcore.batch_encode()` | Low-level | `float32` array → list of hex strings |
| `wavcore.batch_decode()` | Low-level | List of hex strings → `float32` array |
| `wavcore.compute_frame_crc()` | Low-level | Compute CRC-32 for one frame |

---

### `wavcore.record()`

Record a fixed duration from the microphone. All encoding happens **after** capture in one fast batch call.

```python
stats = wavcore.record(
    vtxt_path   = "audio.vtxt",   # required — output .vtxt path
    orig_wav    = "original.wav", # optional — ground-truth WAV  (default "original.wav")
    duration    = 10,             # optional — seconds to record (default 10)
    sample_rate = 48_000,         # optional — Hz                (default 48000)
    frame_ms    = 20,             # optional — frame size in ms  (default 20)
)
```

**Pipeline:**
```
Mic → capture all audio → C batch_encode() → C CRC-32 per frame → write .vtxt
```

**Returns:**

```python
{
    "frames":        500,           # frames written
    "duration_ms":   10000.0,       # ms
    "sample_rate":   48000,
    "channels":      1,
    "peak":          0.518646,      # 0.0–1.0
    "rms":           0.055205,
    "vtxt_path":     "audio.vtxt",
    "orig_wav_path": "original.wav",
    "created_unix":  1745123456,
    "vtxt_size":     3942506,       # bytes
    "encode_ms":     35.2,          # total encode time
}
```

**Example:**

```python
import wavcore

stats = wavcore.record("voice.vtxt", "voice_orig.wav", duration=5)

print(f"Recorded : {stats['frames']} frames")
print(f"Duration : {stats['duration_ms'] / 1000:.1f} s")
print(f"Peak     : {stats['peak']:.4f}")
print(f"File     : {stats['vtxt_size']:,} bytes")
```

---

### `wavcore.live_record()`

**NEW in 2.0.0** — Records from the microphone and writes each 20ms frame to `.vtxt` **in real-time** as audio arrives. The file grows on disk while you speak. Press **ENTER** to stop early.

```python
stats = wavcore.live_record(
    vtxt_path    = "audio.vtxt",   # required — output .vtxt path
    orig_wav     = "original.wav", # optional — ground-truth WAV   (default "original.wav")
    max_duration = 60,             # optional — max seconds        (default 60)
    sample_rate  = 48_000,         # optional — Hz                 (default 48000)
    frame_ms     = 20,             # optional — frame size in ms   (default 20)
)
```

**Pipeline (per frame, every 20ms):**
```
Mic callback → queue → C batch_encode() → C CRC-32 → write [FRAME] → f.flush()
```

**Key difference from `record()`:**

| | `record()` | `live_record()` |
|---|---|---|
| When is .vtxt written? | After full capture | Every 20ms frame |
| Can you stop early? | No | Yes — press ENTER |
| Duration | Fixed | Up to `max_duration` |
| File visible on disk | Only after done | Grows in real-time |

**Returns:** Same dict shape as `record()`.

**Example:**

```python
import wavcore

# Record up to 2 minutes, stop early by pressing ENTER
stats = wavcore.live_record(
    vtxt_path    = "live_voice.vtxt",
    orig_wav     = "live_orig.wav",
    max_duration = 120,
)

print(f"Recorded : {stats['frames']} frames  ({stats['duration_ms']/1000:.1f} s)")
print(f"File     : {stats['vtxt_size']:,} bytes")
```

**Live progress output while recording:**
```
  [LIVE] Frame     47  |  0.9s  |  45.2 KB
```
You can open `live_voice.vtxt` in a text editor while recording — frames appear in real-time.

---

### `wavcore.decode()`

Convert **any** `.vtxt` file into a WAV file, with optional playback. Works with files from both `record()` and `live_record()`.

```python
stats = wavcore.decode(
    vtxt_path  = "audio.vtxt",        # required — input .vtxt file
    output_wav = "reconstructed.wav", # optional — output WAV path (default "reconstructed.wav")
    play       = True,                # optional — play after decode (default True)
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
    "ok_frames":     500,             # frames with valid CRC
    "bad_frames":    0,               # corrupted or missing frames
    "integrity_pct": 100.0,           # 100.0 = perfect lossless
    "duration_s":    10.0,            # seconds
    "peak":          0.518646,
    "rms":           0.055205,
    "output_wav":    "reconstructed.wav",
    "sample_rate":   48000,
    "total_ms":      35.8,            # decode pipeline time in ms
}
```

**Example — just convert, no playback (server use):**

```python
import wavcore

stats = wavcore.decode(
    vtxt_path  = "voice_data.vtxt",
    output_wav = "output.wav",
    play       = False,              # don't play, just save
)

print(f"Integrity : {stats['integrity_pct']:.2f}%")
print(f"Duration  : {stats['duration_s']:.2f} s")
print(f"Bad frames: {stats['bad_frames']}")
```

**Example — decode and play immediately:**

```python
wavcore.decode("voice_data.vtxt", "output.wav", play=True)
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

Always check this first when debugging performance. You want `C engine`.

---

### `wavcore.batch_encode(audio, spf)`

Low-level: encode a `float32` numpy array into a list of hex strings (one per frame).

```python
import wavcore
import numpy as np

audio    = np.random.randn(5 * 960).astype(np.float32)  # 5 frames
spf      = 960                                           # samples per frame

hex_list = wavcore.batch_encode(audio, spf)

print(len(hex_list))       # 5
print(len(hex_list[0]))    # 7680  (960 samples × 8 hex chars each)
print(type(hex_list[0]))   # <class 'str'>
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `audio` | `np.ndarray` float32, 1-D | Audio samples, length = `n_frames × spf` |
| `spf` | `int` | Samples per frame (e.g. 960 for 20ms @ 48kHz) |

**Returns:** `list[str]` — uppercase hex strings, one per frame.

---

### `wavcore.batch_decode(hex_list, spf)`

Low-level: decode a list of hex strings back to a contiguous `float32` array. Exact inverse of `batch_encode`.

```python
audio_back = wavcore.batch_decode(hex_list, spf=960)

print(audio_back.shape)  # (4800,)  = 5 frames × 960 samples
print(audio_back.dtype)  # float32
print(np.array_equal(audio, audio_back))  # True — bit-perfect
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `hex_list` | `list[str]` | Hex strings from `batch_encode` |
| `spf` | `int` | Samples per frame |

**Returns:** `np.ndarray` float32, 1-D.

---

### `wavcore.compute_frame_crc()`

Low-level: compute the CRC-32 checksum for a single audio frame. Used to verify frame integrity.

```python
import wavcore
import numpy as np

samples  = np.random.randn(960).astype(np.float32)
payload  = samples.tobytes()

crc = wavcore.compute_frame_crc(
    version      = 1,
    frame_id     = 0,
    timestamp_ms = 1745123456789.0,
    sample_rate  = 48000,
    channels     = 1,
    bit_depth    = 32,
    payload      = payload,         # raw bytes of float32 samples
)

print(f"CRC-32: {crc:08X}")   # e.g.  BC5C582D
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `version` | `int` | Frame version (always 1) |
| `frame_id` | `int` | Sequential frame index (0, 1, 2 ...) |
| `timestamp_ms` | `float` | Wall-clock timestamp in milliseconds |
| `sample_rate` | `int` | Hz (e.g. 48000) |
| `channels` | `int` | Number of channels (1 = mono) |
| `bit_depth` | `int` | Bits per sample (32 for float32) |
| `payload` | `bytes` | Raw bytes of the float32 sample array |

**Returns:** `int` — 32-bit unsigned CRC value.

> **Identical to:** `zlib.crc32(struct.pack(">BIdIBBI", ...) + payload) & 0xFFFFFFFF`

---

## Architecture

```text
                    ┌─────────────────────────────┐
                    │      NORMAL MODE             │
  Microphone ──────>│  sd.rec() (full capture)     │
                    │  C batch_encode()            │
                    │  C compute_frame_crc() ×N    │
                    │  write .vtxt (all at once)   │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │      LIVE MODE               │
  Microphone ──────>│  sd.InputStream (callback)   │
                    │    ↓ every 20ms              │
                    │  queue → C batch_encode()    │
                    │  C compute_frame_crc()       │
                    │  write [FRAME] + f.flush()   │
                    │  (file grows live on disk)   │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │      DECODE (both modes)     │
  .vtxt ───────────>│  parse [FRAME] blocks        │
                    │  C batch_decode()            │
                    │  C CRC-32 verify             │
                    │  gap detection → silence     │
                    │  save WAV + play             │
                    └─────────────────────────────┘
```

---

## VTXT Format

```text
# ================================================================
# wavcore VTXT  v1.0
# Recorded : 2026-04-21 12:00:00 UTC
# ================================================================

[FILE_HEADER]
CODEC_VERSION=1
FILE_VERSION=1
TOTAL_FRAMES=500
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
FRAME_MS=20
DURATION_MS=10000.000000
CREATED_UNIX=1745467200
CREATED_UTC=2026-04-21 12:00:00 UTC
[/FILE_HEADER]

[FRAME]
FRAME_ID=0
FRAME_VERSION=1
TIMESTAMP_MS=1745467200000.000000
SAMPLE_RATE=48000
CHANNELS=1
BIT_DEPTH=32
PAYLOAD_LEN=3840
SAMPLES_COUNT=960
ORIG_CRC32=BC5C582D
SAMPLES_HEX=3C8B43963D0A12F4...
[/FRAME]
```

Live mode files also include `RECORD_MODE=LIVE` in the header.

---

## Performance

| Operation | Frames | Time |
|---|---:|---:|
| Encode (C cffi) | 500 | ~7.5 ms |
| Decode (C cffi) | 500 | ~4.6 ms |
| CRC verify (C) | 500 | ~7.4 ms |
| Full pipeline | 500 | ~35.8 ms |

Real-time budget per 20ms frame: **20,000 µs**
WavCore encodes in: **~15 µs/frame** (1326× faster than real-time)

---

## Integration Examples

### 1. Direct `.vtxt` → WAV (no recording needed)

```python
import wavcore

# You already have a .vtxt file — just convert it
stats = wavcore.decode(
    vtxt_path  = "existing_voice.vtxt",
    output_wav = "output.wav",
    play       = False,
)
print(f"Done — {stats['duration_s']:.1f}s  |  {stats['integrity_pct']:.1f}% intact")
```

### 2. Live Record Then Decode

```python
import wavcore

# Step 1 — record live (press ENTER to stop)
rec = wavcore.live_record("voice.vtxt", "orig.wav", max_duration=120)
print(f"Captured {rec['frames']} frames ({rec['duration_ms']/1000:.1f}s)")

# Step 2 — decode immediately
dec = wavcore.decode("voice.vtxt", "reconstructed.wav", play=True)
print(f"Integrity: {dec['integrity_pct']:.2f}%")
```

### 3. Voice Messaging (HTTP)

```python
import wavcore, requests

# === SENDER ===
wavcore.record("message.vtxt", "send_orig.wav", duration=5)
with open("message.vtxt", "r") as f:
    payload = f.read()

requests.post(
    "https://api.myapp.com/voice/send",
    data=payload.encode("utf-8"),
    headers={"Content-Type": "text/plain; charset=utf-8"},
)

# === RECEIVER ===
response = requests.get("https://api.myapp.com/voice/recv/msg123")
with open("received.vtxt", "w", encoding="utf-8") as f:
    f.write(response.text)

result = wavcore.decode("received.vtxt", "playback.wav", play=True)
print(f"Played {result['duration_s']:.1f}s  |  {result['integrity_pct']:.1f}% intact")
```

### 4. Firebase Realtime Database

```python
import wavcore
from firebase_admin import db

# Record and encode
wavcore.record("voice.vtxt", "voice.wav", duration=5)
with open("voice.vtxt", "r") as f:
    vtxt_data = f.read()

# Push as text to Firebase
ref = db.reference("voice_messages")
ref.push({"sender": "Alice", "vtxt": vtxt_data})

# On receiver — read and decode
messages = ref.get()
for key, msg in messages.items():
    with open("recv.vtxt", "w") as f:
        f.write(msg["vtxt"])
    wavcore.decode("recv.vtxt", "playback.wav", play=True)
```

### 5. SQLite Storage

```python
import wavcore, sqlite3

conn = sqlite3.connect("voices.db")
conn.execute("""CREATE TABLE IF NOT EXISTS voice_messages
    (id INTEGER PRIMARY KEY, sender TEXT, vtxt_data TEXT, created_at REAL)""")

# Record and store
stats = wavcore.record("temp.vtxt", "temp_orig.wav", duration=5)
with open("temp.vtxt") as f:
    vtxt = f.read()
conn.execute(
    "INSERT INTO voice_messages (sender, vtxt_data, created_at) VALUES (?, ?, ?)",
    ("Alice", vtxt, stats["created_unix"])
)
conn.commit()

# Retrieve and decode
row = conn.execute(
    "SELECT vtxt_data FROM voice_messages ORDER BY id DESC LIMIT 1"
).fetchone()
with open("playback.vtxt", "w") as f:
    f.write(row[0])
wavcore.decode("playback.vtxt", "playback.wav", play=True)
```

### 6. Custom Frame-by-Frame Streaming

```python
import wavcore, numpy as np, sounddevice as sd

SAMPLE_RATE = 48_000
SPF         = 960           # 20ms @ 48kHz
frame_id    = 0
frames_sent = []

def audio_callback(indata, frames, time_info, status):
    global frame_id
    chunk   = np.ascontiguousarray(indata.flatten(), dtype=np.float32)
    hex_str = wavcore.batch_encode(chunk, SPF)[0]
    payload = chunk.tobytes()
    crc     = wavcore.compute_frame_crc(
        1, frame_id,
        time_info.inputBufferAdcTime * 1000,
        SAMPLE_RATE, 1, 32, payload
    )
    frames_sent.append((frame_id, hex_str, f"{crc:08X}"))
    frame_id += 1

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                    dtype="float32", blocksize=SPF,
                    callback=audio_callback):
    input("Streaming... press ENTER to stop\n")

print(f"Captured {len(frames_sent)} frames")
```

### 7. Checking Signal Quality

```python
import wavcore

rec  = wavcore.record("audio.vtxt", "orig.wav", duration=10)
dec  = wavcore.decode("audio.vtxt", "recon.wav", play=False)

# Recording quality
if rec["peak"] < 0.001:
    print("WARNING: Mic too quiet — check OS audio settings")
elif rec["peak"] > 0.95:
    print("WARNING: Clipping detected — move mic further away")
else:
    print(f"Good signal: peak={rec['peak']:.4f}  rms={rec['rms']:.4f}")

# Decode quality
if dec["integrity_pct"] == 100.0:
    print("Perfect reconstruction — bit-identical to original")
elif dec["integrity_pct"] >= 95.0:
    print(f"Good: {dec['integrity_pct']:.1f}% frames valid")
else:
    print(f"Degraded: {dec['bad_frames']} frames corrupted/missing")

# Speed
fps = rec["frames"] / (rec["encode_ms"] / 1000)
print(f"Encode: {rec['encode_ms']:.1f} ms  ({fps:.0f} frames/s)")
print(f"Decode: {dec['total_ms']:.1f} ms")
```

---

## Configuration Reference

| Parameter | Default | Range | Notes |
|---|---|---|---|
| `duration` | `10` | 1–3600 s | `record()` only — fixed length |
| `max_duration` | `60` | 1–3600 s | `live_record()` only — press ENTER to stop early |
| `sample_rate` | `48000` | 8000–192000 | Higher = better quality, larger file |
| `frame_ms` | `20` | 10–100 | Smaller = lower latency |
| `play` | `True` | True/False | Set `False` on servers without audio output |

### Sample Rate vs File Size (10 seconds)

| Sample Rate | Samples/Frame (20ms) | File Size | Quality |
|---|---|---|---|
| 8,000 Hz | 160 → 1,280 chars | ~660 KB | Phone call |
| 16,000 Hz | 320 → 2,560 chars | ~1.3 MB | VoIP |
| 44,100 Hz | 882 → 7,056 chars | ~3.6 MB | CD quality |
| **48,000 Hz** | **960 → 7,680 chars** | **~3.9 MB** | **Default** |
| 96,000 Hz | 1,920 → 15,360 chars | ~7.8 MB | Professional |

---

## Output Files

| File | Created by | Contains |
|---|---|---|
| `voice_data.vtxt` | `record()` / `live_record()` | Text-encoded audio frames |
| `original_reference.wav` | `record()` / `live_record()` | Raw mic capture (ground truth) |
| `reconstructed.wav` | `decode()` | Rebuilt audio from `.vtxt` |

---

## Troubleshooting

### "Pure-Python fallback" instead of C engine

```bash
pip install -e .          # triggers C compilation
# or reinstall from PyPI
pip install --force-reinstall wavcore
```

### No audio recorded (`peak < 0.001`)

```python
import sounddevice
print(sounddevice.query_devices())   # check available devices
```

Also check OS microphone permissions (Settings → Privacy → Microphone).

### `sounddevice` not found

```bash
pip install sounddevice
# Linux also needs:
sudo apt install libportaudio2
```

### CRC failures after local record+decode

Indicates file corruption (partial overwrite). Re-record to get a clean file.
For network transmission, add retry logic and re-request specific frames.

### Live mode: ENTER key not stopping

This can happen in some terminal environments. Press `Ctrl+C` as an alternative stop signal.

---

## Documentation

Full technical docs are in the `docs/` folder:

| File | Contents |
|---|---|
| `docs/ARCHITECTURE.md` | C engine, build system, internal design |
| `docs/VTXT_FORMAT_SPEC.md` | Complete .vtxt format specification |
| `docs/PERFORMANCE_GUIDE.md` | Benchmarks, tuning, profiling |
| `docs/USER_MANUAL.md` | Detailed usage guide |
| `docs/PYPI_PUBLISHING_GUIDE.md` | How to publish to PyPI |

---

## Developer

**Prashant Pandey**

- technical121@gmail.com
- codex.admim@gmail.com

GitHub: https://github.com/Zyro-Hub/wavecore
PyPI: https://pypi.org/project/wavcore/

---

## License

MIT License
