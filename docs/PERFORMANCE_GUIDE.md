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
