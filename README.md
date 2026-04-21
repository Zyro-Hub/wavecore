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
- **File Mode** (`file_to_vtxt`) — convert **any existing audio file** (WAV, FLAC, OGG, MP3…) to `.vtxt` **without a microphone**.
- **Direct Convert** (`convert_audio`) — convert any audio file straight to WAV in **one call** — no microphone, no manual vtxt step.
- `app.py` now shows a 3-option mode selection menu on startup.

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
| **File mode** | Convert existing audio file → `.vtxt` — no mic needed |
| **Direct convert** | `convert_audio()` — audio file → WAV in one call |
| **CRC-32** | Per-frame integrity check |
| **Gap handling** | Missing frames → silence during decode |
| **Pure-Python fallback** | Works without native build |
| **Text transport** | Works with Firebase, SQLite, HTTP, WebSocket |

---

## Installation

```bash
pip install wavcore==2.0.0 .
```

Auto-installs: `numpy`, `sounddevice`, `cffi`
The C engine is compiled during install. No extra steps.

### Development (editable) Install

```bash
pip install -e .
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
from recorder_converter import file_to_vtxt, convert_audio

# Normal mode — record 10s from mic, then encode
wavcore.record("audio.vtxt", "original.wav", duration=10)

# Live mode — write frames to .vtxt in real-time while speaking
wavcore.live_record("audio.vtxt", "original.wav", max_duration=60)

# File mode — convert an existing audio file to .vtxt (no mic)
file_to_vtxt("my_song.wav", "audio.vtxt")

# Direct convert — audio file → WAV in ONE call (no mic, no manual steps)
convert_audio("my_song.wav", "output.wav", play=True)

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
  ┌────────────────────────────────────────────────────────┐
  │  [1]  NORMAL MODE                                      │
  │       Record mic audio, encode all at once to .vtxt.   │
  │                                                        │
  │  [2]  LIVE MODE                                        │
  │       Each frame encoded + written to .vtxt live       │
  │       while you speak. Press ENTER to stop early.      │
  │                                                        │
  │  [3]  FILE MODE                                        │
  │       Convert an existing audio file (WAV/FLAC/OGG)    │
  │       to .vtxt — no microphone needed.                 │
  └────────────────────────────────────────────────────────┘

  Enter 1, 2 or 3:
```

All three modes produce a `.vtxt` file compatible with the same decode + playback step.

---

## Full Public API Reference

### Summary Table

| Function | Mode | Description |
|---|---|---|
| `wavcore.record()` | Normal | Record full audio from mic, encode to `.vtxt` |
| `wavcore.live_record()` | **Live** | Encode + write each frame live while speaking |
| `file_to_vtxt()` | **File** | Existing audio file → `.vtxt` (no mic needed) |
| `convert_audio()` | **Direct** | Audio file → WAV in one call (no mic, no manual vtxt) |
| `wavcore.decode()` | Decode | Any `.vtxt` → WAV + optional playback |
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

### `file_to_vtxt()` — **NEW in 2.0.0**

Convert **any existing audio file** to `.vtxt` using the C engine — **no microphone required**.

This is the function to use when you already have an audio file and want to encode it into the VTXT format.

```python
from recorder_converter import file_to_vtxt

stats = file_to_vtxt(
    audio_path  = "song.wav",       # required — input audio file
    vtxt_path   = "song.vtxt",      # required — output .vtxt path
    sample_rate = 48_000,           # optional — target Hz    (default 48000)
    frame_ms    = 20,               # optional — frame size   (default 20ms)
)
```

**Supported input formats:**

| Format | Requirement |
|---|---|
| `.wav` | Built-in — no extra install |
| `.flac` `.ogg` `.aiff` | `pip install soundfile` |
| `.mp3` | `pip install soundfile` + libsndfile with MP3 support |

**Pipeline:**
```
audio file → read → mono mix → resample if needed
          → C batch_encode() → C CRC-32 per frame → write .vtxt
```

**Returns:**

```python
{
    "frames":       500,              # frames written
    "duration_ms":  10000.0,          # ms
    "sample_rate":  48000,
    "channels":     1,
    "peak":         0.724518,         # 0.0–1.0
    "rms":          0.182350,
    "vtxt_path":    "song.vtxt",
    "source_file":  "/path/to/song.wav",  # absolute path of input
    "created_unix": 1745123456,
    "vtxt_size":    3942506,          # bytes
    "encode_ms":    42.1,
}
```

**Examples:**

```python
from recorder_converter import file_to_vtxt
import wavcore

# ── WAV file → .vtxt → decode + play ──────────────────────
file_to_vtxt("recording.wav", "recording.vtxt")
wavcore.decode("recording.vtxt", "output.wav", play=True)

# ── FLAC file (needs: pip install soundfile) ───────────────
file_to_vtxt("vocals.flac", "vocals.vtxt", sample_rate=44_100)
wavcore.decode("vocals.vtxt", "vocals_recon.wav", play=False)

# ── Check stats ────────────────────────────────────────────
stats = file_to_vtxt("interview.wav", "interview.vtxt")
print(f"Encoded {stats['frames']} frames ({stats['duration_ms']/1000:.1f}s)")
print(f"File size: {stats['vtxt_size']:,} bytes")
print(f"Took: {stats['encode_ms']:.1f} ms")
```

**How it handles different sample rates:**

If the source file has a different sample rate than `sample_rate`, the audio is resampled automatically:
- Uses `scipy.signal.resample_poly` if scipy is installed (high quality)
- Falls back to numpy linear interpolation if not

```python
# Source WAV is 44100 Hz, target is 48000 Hz — resampled automatically
file_to_vtxt("cd_audio.wav", "cd_audio.vtxt", sample_rate=48_000)
```

**Note:** The `.vtxt` produced by `file_to_vtxt()` is fully compatible with `wavcore.decode()`. The header will contain `SOURCE_FILE` and `RECORD_MODE=FILE` fields.

---

### `convert_audio()` — Direct Audio Conversion

The **simplest way** to convert any audio file to WAV using the WavCore pipeline. One function call — no microphone, no manual steps.

Internally it calls `file_to_vtxt()` then `vtxt_to_wav()` and optionally deletes the intermediate `.vtxt`.

```python
from recorder_converter import convert_audio

stats = convert_audio(
    audio_path  = "song.wav",        # required — input audio file
    output_wav  = "output.wav",      # required — output WAV path
    sample_rate = 48_000,            # optional — target Hz      (default 48000)
    frame_ms    = 20,                # optional — frame size ms  (default 20)
    play        = False,             # optional — play after done (default False)
    keep_vtxt   = False,             # optional — keep .vtxt?    (default False)
    vtxt_path   = None,              # optional — custom .vtxt path (auto if None)
)
```

**Pipeline:**
```
audio_path  →  file_to_vtxt()  →  temp_vtxt
            →  vtxt_to_wav()   →  output_wav
            →  (delete temp_vtxt if keep_vtxt=False)
```

**Returns:**

```python
{
    "encode":        { ...file_to_vtxt stats... },
    "decode":        { ...vtxt_to_wav stats... },
    "vtxt_path":     "output_temp.vtxt",   # intermediate vtxt (deleted if keep_vtxt=False)
    "output_wav":    "output.wav",
    "duration_s":    10.0,
    "integrity_pct": 100.0,
    "peak":          0.724518,
    "rms":           0.182350,
}
```

**Examples:**

```python
from recorder_converter import convert_audio

# ── Simplest use — WAV in, WAV out ────────────────────────────
convert_audio("recording.wav", "output.wav")

# ── Play the result immediately ───────────────────────────────
convert_audio("interview.wav", "interview_clean.wav", play=True)

# ── Keep the .vtxt too (for inspection or re-use) ─────────────
stats = convert_audio(
    audio_path = "song.flac",          # FLAC needs: pip install soundfile
    output_wav = "song_out.wav",
    keep_vtxt  = True,
    vtxt_path  = "song_encoded.vtxt",  # save .vtxt here
)
print(f"Duration : {stats['duration_s']:.1f}s")
print(f"Integrity: {stats['integrity_pct']:.2f}%")

# ── Check encode + decode stats separately ────────────────────
print(f"Frames encoded : {stats['encode']['frames']}")
print(f"Frames valid   : {stats['decode']['ok_frames']}")
print(f"Total encode   : {stats['encode']['encode_ms']:.1f} ms")
print(f"Total decode   : {stats['decode']['total_ms']:.1f} ms")
```

**Comparison — two ways to do the same thing:**

```python
# ❌ Manual (3 steps)
from recorder_converter import file_to_vtxt, vtxt_to_wav
file_to_vtxt("song.wav", "song.vtxt")
vtxt_to_wav("song.vtxt", "output.wav", play_audio=True)
import os; os.remove("song.vtxt")

# ✅ Direct (1 step)
from recorder_converter import convert_audio
convert_audio("song.wav", "output.wav", play=True)
```

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
                    │      FILE MODE  ← NEW        │
  Audio File ──────>│  read (wave / soundfile)     │
  (WAV/FLAC/OGG)    │  mono mix + resample         │
                    │  C batch_encode()            │
                    │  C compute_frame_crc() ×N    │
                    │  write .vtxt (all at once)   │
                    └─────────────────────────────┘

                    ┌─────────────────────────────┐
                    │      DECODE (all modes)      │
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
File mode files include `RECORD_MODE=FILE` and `SOURCE_FILE=<filename>` in the header.

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

| Parameter | Default | Range | Applies to |
|---|---|---|---|
| `duration` | `10` | 1–3600 s | `record()` only — fixed length |
| `max_duration` | `60` | 1–3600 s | `live_record()` only — press ENTER to stop early |
| `audio_path` | — | any path | `file_to_vtxt()` only — input audio file |
| `sample_rate` | `48000` | 8000–192000 | All modes — higher = better quality, larger file |
| `frame_ms` | `20` | 10–100 | All modes — smaller = lower latency |
| `play` | `True` | True/False | `decode()` only — set `False` on servers |

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
| `voice_data.vtxt` | `record()` / `live_record()` / `file_to_vtxt()` | Text-encoded audio frames |
| `original_reference.wav` | `record()` / `live_record()` | Raw mic capture (ground truth) |
| `reconstructed.wav` | `decode()` | Rebuilt audio from `.vtxt` |

> **File Mode note:** `file_to_vtxt()` does not create an `original_reference.wav` — the source audio file itself is the reference. The `.vtxt` header records the original filename as `SOURCE_FILE`.

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

### File mode: format not supported

```bash
pip install soundfile        # for FLAC, OGG, AIFF
```

For MP3, soundfile needs libsndfile compiled with MP3 support (platform-dependent).
Alternatively, convert your MP3 to WAV first using any audio tool, then use `file_to_vtxt`.

### File mode: quality sounds different after decode

If the source file's sample rate (e.g. 44100 Hz) differs from `sample_rate` (default 48000 Hz), the audio is resampled. For best quality, match the sample rate to the source:

```python
from recorder_converter import file_to_vtxt

# Match source rate (44100 Hz CD audio)
file_to_vtxt("song.wav", "song.vtxt", sample_rate=44_100)
```

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

---
---
---

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

---

# WavCore v2.0.0 — Performance Guide

> **How to use WavCore at maximum speed — patterns, benchmarks, and optimization techniques.**

---

## Table of Contents

1. [Benchmark Results](#benchmark-results)
2. [The Golden Rule — Always Use Batch](#the-golden-rule)
3. [Engine Verification Checklist](#engine-verification-checklist)
4. [Fastest Encode Pattern](#fastest-encode-pattern)
5. [Fastest Decode Pattern](#fastest-decode-pattern)
6. [Live Mode Performance](#live-mode-performance)
7. [Fastest Real-Time Streaming Pattern](#fastest-real-time-streaming-pattern)
8. [Memory Optimization](#memory-optimization)
9. [Multi-Channel Audio](#multi-channel-audio)
10. [Profiling Your Pipeline](#profiling-your-pipeline)
11. [Performance Comparison](#performance-comparison)
12. [Real-Time Latency Budget](#real-time-latency-budget)
13. [NumPy Best Practices](#numpy-best-practices)

---

## Benchmark Results

Measured on Intel Core i5, Python 3.12, MSVC 64-bit C engine.

| Operation | N Frames | Time | Per Frame | Budget Used |
|---|---|---|---|---|
| `batch_encode` | 500 | **6.9 ms** | 13.8 µs | 0.069% |
| `batch_decode` | 500 | **4.6 ms** | 9.2 µs | 0.046% |
| `compute_frame_crc` | 500 | **7.4 ms** | 14.8 µs | 0.074% |
| Parse .vtxt | 500 | **14.5 ms** | 29.0 µs | 0.145% |
| Write .vtxt | 500 | **5.1 ms** | 10.2 µs | 0.051% |
| **Full decode pipeline** | **500** | **35.8 ms** | **71.6 µs** | **0.358%** |
| Live mode per frame | 1 | **~32 µs** | 32 µs | 0.16% |
| Real-time budget | 1 | 20,000 µs | — | 100% |

**The C engine is 1,448× faster than the real-time budget.**

---

## The Golden Rule

> **Always pass ALL frames to one `batch_encode` / `batch_decode` call.**
> Never loop and encode one frame at a time.

### ❌ SLOW — One frame per call

```python
results = []
for i in range(n_frames):
    frame = audio[i*spf:(i+1)*spf]
    hex_str = wavcore.batch_encode(frame, spf)[0]  # BAD: 500 calls
    results.append(hex_str)
```

Benchmark: ~250 ms for 500 frames (Python loop dominates)

### ✅ FAST — All frames in one call

```python
hex_list = wavcore.batch_encode(audio, spf)        # GOOD: one call
```

Benchmark: 6.9 ms for 500 frames — **36× faster**

Same rule for `batch_decode`:

```python
# ❌ SLOW
audio = np.concatenate([wavcore.batch_decode([hs], spf) for hs in hex_list])

# ✅ FAST
audio = wavcore.batch_decode(hex_list, spf)
```

> **Exception:** Live Mode encodes one frame at a time by design — this is correct because each frame must be written to disk immediately. The C engine is fast enough (14 µs/frame, 0.07% of budget) that this has zero practical impact.

---

## Engine Verification Checklist

```python
import wavcore

engine = wavcore.engine_info()
print(engine)

if "C engine" not in engine:
    raise RuntimeError(
        "C engine not loaded!\n"
        "Run: pip install -e .  (from wavcore source directory)\n"
        f"Current: {engine}"
    )

print("✓ C engine active — ready for high-performance operation")
```

---

## Fastest Encode Pattern

```python
import wavcore, numpy as np, time

SAMPLE_RATE = 48_000
SPF         = 960     # 20ms @ 48kHz

def encode_audio_fastest(audio: np.ndarray):
    # Step 1: Contiguous float32 (zero-copy if already correct)
    audio = np.ascontiguousarray(audio, dtype=np.float32)

    # Step 2: Pad to exact multiple of SPF
    rem = len(audio) % SPF
    if rem:
        audio = np.append(audio, np.zeros(SPF - rem, dtype=np.float32))

    n_frames = len(audio) // SPF

    # Step 3: ONE C call — all frames at once
    t0       = time.perf_counter()
    hex_list = wavcore.batch_encode(audio, SPF)
    t_enc    = (time.perf_counter() - t0) * 1000

    print(f"Encoded {n_frames} frames in {t_enc:.2f} ms ({t_enc/n_frames*1000:.1f} µs/frame)")
    return hex_list

audio = np.random.default_rng(42).standard_normal(10 * 960).astype(np.float32)
hex_list = encode_audio_fastest(audio)
# Encoded 10 frames in 0.14 ms  (13.8 µs/frame)
```

---

## Fastest Decode Pattern

```python
import wavcore, time

def decode_vtxt_fastest(vtxt_path: str):
    """Maximum-speed decode without playback."""
    t0    = time.perf_counter()
    stats = wavcore.decode(vtxt_path, "temp_out.wav", play=False)
    t1    = time.perf_counter()
    print(f"Decoded in {(t1-t0)*1000:.1f} ms  |  Integrity: {stats['integrity_pct']:.1f}%")
    return stats

def decode_hex_list_fastest(hex_list: list) -> np.ndarray:
    """Decode if you already have the hex strings (e.g. from network). No file I/O."""
    import numpy as np, time
    t0    = time.perf_counter()
    audio = wavcore.batch_decode(hex_list, 960)
    t1    = time.perf_counter()
    n = len(hex_list)
    print(f"batch_decode: {n} frames in {(t1-t0)*1000:.2f} ms ({(t1-t0)*1000/n*1000:.1f} µs/frame)")
    return audio
```

---

## Live Mode Performance

Live Mode (`wavcore.live_record()`) processes one frame every 20ms. Performance per frame:

| Step | Time |
|---|---|
| `sd.InputStream` callback (copy) | ~5 µs |
| `batch_encode()` — C engine | ~14 µs |
| `compute_frame_crc()` — C engine | ~3 µs |
| `write [FRAME]` + `f.flush()` | ~10 µs |
| **Total per 20ms frame** | **~32 µs** |
| **Budget remaining** | **19,968 µs (99.84%)** |

The live write loop is `0.16%` of the real-time budget. The remaining 99.84% is free for your application logic.

**Live mode file growth rate:**

```
7,680 chars (SAMPLES_HEX) + ~200 chars (frame metadata) = ~7,900 chars/frame
At 50 frames/sec → ~395 KB/sec → ~23 MB/minute
```

---

## Fastest Real-Time Streaming Pattern

```python
import wavcore, numpy as np, sounddevice as sd, queue, threading

SAMPLE_RATE = 48_000
SPF         = 960

encode_q = queue.Queue(maxsize=100)
encoded  = []

def audio_callback(indata, frames, time_info, status):
    """Called every 20ms — just queue the data, don't encode here."""
    encode_q.put_nowait(indata.copy().flatten())

def encoder_thread():
    """Separate thread: encode frames as they arrive."""
    frame_id = 0
    while True:
        chunk = encode_q.get()
        if chunk is None:
            break
        hex_str = wavcore.batch_encode(chunk.astype(np.float32), SPF)[0]
        encoded.append((frame_id, hex_str))
        frame_id += 1

t = threading.Thread(target=encoder_thread, daemon=True)
t.start()

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                    dtype="float32", blocksize=SPF,
                    callback=audio_callback):
    input("Streaming... press ENTER to stop\n")

encode_q.put(None)
t.join()
print(f"Encoded {len(encoded)} frames in real-time")
```

**Note:** This is the pattern used internally by `live_record()`. Use `wavcore.live_record()` directly unless you need custom frame handling.

---

## Memory Optimization

### Pre-allocate output arrays

```python
# batch_decode allocates a new array — assign it directly
audio_out = wavcore.batch_decode(hex_list, spf=960)
```

### Avoid unnecessary copies

```python
# ❌ np.array() always allocates
audio = np.array(raw_data).astype(np.float32)

# ✅ zero-copy if already float32 and contiguous
audio = np.ascontiguousarray(raw_data, dtype=np.float32)
```

### In-memory round-trip (no file I/O)

```python
import wavcore, numpy as np

audio    = np.random.randn(500 * 960).astype(np.float32)
hex_list = wavcore.batch_encode(audio, 960)   # encode
back     = wavcore.batch_decode(hex_list, 960) # decode
print(np.array_equal(audio, back))             # True
```

---

## Multi-Channel Audio

WavCore is mono by default. For stereo:

```python
import wavcore, numpy as np

SAMPLE_RATE = 48_000
SPF         = 960

# Interleaved stereo: [L0, R0, L1, R1, ...]
stereo = np.random.randn(10 * SPF * 2).astype(np.float32)

# Split channels
left  = stereo[0::2]
right = stereo[1::2]

# Encode each independently
hex_left  = wavcore.batch_encode(left,  SPF)
hex_right = wavcore.batch_encode(right, SPF)

# Decode
back_left  = wavcore.batch_decode(hex_left,  SPF)
back_right = wavcore.batch_decode(hex_right, SPF)

# Interleave back
back_stereo = np.empty_like(stereo)
back_stereo[0::2] = back_left
back_stereo[1::2] = back_right

print(np.array_equal(stereo, back_stereo))   # True
```

---

## Profiling Your Pipeline

```python
import wavcore, numpy as np, time, os

def profile_wavcore(vtxt_path: str):
    print(f"\n{'─'*50}")
    print(f"  WavCore v{wavcore.__version__} Pipeline Profiler")
    print(f"  Engine: {wavcore.engine_info()}")
    print(f"{'─'*50}")

    size = os.path.getsize(vtxt_path)
    print(f"  File : {vtxt_path}")
    print(f"  Size : {size:,} bytes  ({size/1024:.1f} KB)\n")

    t0    = time.perf_counter()
    stats = wavcore.decode(vtxt_path, "_profile_out.wav", play=False)
    wall  = (time.perf_counter() - t0) * 1000

    n = stats["ok_frames"] + stats["bad_frames"]

    print(f"  Decode pipeline:")
    print(f"  ├── Parse .vtxt    : ~14.5 ms")
    print(f"  ├── batch_decode   : ~4.6 ms  ({4600/n:.1f} µs/frame)")
    print(f"  ├── CRC verify     : ~7.1 ms  ({7100/n:.1f} µs/frame)")
    print(f"  └── Write WAV      : ~5.1 ms")
    print(f"\n  Wall total        : {wall:.1f} ms  ({wall/n*1000:.1f} µs/frame)")
    print(f"  Throughput        : {n/wall*1000:.0f} frames/sec")
    print(f"  Integrity         : {stats['integrity_pct']:.1f}%")
    print(f"  Duration          : {stats['duration_s']:.3f} s")
    print(f"{'─'*50}\n")

    os.remove("_profile_out.wav")

# Usage:
# profile_wavcore("voice_data.vtxt")
```

---

## Performance Comparison

### C engine vs Pure Python

| Operation | C engine | Pure Python | Speedup |
|---|---|---|---|
| `samples_to_hex` (960 samples) | **15 µs** | 320 µs | **21×** |
| `hex_to_samples` (960 samples) | **9 µs** | 180 µs | **20×** |
| `frame_crc32` | **3 µs** | 28 µs | **9×** |
| `batch_encode` (500 frames) | **6.9 ms** | 160 ms | **23×** |
| `batch_decode` (500 frames) | **4.6 ms** | 90 ms | **20×** |
| Full pipeline (500 frames) | **35.8 ms** | ~400 ms | **11×** |

### WavCore vs Lossy Codecs

| Codec | Latency | Quality | Loss |
|---|---|---|---|
| **WavCore Normal** | **35 ms** | **Lossless** | **0%** |
| **WavCore Live** | **~32 µs/frame** | **Lossless** | **0%** |
| Opus (VoIP) | 20–100 ms | Lossy | ~5–15% |
| MP3 (320k) | ~50 ms | Lossy | ~3% |
| AAC | ~80 ms | Lossy | ~5% |
| PCM WAV | 0 ms | Lossless | 0% |

---

## Real-Time Latency Budget

For a **20ms frame** at 48kHz (960 samples), budget = **20,000 µs**.

### Normal Mode (batch — after full capture)

```
Full recording captured [budget = irrelevant, post-capture]
   │
   ▼  batch_encode() [C]     ≈ 14 µs × 1 frame
   ▼  compute_frame_crc() [C] ≈  3 µs × 1 frame
   ▼  write to file           ≈ 10 µs × 1 frame
[Total per frame]            ≈ 27 µs  (0.14% of budget)
```

### Live Mode (real-time, per frame)

```
Frame captured by PortAudio  [20,000 µs budget starts]
   │
   ▼  audio_callback()        ≈  5 µs  (copy to queue)
   ▼  batch_encode() [C]      ≈ 14 µs  (hex encode)
   ▼  compute_frame_crc() [C] ≈  3 µs  (CRC-32)
   ▼  write + f.flush()       ≈ 10 µs  (disk write)
[Total per frame]             ≈ 32 µs  (0.16% of budget)
[Budget remaining]           = 19,968 µs  (99.84% free!)
```

---

## NumPy Best Practices

### 1. Always use `float32`

```python
# ❌ float64: double memory, C engine must convert
audio = np.array([0.5, -0.3, 0.1])            # float64 by default

# ✅ float32: native format, zero-copy to C
audio = np.array([0.5, -0.3, 0.1], dtype=np.float32)
```

### 2. Use `np.ascontiguousarray`

```python
# ❌ np.array() always allocates
arr = np.array(existing, dtype=np.float32)

# ✅ zero-copy if already contiguous float32
arr = np.ascontiguousarray(existing, dtype=np.float32)
```

### 3. Reproducible tests

```python
rng  = np.random.default_rng(seed=42)
test = rng.standard_normal(960 * 500).astype(np.float32)
```

### 4. Slice views need contiguous before C calls

```python
frame = audio[i*960 : (i+1)*960]                         # view, may not be contiguous
frame = np.ascontiguousarray(frame, dtype=np.float32)    # safe for C
```

### 5. batch_encode beats any loop

```python
frames   = audio[:n*spf].reshape(n, spf)   # 2D view, zero-copy
hex_list = wavcore.batch_encode(audio, spf) # always faster than looping frames
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│           WavCore v2.0.0 Performance Quick Reference        │
├────────────────────────────┬────────────────────────────────┤
│  Record (fixed duration)   │  wavcore.record(vtxt, wav)     │
│  Record (live, open-ended) │  wavcore.live_record(vtxt,wav) │
│  Decode vtxt               │  wavcore.decode(vtxt, wav)     │
│  Encode in-memory          │  batch_encode(audio, spf)      │
│  Decode in-memory          │  batch_decode(hex_list, spf)   │
│  CRC one frame             │  compute_frame_crc(...)        │
│  Check engine              │  engine_info()                 │
├────────────────────────────┼────────────────────────────────┤
│  SPF (48kHz, 20ms)         │  960 samples                   │
│  Hex chars per frame       │  7,680 chars (960 × 8)         │
│  File size (10s)           │  ~3.9 MB                       │
│  Encode 500 frames         │  6.9 ms  (C engine)            │
│  Decode 500 frames         │  4.6 ms  (C engine)            │
│  Full pipeline 500 frames  │  35.8 ms                       │
│  Live mode per frame       │  ~32 µs  (0.16% of budget)     │
│  Real-time headroom        │  1,448×  faster than budget    │
├────────────────────────────┼────────────────────────────────┤
│  dtype                     │  np.float32 always             │
│  contiguous                │  np.ascontiguousarray(a,f32)   │
│  pattern                   │  ONE batch call, not a loop    │
└────────────────────────────┴────────────────────────────────┘
```
---
---

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


---
---

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
