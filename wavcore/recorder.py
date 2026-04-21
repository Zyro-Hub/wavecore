"""
wavcore.recorder — Microphone capture → .vtxt
=============================================
Records microphone audio and encodes directly to the .vtxt
text-frame format using the C engine for maximum speed.

Internal use — call via  wavcore.record()  for the public API.
"""

import os
import sys
import time
import wave
import struct
import datetime
import numpy as np

try:
    import sounddevice as sd
except ImportError as e:
    raise ImportError("wavcore requires 'sounddevice'.  Run: pip install sounddevice") from e

from wavcore._codec.codec import batch_encode, compute_frame_crc, engine_info

# ── Constants ─────────────────────────────────────────────────
_FRAME_VER = 1
_CODEC_VER  = 1
_FILE_VER   = 1
_FRAME_HDR  = ">BIdIBBI"   # ver, frame_id, ts_ms, sr, ch, bd, plen


def record_to_vtxt(
    vtxt_path:    str,
    orig_wav_path: str,
    duration_sec: int   = 10,
    sample_rate:  int   = 48_000,
    frame_ms:     int   = 20,
) -> dict:
    """
    Record from the microphone and write audio directly to a .vtxt file.

    Parameters
    ----------
    vtxt_path     : output .vtxt path
    orig_wav_path : output original WAV path (ground-truth reference)
    duration_sec  : recording length in seconds
    sample_rate   : capture rate in Hz (default 48000)
    frame_ms      : frame size in milliseconds (default 20)

    Returns
    -------
    dict: frames, duration_ms, sample_rate, channels, peak, rms,
          vtxt_path, orig_wav_path, created_unix, vtxt_size, encode_ms
    """
    channels          = 1
    bit_depth         = 32
    spf               = int(sample_rate * frame_ms / 1000)   # samples per frame
    total_samples     = sample_rate * duration_sec

    print("=" * 64)
    print("  wavcore.record  [C engine]")
    print(f"  {engine_info()}")
    print("=" * 64)
    print(f"  Sample rate  : {sample_rate:,} Hz")
    print(f"  Duration     : {duration_sec} s")
    print(f"  Frame size   : {frame_ms} ms  ({spf} samples/frame)")
    print(f"  Output       : {vtxt_path}")
    print()

    # ── Countdown ─────────────────────────────────────────────
    for i in range(3, 0, -1):
        print(f"  Starting in {i}...", end="\r", flush=True)
        time.sleep(1)
    print("  [REC] RECORDING — speak now!                     ")
    print()

    # ── Capture ───────────────────────────────────────────────
    t_start = time.time()
    try:
        raw = sd.rec(
            total_samples,
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            blocking=True,
        )
        sd.wait()
    except Exception as exc:
        raise RuntimeError(f"wavcore.recorder: sounddevice error — {exc}") from exc

    t_end        = time.time()
    created_unix = int(t_start)
    rec_start_ms = t_start * 1000.0
    actual_secs  = t_end - t_start
    print(f"  [OK] Captured {actual_secs:.2f} s of audio.")

    # ── Validate signal ───────────────────────────────────────
    audio = np.ascontiguousarray(raw.flatten(), dtype=np.float32)
    peak  = float(np.max(np.abs(audio)))
    rms   = float(np.sqrt(np.mean(audio ** 2)))
    print(f"       Peak={peak:.6f}   RMS={rms:.6f}", end="")
    if peak < 0.001:
        print("  [WARN] Very quiet — check your microphone!")
    else:
        print()

    # ── Save original reference WAV ───────────────────────────
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(orig_wav_path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    print(f"  [OK] Original WAV : {orig_wav_path}")
    print()

    # ── Pad audio to exact multiple of spf ────────────────────
    remainder = len(audio) % spf
    if remainder:
        pad   = spf - remainder
        audio = np.append(audio, np.zeros(pad, dtype=np.float32))
    n_frames = len(audio) // spf

    # ── C batch hex-encode all frames in ONE call ─────────────
    t0       = time.perf_counter()
    hex_list = batch_encode(audio, spf)
    t_enc    = (time.perf_counter() - t0) * 1000
    print(f"  Hex encode   : {t_enc:.1f} ms  ({t_enc/n_frames*1000:.1f} µs/frame)")

    # ── Compute CRC per frame (C engine) ─────────────────────
    t0     = time.perf_counter()
    crcs   = []
    metas  = []   # (frame_id, ts_ms, payload_len)
    for i in range(n_frames):
        chunk   = audio[i * spf: (i + 1) * spf]
        payload = chunk.tobytes()          # float32 bytes
        ts_ms   = rec_start_ms + i * frame_ms
        crc     = compute_frame_crc(
            _FRAME_VER, i, ts_ms, sample_rate, channels, bit_depth, payload
        )
        crcs.append(f"{crc:08X}")
        metas.append((i, ts_ms, len(payload)))
    t_crc = (time.perf_counter() - t0) * 1000
    print(f"  CRC-32       : {t_crc:.1f} ms  ({t_crc/n_frames*1000:.1f} µs/frame)")

    # ── Write .vtxt ──────────────────────────────────────────
    now_utc     = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    duration_ms = duration_sec * 1000.0

    t0 = time.perf_counter()
    with open(vtxt_path, "w", encoding="utf-8") as f:
        f.write("# ================================================================\n")
        f.write("# wavcore VTXT  v1.0\n")
        f.write(f"# Recorded : {now_utc}\n")
        f.write(f"# Engine   : {engine_info()}\n")
        f.write("# SAMPLES_HEX = raw IEEE-754 float32 bytes, uppercase hex\n")
        f.write("# Zero precision loss — no floating-point rounding\n")
        f.write("# ================================================================\n\n")

        f.write("[FILE_HEADER]\n")
        f.write(f"CODEC_VERSION={_CODEC_VER}\n")
        f.write(f"FILE_VERSION={_FILE_VER}\n")
        f.write(f"TOTAL_FRAMES={n_frames}\n")
        f.write(f"SAMPLE_RATE={sample_rate}\n")
        f.write(f"CHANNELS={channels}\n")
        f.write(f"BIT_DEPTH={bit_depth}\n")
        f.write(f"FRAME_MS={frame_ms}\n")
        f.write(f"DURATION_MS={duration_ms:.6f}\n")
        f.write(f"CREATED_UNIX={created_unix}\n")
        f.write(f"CREATED_UTC={now_utc}\n")
        f.write("[/FILE_HEADER]\n\n")

        for i, (fid, ts_ms, plen) in enumerate(metas):
            f.write("[FRAME]\n")
            f.write(f"FRAME_ID={fid}\n")
            f.write(f"FRAME_VERSION={_FRAME_VER}\n")
            f.write(f"TIMESTAMP_MS={ts_ms:.6f}\n")
            f.write(f"SAMPLE_RATE={sample_rate}\n")
            f.write(f"CHANNELS={channels}\n")
            f.write(f"BIT_DEPTH={bit_depth}\n")
            f.write(f"PAYLOAD_LEN={plen}\n")
            f.write(f"SAMPLES_COUNT={plen // 4}\n")
            f.write(f"ORIG_CRC32={crcs[i]}\n")
            f.write(f"SAMPLES_HEX={hex_list[i]}\n")
            f.write("[/FRAME]\n\n")

    t_write   = (time.perf_counter() - t0) * 1000
    vtxt_size = os.path.getsize(vtxt_path)
    encode_ms = t_enc + t_crc + t_write

    print(f"  Write vtxt   : {t_write:.1f} ms")
    print()
    print(f"  [DONE] {n_frames} frames  |  {vtxt_size:,} bytes  "
          f"|  {encode_ms:.1f} ms total")
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
        "encode_ms":     encode_ms,
    }
