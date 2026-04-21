# WavCore

**Ultra-fast lossless voice codec with a C engine.**

Record → serialize to text → transmit → reconstruct. Bit-perfect.  
Designed for real-time communication (VoIP, messaging apps, IoT, research).

---

## Features

- **Lossless** — IEEE-754 hex encoding, zero floating-point rounding
- **CRC-32 per frame** — every 20 ms frame integrity-verified
- **C engine** — MSVC/GCC compiled via cffi — 9 µs/frame decode
- **VTXT format** — human-readable, version-controlled, diff-able audio
- **Gap handling** — missing frames replaced with silence automatically
- **Pure-Python fallback** — works without a C compiler (5× slower)

---

## Installation

```bash
pip install wavcore
```

All dependencies (`numpy`, `sounddevice`, `cffi`) install automatically.  
The C engine compiles automatically during install.

---

## Quick Start

```python
import wavcore

# 1 — Record 10 s of microphone input
wavcore.record("audio.vtxt", "original.wav", duration=10)

# 2 — Reconstruct and play back
wavcore.decode("audio.vtxt", "reconstructed.wav", play=True)

# 3 — Check engine
print(wavcore.engine_info())
# → C engine [cffi / MSVC 64-bit]  — ultra-fast
```

---

## API Reference

### High-level

| Function | Description |
|---|---|
| `wavcore.record(vtxt, wav, duration, sample_rate, frame_ms)` | Record mic → `.vtxt` + original WAV |
| `wavcore.decode(vtxt, wav, play)` | `.vtxt` → reconstructed WAV (+ optional playback) |
| `wavcore.engine_info()` | Returns active engine name and speed class |

### Low-level (frame-level)

| Function | Description |
|---|---|
| `wavcore.batch_encode(audio, spf)` | `float32[]` → list of hex strings |
| `wavcore.batch_decode(hex_list, spf)` | list of hex strings → `float32[]` |
| `wavcore.compute_frame_crc(ver, fid, ts, sr, ch, bd, payload)` | CRC-32 identical to zlib |

---

## VTXT Format

WavCore uses a human-readable `.vtxt` text format for audio serialization:

```
[FILE_HEADER]
SAMPLE_RATE=48000
TOTAL_FRAMES=500
...
[/FILE_HEADER]

[FRAME]
FRAME_ID=0
TIMESTAMP_MS=1745123456789.000000
ORIG_CRC32=BC5C582D
SAMPLES_HEX=3C8B4396...  ← raw IEEE-754 float32 bytes
[/FRAME]
```

- Store in Git, send over HTTP, inspect in Notepad
- Fully round-trips back to bit-identical binary audio

---

## Performance (Ryzen 3 7000 series, Python 3.12)

| Operation | Frames | Time | Per-frame |
|---|---|---|---|
| Encode (mic → vtxt) | 500 | 7.5 ms | 15 µs |
| Decode (vtxt → wav) | 500 | 4.6 ms | 9 µs |
| CRC-32 verify | 500 | 7.4 ms | 15 µs |
| **Real-time budget** | 1 | 20,000 µs | — |

The C engine is **~1,300× faster** than the real-time frame budget.

---

## Integration Examples

### WhatsApp / VoIP — send voice as text

```python
import wavcore, requests

# Sender
stats  = wavcore.record("msg.vtxt", "orig.wav", duration=5)
text   = open("msg.vtxt").read()
requests.post("https://yourapi.com/voice", data=text)

# Receiver
open("recv.vtxt", "w").write(response.text)
wavcore.decode("recv.vtxt", "playback.wav", play=True)
```

### IoT / Embedded — store voice compactly as text

```python
import wavcore
wavcore.record("/sd/voice_memo.vtxt", "/sd/orig.wav", duration=30)
```

---

## License

MIT © WavCore Project
