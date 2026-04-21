"""
wavcore.converter — .vtxt → WAV reconstruction
===============================================
Parses a .vtxt file, validates every frame's CRC-32 using the
C engine, reconstructs the float32 audio, saves as WAV, and
optionally plays back through the system's audio device.

Internal use — call via  wavcore.decode()  for the public API.
"""

import os
import sys
import time
import wave
import numpy as np

try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False

from wavcore._codec.codec import batch_decode, compute_frame_crc, engine_info

# ── Required frame keys ───────────────────────────────────────
_REQUIRED_KEYS = {
    "FRAME_ID", "FRAME_VERSION", "TIMESTAMP_MS",
    "SAMPLE_RATE", "CHANNELS", "BIT_DEPTH",
    "PAYLOAD_LEN", "SAMPLES_COUNT", "ORIG_CRC32", "SAMPLES_HEX",
}


# ── Parser ────────────────────────────────────────────────────

def _parse_vtxt(path: str):
    """
    Parse a .vtxt file into (file_header dict, [frame dict, ...]).
    Raises ValueError on malformed input.
    """
    file_hdr = {}
    frames   = []
    in_fh = in_fr = False
    cur_fr = {}

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line == "[FILE_HEADER]":   in_fh = True;  continue
            if line == "[/FILE_HEADER]":  in_fh = False; continue
            if line == "[FRAME]":
                if in_fr:
                    raise ValueError(f"Line {lineno}: nested [FRAME] block")
                in_fr = True; cur_fr = {}; continue
            if line == "[/FRAME]":
                if not in_fr:
                    raise ValueError(f"Line {lineno}: [/FRAME] without [FRAME]")
                missing = _REQUIRED_KEYS - set(cur_fr)
                if missing:
                    fid = cur_fr.get("FRAME_ID", "?")
                    raise ValueError(f"Frame {fid} missing keys: {missing}")
                frames.append(cur_fr)
                in_fr = False; continue
            if "=" not in line:
                raise ValueError(f"Line {lineno}: unexpected content: {line!r}")
            k, _, v = line.partition("=")
            k = k.strip(); v = v.strip()
            if in_fh:   file_hdr[k] = v
            elif in_fr: cur_fr[k]  = v

    if in_fr:
        raise ValueError("File ended inside an unclosed [FRAME] block.")
    if not file_hdr:
        raise ValueError("No [FILE_HEADER] block found in file.")
    return file_hdr, frames


def _save_wav(audio: np.ndarray, sample_rate: int, channels: int, path: str):
    """Write a float32 array as a 16-bit PCM WAV file."""
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())


# ── Public function ───────────────────────────────────────────

def vtxt_to_wav(
    vtxt_path:  str,
    output_wav: str,
    play_audio: bool = True,
) -> dict:
    """
    Reconstruct audio from a .vtxt file.

    Parameters
    ----------
    vtxt_path  : path to the .vtxt file
    output_wav : path for the output WAV file
    play_audio : if True, play audio after saving (requires sounddevice)

    Returns
    -------
    dict: ok_frames, bad_frames, integrity_pct, duration_s,
          peak, rms, output_wav, sample_rate, total_ms
    """
    print("=" * 64)
    print("  wavcore.decode  [C engine]")
    print(f"  {engine_info()}")
    print("=" * 64)

    if not os.path.exists(vtxt_path):
        raise FileNotFoundError(f"wavcore.decode: vtxt not found: {vtxt_path}")

    vtxt_size = os.path.getsize(vtxt_path)
    print(f"  Input  : {vtxt_path}")
    print(f"  Size   : {vtxt_size:,} bytes  ({vtxt_size / 1024:.1f} KB)")
    print()

    t_total = time.perf_counter()

    # ── Parse ─────────────────────────────────────────────────
    print("  Parsing .vtxt ...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        file_hdr, frames = _parse_vtxt(vtxt_path)
    except ValueError as exc:
        raise ValueError(f"wavcore.decode: {exc}") from exc
    t_parse = (time.perf_counter() - t0) * 1000

    sample_rate = int(file_hdr["SAMPLE_RATE"])
    channels    = int(file_hdr["CHANNELS"])
    n           = len(frames)

    # Determine spf from the first frame (not hardcoded) — bug-fix
    spf = int(frames[0]["SAMPLES_COUNT"]) if n > 0 else int(sample_rate * 20 / 1000)
    print(f"OK  ({n} frames, {spf} samples/frame, {sample_rate:,} Hz)  "
          f"[{t_parse:.1f} ms]")

    # ── C batch decode all frames in ONE call ─────────────────
    print("  C batch_decode ...", end=" ", flush=True)
    t0       = time.perf_counter()
    hex_list = [fr["SAMPLES_HEX"] for fr in frames]
    try:
        audio_flat = batch_decode(hex_list, spf)
    except ValueError as exc:
        raise ValueError(f"wavcore.decode: hex decode failed — {exc}") from exc
    t_decode = (time.perf_counter() - t0) * 1000
    print(f"OK  [{t_decode:.1f} ms  |  {t_decode/n*1000:.1f} µs/frame]")

    # ── CRC verify + gap detection ────────────────────────────
    print("  CRC verify ...", end=" ", flush=True)
    t0 = time.perf_counter()

    ok_frames  = 0
    bad_frames = 0
    bad_ids    = []
    prev_id    = -1
    segments   = []   # list of float32 arrays in order
    cursor     = 0

    for i, meta in enumerate(frames):
        fid      = int(meta["FRAME_ID"])
        ver      = int(meta["FRAME_VERSION"])
        ts_ms    = float(meta["TIMESTAMP_MS"])
        fsr      = int(meta["SAMPLE_RATE"])
        fch      = int(meta["CHANNELS"])
        fbd      = int(meta["BIT_DEPTH"])
        n_samp   = int(meta["SAMPLES_COUNT"])
        orig_crc = int(meta["ORIG_CRC32"], 16)

        # Gap detection — insert silence for missing frame IDs
        if prev_id >= 0 and fid != prev_id + 1:
            gap = fid - (prev_id + 1)
            segments.append(np.zeros(gap * spf, dtype=np.float32))
            bad_frames += gap
            bad_ids.extend(range(prev_id + 1, fid))
        prev_id = fid

        # Slice this frame's samples from decoded flat array
        frame_samples = audio_flat[cursor: cursor + n_samp]
        cursor       += n_samp

        # Verify CRC using C engine
        payload  = frame_samples.astype(np.float32).tobytes()
        computed = compute_frame_crc(ver, fid, ts_ms, fsr, fch, fbd, payload)

        if computed != orig_crc:
            bad_ids.append(fid)
            bad_frames += 1
        else:
            ok_frames += 1

        segments.append(frame_samples)

    t_crc = (time.perf_counter() - t0) * 1000
    print(f"OK  [{t_crc:.1f} ms]  {ok_frames}/{n} valid")

    # ── Assemble audio ─────────────────────────────────────────
    if not segments:
        raise ValueError("wavcore.decode: no audio data decoded.")
    audio      = np.concatenate(segments)
    total_fr   = ok_frames + bad_frames
    integrity  = (ok_frames / total_fr * 100) if total_fr > 0 else 0.0
    duration_s = len(audio) / sample_rate
    peak       = float(np.max(np.abs(audio)))
    rms        = float(np.sqrt(np.mean(audio ** 2)))

    # ── Report ─────────────────────────────────────────────────
    print()
    print("  INTEGRITY REPORT")
    print(f"  |- Frames total   : {total_fr}")
    print(f"  |- CRC valid      : {ok_frames}")
    print(f"  |- Bad / gaps     : {bad_frames}")
    print(f"  |- Integrity      : {integrity:.2f}%")
    print(f"  |- Duration       : {duration_s:.3f} s")
    print(f"  |- Peak amplitude : {peak:.6f}")
    print(f"  |- RMS level      : {rms:.6f}")
    if bad_ids:
        shown = [str(x) for x in bad_ids[:10]]
        print(f"  |- Bad frame IDs  : [{', '.join(shown)}"
              f"{'...' if len(bad_ids) > 10 else ''}]")

    # ── Save WAV ──────────────────────────────────────────────
    print()
    print(f"  Saving WAV ...", end=" ", flush=True)
    t0 = time.perf_counter()
    _save_wav(audio, sample_rate, channels, output_wav)
    t_wav    = (time.perf_counter() - t0) * 1000
    wav_size = os.path.getsize(output_wav)
    print(f"OK  [{t_wav:.1f} ms  |  {wav_size:,} bytes]")

    total_ms = (time.perf_counter() - t_total) * 1000
    print(f"  Total pipeline : {total_ms:.1f} ms  "
          f"({total_ms / n * 1000:.1f} µs/frame)")
    print()

    # ── Playback ──────────────────────────────────────────────
    if play_audio:
        if not _SD_AVAILABLE:
            print("  [WARN] sounddevice not available — skipping playback.")
        else:
            print("=" * 64)
            print(f"  [PLAY] {duration_s:.1f} s — {output_wav}")
            print("=" * 64)
            time.sleep(0.2)
            playback = audio.reshape(-1, channels) if channels > 1 else audio
            sd.play(playback, samplerate=sample_rate)
            sd.wait()
            print("  [OK] Playback complete.")
            print()

    return {
        "ok_frames":     ok_frames,
        "bad_frames":    bad_frames,
        "integrity_pct": integrity,
        "duration_s":    duration_s,
        "peak":          peak,
        "rms":           rms,
        "output_wav":    output_wav,
        "sample_rate":   sample_rate,
        "total_ms":      total_ms,
    }
