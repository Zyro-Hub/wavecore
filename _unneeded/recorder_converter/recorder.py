"""
recorder_converter.recorder  (C-accelerated)
=============================================
Records microphone input and writes DIRECTLY to .vtxt using
the C engine (cffi/MSVC 64-bit) for hex encoding + CRC.

Pipeline:
  Mic (48 kHz, float32)
    -> 20ms frames
    -> C batch_encode()  [1326x faster than real-time]
    -> C compute_frame_crc() per frame
    -> voice_data.vtxt
    -> original_reference.wav  (16-bit PCM WAV, ground truth)

Public API
──────────
  record_to_vtxt(vtxt_path, orig_wav_path,
                 duration_sec=10, sample_rate=48000, frame_ms=20)
  -> dict  (stats)
"""

import os
import sys
import struct
import time
import wave
import datetime
import numpy as np
import sounddevice as sd

# ── Import C codec engine ─────────────────────────────────────
_HERE        = os.path.dirname(os.path.abspath(__file__))
_CODEC_DIR   = os.path.join(_HERE, "vdat_txt_converter")
sys.path.insert(0, _CODEC_DIR)

from codec import (
    batch_encode,
    compute_frame_crc,
    engine_info as _codec_engine_info,
)

# ── Frame header layout (same as the rest of the project) ────
_FRAME_HDR_FMT  = ">BIdIBBI"
_FRAME_VER      = 1
_CODEC_VER      = 1
_FILE_VER       = 1


def record_to_vtxt(
    vtxt_path:    str,
    orig_wav_path: str,
    duration_sec: int  = 10,
    sample_rate:  int  = 48_000,
    frame_ms:     int  = 20,
) -> dict:
    """
    Record `duration_sec` seconds of microphone audio, encode to .vtxt
    using the C engine for maximum speed, and save original WAV.

    Returns stats dict:
      frames, duration_ms, sample_rate, channels, peak, rms,
      vtxt_path, orig_wav_path, created_unix, vtxt_size, encode_ms
    """
    channels          = 1
    bit_depth         = 32
    samples_per_frame = int(sample_rate * frame_ms / 1000)   # 960
    total_samples     = sample_rate * duration_sec            # 480000

    print("=" * 64)
    print("  RECORDER  ->  .vtxt  [C engine]")
    print(f"  Engine  : {_codec_engine_info()}")
    print("=" * 64)
    print(f"  Sample rate   : {sample_rate:,} Hz")
    print(f"  Duration      : {duration_sec} s")
    print(f"  Frame size    : {frame_ms} ms  ({samples_per_frame} samples)")
    print(f"  Output vtxt   : {vtxt_path}")
    print("=" * 64)
    print()

    # ── Countdown ─────────────────────────────────────────────
    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  [REC] RECORDING ... speak now!               ")
    print()

    # ── Capture ───────────────────────────────────────────────
    t_start = time.time()
    raw = sd.rec(
        total_samples,
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
        blocking=True,
    )
    sd.wait()
    t_end        = time.time()
    created_unix = int(t_start)
    rec_start_ms = t_start * 1000.0

    print(f"  [OK] Captured {t_end - t_start:.2f}s of audio.")

    # ── Save original reference WAV ───────────────────────────
    audio = raw.flatten()
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(orig_wav_path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    print(f"  [OK] Original WAV : {orig_wav_path}")

    # Stats
    peak = float(np.max(np.abs(audio)))
    rms  = float(np.sqrt(np.mean(audio ** 2)))
    print(f"       Peak={peak:.6f}   RMS={rms:.6f}")
    if peak < 0.001:
        print("  [WARN] Very quiet — check microphone!")
    print()

    # ── Pad audio to exact multiple of samples_per_frame ─────
    remainder = len(audio) % samples_per_frame
    if remainder:
        audio = np.append(audio, np.zeros(samples_per_frame - remainder,
                                          dtype=np.float32))
    n_frames = len(audio) // samples_per_frame

    # ── C batch hex-encode ALL frames in one call ─────────────
    print("  Encoding frames (C batch_encode) ...", end=" ", flush=True)
    t0       = time.perf_counter()
    hex_list = batch_encode(audio.astype(np.float32), samples_per_frame)
    t_encode = (time.perf_counter() - t0) * 1000
    print(f"{t_encode:.1f} ms  ({t_encode/n_frames*1000:.1f} us/frame)")

    # ── Compute CRC per frame (C engine) ──────────────────────
    print("  Computing CRC-32 (C engine) ...", end=" ", flush=True)
    t0        = time.perf_counter()
    frame_crcs = []
    payloads   = []
    for i in range(n_frames):
        chunk   = audio[i * samples_per_frame: (i+1) * samples_per_frame]
        payload = chunk.astype(np.float32).tobytes()
        ts_ms   = rec_start_ms + i * frame_ms
        crc     = compute_frame_crc(
            _FRAME_VER, i, ts_ms, sample_rate, channels, bit_depth, payload
        )
        frame_crcs.append(f"{crc:08X}")
        payloads.append((i, ts_ms, len(payload)))
    t_crc = (time.perf_counter() - t0) * 1000
    print(f"{t_crc:.1f} ms")

    # ── Write .vtxt ──────────────────────────────────────────
    print("  Writing .vtxt ...", end=" ", flush=True)
    now_utc     = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    duration_ms = duration_sec * 1000.0

    t0 = time.perf_counter()
    with open(vtxt_path, "w", encoding="utf-8") as f:
        # File comment block
        f.write("# ================================================================\n")
        f.write("# VDAT TEXT CODEC  v1  (C-accelerated recorder)\n")
        f.write("# Encoder : recorder_converter.recorder  +  codec_core (C engine)\n")
        f.write(f"# Recorded: {now_utc}\n")
        f.write(f"# Engine  : {_codec_engine_info()}\n")
        f.write("#\n")
        f.write("# SAMPLES_HEX = raw IEEE-754 float32 bytes, uppercase hex\n")
        f.write("# Lossless: no floating-point rounding ever occurs\n")
        f.write("# ================================================================\n\n")

        # [FILE_HEADER]
        f.write("[FILE_HEADER]\n")
        f.write(f"CODEC_VERSION={_CODEC_VER}\n")
        f.write(f"FILE_VERSION={_FILE_VER}\n")
        f.write(f"TOTAL_FRAMES={n_frames}\n")
        f.write(f"SAMPLE_RATE={sample_rate}\n")
        f.write(f"CHANNELS={channels}\n")
        f.write(f"BIT_DEPTH={bit_depth}\n")
        f.write(f"DURATION_MS={duration_ms:.6f}\n")
        f.write(f"CREATED_UNIX={created_unix}\n")
        f.write(f"CREATED_UTC={now_utc}\n")
        f.write("[/FILE_HEADER]\n\n")

        # [FRAME] blocks
        for i, (fid, ts_ms, plen) in enumerate(payloads):
            f.write("[FRAME]\n")
            f.write(f"FRAME_ID={fid}\n")
            f.write(f"FRAME_VERSION={_FRAME_VER}\n")
            f.write(f"TIMESTAMP_MS={ts_ms:.6f}\n")
            f.write(f"SAMPLE_RATE={sample_rate}\n")
            f.write(f"CHANNELS={channels}\n")
            f.write(f"BIT_DEPTH={bit_depth}\n")
            f.write(f"PAYLOAD_LEN={plen}\n")
            f.write(f"SAMPLES_COUNT={plen // 4}\n")
            f.write(f"ORIG_CRC32={frame_crcs[i]}\n")
            f.write(f"SAMPLES_HEX={hex_list[i]}\n")
            f.write("[/FRAME]\n\n")

    t_write  = (time.perf_counter() - t0) * 1000
    vtxt_size = os.path.getsize(vtxt_path)
    total_ms  = t_encode + t_crc + t_write

    print(f"{t_write:.1f} ms")
    print()
    print(f"  [OK] Frames   : {n_frames}")
    print(f"  [OK] vtxt     : {vtxt_size:,} bytes  ({vtxt_size/1024:.1f} KB)")
    print(f"  [OK] Encode   : {t_encode:.1f} ms  |  CRC: {t_crc:.1f} ms  "
          f"|  Write: {t_write:.1f} ms")
    print(f"  [OK] Total    : {total_ms:.1f} ms  "
          f"({total_ms/n_frames*1000:.1f} us/frame)")
    print()

    return {
        "frames":        n_frames,
        "duration_ms":   duration_ms,
        "sample_rate":   sample_rate,
        "channels":      channels,
        "peak":          peak,
        "rms":           rms,
        "vtxt_path":     vtxt_path,
        "orig_wav_path": orig_wav_path,
        "created_unix":  created_unix,
        "vtxt_size":     vtxt_size,
        "encode_ms":     total_ms,
    }
