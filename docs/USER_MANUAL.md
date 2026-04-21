# WavCore — User Manual

> **Everything you need to start recording, encoding, and reconstructing audio.**

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start (3 lines)](#quick-start)
3. [Core Concepts](#core-concepts)
4. [High-Level API](#high-level-api)
   - [wavcore.record()](#wavcore-record)
   - [wavcore.decode()](#wavcore-decode)
   - [wavcore.engine_info()](#wavcore-engine_info)
5. [Low-Level Frame API](#low-level-frame-api)
6. [Working with Stats Dicts](#working-with-stats-dicts)
7. [Integration Examples](#integration-examples)
8. [Running app.py](#running-apppy)
9. [Troubleshooting](#troubleshooting)
10. [Configuration Reference](#configuration-reference)

---

## Installation

### Standard Install

```bash
pip install wavcore
```

This automatically installs:
- `numpy` — array math
- `sounddevice` — microphone + speaker access
- `cffi` — C extension compiler

And compiles the C engine during install. No extra steps needed.

### Development Install (editable)

Use this if you have the source code and want to modify wavcore:

```bash
cd "path/to/voice experiment"
pip install -e .
```

After this, any changes you make to `wavcore/` take effect immediately —
no reinstall needed.

### Verify Installation

```python
import wavcore
print(wavcore.__version__)   # → 1.0.0
print(wavcore.engine_info()) # → C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast
```

---

## Quick Start

Record 10 seconds, encode to text format, decode back to audio and play:

```python
import wavcore

wavcore.record("audio.vtxt", "original.wav")         # step 1: record
wavcore.decode("audio.vtxt", "reconstructed.wav")    # step 2: reconstruct
```

That's it. Two function calls. The C engine handles everything at 9 µs/frame.

---

## Core Concepts

### What is a .vtxt file?

A `.vtxt` file is WavCore's lossless audio text format.
It contains your audio encoded as **uppercase hexadecimal strings** — one line per 20ms frame.

- **Lossless:** Every bit of your float32 audio is preserved exactly
- **Human-readable:** You can open it in Notepad and read the metadata
- **Portable:** It's plain text — send it over HTTP, email, WebSocket, store in a database

### What is a Frame?

WavCore splits audio into **frames** of fixed duration (default: 20ms = 960 samples @ 48kHz).
Each frame has:
- A unique `FRAME_ID` (sequential integer)
- A `TIMESTAMP_MS` (wall-clock time of capture)
- A `CRC-32` checksum (for integrity verification)
- A `SAMPLES_HEX` hex string (the actual audio data)

### Why Lossless?

Normal audio codecs (MP3, AAC, Opus) use psychoacoustic compression and **discard data**.
WavCore never discards anything. Every `float32` sample value is encoded as its exact
IEEE-754 bit pattern in hex. Decoding gives back the **identical bytes**, not an approximation.

```python
import numpy as np
import wavcore

original = np.array([0.5, -0.25, 0.1234], dtype=np.float32)
hex_str  = wavcore.batch_encode(original, 3)[0]            # encode
back     = wavcore.batch_decode([hex_str], 3)              # decode

print(np.array_equal(original, back))   # → True  (bit-perfect)
```

---

## High-Level API

### `wavcore.record()`

```python
stats = wavcore.record(
    vtxt_path   = "audio.vtxt",      # required: output .vtxt path
    orig_wav    = "original.wav",    # optional: ground-truth WAV (default "original.wav")
    duration    = 10,                # optional: seconds to record  (default 10)
    sample_rate = 48_000,            # optional: Hz                 (default 48000)
    frame_ms    = 20,                # optional: frame size in ms   (default 20)
)
```

**What it does:**
1. Counts down 3 seconds ("Starting in 3... 2... 1...")
2. Records `duration` seconds from the default microphone
3. Saves the raw recording as `orig_wav` (16-bit PCM WAV — ground truth)
4. Encodes ALL frames using the C engine in one batch call
5. Computes CRC-32 for every frame in C
6. Writes the `.vtxt` file

**Returns a dict:**

```python
{
    "frames":        500,           # number of frames written
    "duration_ms":   10000.0,       # total audio length in milliseconds
    "sample_rate":   48000,         # Hz
    "channels":      1,             # mono
    "peak":          0.518646,      # peak amplitude (0.0 to 1.0)
    "rms":           0.055205,      # RMS level (indicates loudness)
    "vtxt_path":     "audio.vtxt",  # path to .vtxt file
    "orig_wav_path": "original.wav",
    "created_unix":  1745123456,    # Unix timestamp
    "vtxt_size":     3942506,       # .vtxt file size in bytes
    "encode_ms":     35.2,          # total encode time in ms
}
```

**Tips:**
- Speak clearly and keep the microphone within 30cm
- If `peak < 0.001`, the mic is too quiet or not configured — check OS audio settings
- `rms > 0.05` indicates a good signal level

---

### `wavcore.decode()`

```python
stats = wavcore.decode(
    vtxt_path  = "audio.vtxt",       # required: input .vtxt file
    output_wav = "reconstructed.wav",# optional: output WAV path
    play       = True,               # optional: play audio after decode (default True)
)
```

**What it does:**
1. Parses the `.vtxt` file line-by-line
2. Decodes ALL frames using the C engine in one batch call (9 µs/frame)
3. Verifies the CRC-32 of every frame using the C engine
4. Inserts silence for any missing frame IDs (gap handling)
5. Saves the reconstructed WAV file
6. Plays the audio through the default speaker (if `play=True`)

**Returns a dict:**

```python
{
    "ok_frames":     500,            # frames that passed CRC check
    "bad_frames":    0,              # frames that failed CRC or were missing
    "integrity_pct": 100.0,          # percentage of valid frames
    "duration_s":    10.0,           # reconstructed audio length in seconds
    "peak":          0.518646,       # peak amplitude
    "rms":           0.055205,       # RMS level
    "output_wav":    "reconstructed.wav",
    "sample_rate":   48000,
    "total_ms":      35.8,           # entire decode pipeline in milliseconds
}
```

**Tips:**
- Set `play=False` if you don't want immediate playback (e.g. server-side processing)
- Check `integrity_pct` — 100% means perfect lossless reconstruction
- If `bad_frames > 0`, some frames had transmission errors or corruption

---

### `wavcore.engine_info()`

```python
print(wavcore.engine_info())
```

Returns one of:
```
C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast    ← ideal (after pip install)
C engine [cffi / local build .pyd]  — ultra-fast    ← manual local build
C engine [ctypes DLL]  — fast                       ← DLL fallback
Pure-Python fallback (pip install wavcore to compile C engine)
```

Always check this first when debugging performance. You want to see `C engine`.

---

## Low-Level Frame API

For advanced use cases — streaming, custom formats, per-frame processing.

### `wavcore.batch_encode(audio, spf)`

```python
import wavcore, numpy as np

audio = np.random.randn(10 * 960).astype(np.float32)  # 10 frames
spf   = 960                                            # samples per frame

hex_list = wavcore.batch_encode(audio, spf)

print(len(hex_list))        # → 10
print(len(hex_list[0]))     # → 7680  (960 × 8 hex chars)
print(type(hex_list[0]))    # → <class 'str'>
```

### `wavcore.batch_decode(hex_list, spf)`

```python
reconstructed = wavcore.batch_decode(hex_list, spf)

print(reconstructed.shape)  # → (9600,)
print(reconstructed.dtype)  # → float32
print(np.array_equal(audio, reconstructed))  # → True
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
print(f"CRC-32: {crc:08X}")   # → e.g. BC5C582D
```

---

## Working with Stats Dicts

```python
import wavcore

rec   = wavcore.record("audio.vtxt", "orig.wav", duration=5)
conv  = wavcore.decode("audio.vtxt", "recon.wav", play=False)

# Check recording quality
if rec["peak"] < 0.01:
    print("WARNING: Very quiet recording. Check microphone.")
elif rec["peak"] > 0.95:
    print("WARNING: Clipping detected. Move mic further away.")
else:
    print(f"Good signal: peak={rec['peak']:.3f}, rms={rec['rms']:.3f}")

# Check decode quality
if conv["integrity_pct"] == 100.0:
    print("Perfect reconstruction.")
elif conv["integrity_pct"] >= 95.0:
    print(f"Good: {conv['integrity_pct']:.1f}% frames valid.")
else:
    print(f"Degraded: {conv['bad_frames']} frames corrupted or missing.")

# Performance check
print(f"Encode speed: {rec['encode_ms']:.1f} ms for {rec['frames']} frames")
print(f"Decode speed: {conv['total_ms']:.1f} ms for {conv['ok_frames']} frames")
```

---

## Integration Examples

### 1. Voice Messaging (like WhatsApp)

```python
import wavcore, requests

# === SENDER ===
# Record and encode
stats = wavcore.record("message.vtxt", "send_orig.wav", duration=5)
# Read the text file and send via HTTP
with open("message.vtxt", "r") as f:
    text_payload = f.read()

response = requests.post(
    "https://api.myapp.com/voice/send",
    data=text_payload.encode("utf-8"),
    headers={"Content-Type": "text/plain; charset=utf-8"},
)
print(f"Sent {stats['frames']} frames, {stats['vtxt_size']:,} bytes")

# === RECEIVER ===
# Download and decode
response = requests.get("https://api.myapp.com/voice/recv/msg123")
with open("received.vtxt", "w", encoding="utf-8") as f:
    f.write(response.text)

result = wavcore.decode("received.vtxt", "playback.wav", play=True)
print(f"Played {result['duration_s']:.1f}s  |  {result['integrity_pct']:.1f}% intact")
```

### 2. Continuous Streaming (frame by frame)

```python
import wavcore, numpy as np, sounddevice as sd

SAMPLE_RATE = 48_000
FRAME_MS    = 20
SPF         = SAMPLE_RATE * FRAME_MS // 1000   # 960

def on_frame(frame_id: int, hex_str: str, crc: str):
    """Called for each 20ms frame — send over network here."""
    print(f"Frame {frame_id}: {len(hex_str)} hex chars, CRC={crc}")

# Stream and encode frame by frame
stream_buffer = []
def audio_callback(indata, frames, time_info, status):
    audio_frame = np.ascontiguousarray(indata.flatten(), dtype=np.float32)
    hex_str     = wavcore.batch_encode(audio_frame, SPF)[0]
    payload     = audio_frame.tobytes()
    crc         = wavcore.compute_frame_crc(1, len(stream_buffer),
                      time_info.inputBufferAdcTime * 1000,
                      SAMPLE_RATE, 1, 32, payload)
    stream_buffer.append(hex_str)
    on_frame(len(stream_buffer)-1, hex_str, f"{crc:08X}")

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                    dtype="float32", blocksize=SPF,
                    callback=audio_callback):
    input("Recording... press ENTER to stop")
```

### 3. Database Storage

```python
import wavcore, sqlite3

# Store voice as text in SQLite
conn = wavcore.record.__module__  # just showing import
conn = sqlite3.connect("voices.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS voice_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        vtxt_data TEXT,
        created_at REAL
    )
""")

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
row = conn.execute("SELECT vtxt_data FROM voice_messages ORDER BY id DESC LIMIT 1").fetchone()
with open("playback.vtxt", "w") as f:
    f.write(row[0])
wavcore.decode("playback.vtxt", "playback.wav", play=True)
```

### 4. Server-Side — No Playback

```python
import wavcore

# Process without playing audio (server/cloud environment)
stats = wavcore.decode(
    vtxt_path  = "/uploads/voice_001.vtxt",
    output_wav = "/processed/voice_001.wav",
    play       = False,   # ← no sounddevice playback
)
print(f"Processed: integrity={stats['integrity_pct']:.1f}%  "
      f"time={stats['total_ms']:.1f}ms")
```

---

## Running app.py

`app.py` is the all-in-one demo entry point:

```bash
python app.py
```

It will:
1. Show experiment info and wait for you to press ENTER
2. Count down 3 seconds
3. Record 10 seconds of your voice
4. Encode to `voice_data.vtxt` using the C engine
5. Decode `voice_data.vtxt` back to audio
6. Play the reconstructed audio
7. Show a full pipeline report

Output files created:
- `original_reference.wav` — raw microphone capture
- `voice_data.vtxt` — text-encoded audio frames
- `reconstructed.wav` — rebuilt from vtxt

---

## Troubleshooting

### "Pure-Python fallback" instead of C engine

```python
print(wavcore.engine_info())
# → Pure-Python fallback (pip install wavcore to compile C engine)
```

**Fix:** Re-run the install which triggers C compilation:
```bash
pip install -e .
```
Or rebuild manually:
```python
from cffi import FFI
import os
# See docs/ARCHITECTURE.md — Build System section
```

### No audio recorded (peak < 0.001)

- Check OS microphone permissions (Settings → Privacy → Microphone)
- Check that the correct input device is set as default in OS audio settings
- Try: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### `sounddevice` not found

```bash
pip install sounddevice
```

On Linux, also install PortAudio:
```bash
sudo apt install libportaudio2
```

### CRC verification failures

If `bad_frames > 0` after a local record+decode cycle, this indicates file corruption
(e.g. the vtxt was partially overwritten). Re-record to get a clean file.

For network transmission failures, add HTTP retry logic and re-request the specific frames.

---

## Configuration Reference

| Parameter | Default | Range | Notes |
|---|---|---|---|
| `duration` | `10` | 1–3600 s | Recording length |
| `sample_rate` | `48000` | 8000–192000 | Higher = better quality, larger file |
| `frame_ms` | `20` | 10–100 | Smaller = lower latency, more CRC overhead |
| `play` | `True` | True/False | Set False on servers without audio |

### Sample Rate vs File Size

| Sample Rate | Frame Size (20ms) | File Size (10s) | Quality |
|---|---|---|---|
| 8,000 Hz | 160 samples = 1,280 chars | ~660 KB | Phone call |
| 16,000 Hz | 320 samples = 2,560 chars | ~1.3 MB | VoIP |
| 44,100 Hz | 882 samples = 7,056 chars | ~3.6 MB | CD quality |
| **48,000 Hz** | **960 samples = 7,680 chars** | **~3.9 MB** | **Default** |
| 96,000 Hz | 1,920 samples = 15,360 chars | ~7.8 MB | Professional |
