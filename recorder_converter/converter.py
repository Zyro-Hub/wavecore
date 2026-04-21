"""
recorder_converter.converter  (C-accelerated)
==============================================
Reads a .vtxt file and reconstructs audio using the C engine
(cffi/MSVC 64-bit) for hex decoding + CRC verification.

Pipeline:
  voice_data.vtxt
    -> parse [FRAME] blocks  (Python, I/O bound)
    -> C batch_decode()      [1326x faster than real-time]
    -> C compute_frame_crc() per frame  (verify integrity)
    -> float32 audio array
    -> 16-bit PCM WAV
    -> sounddevice playback

Public API
──────────
  vtxt_to_wav(vtxt_path, output_wav, play_audio=True)
  -> dict  (stats)
"""

import os
import sys
import struct
import time
import wave
import numpy as np
import sounddevice as sd

# ── Import C codec engine ─────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_CODEC_DIR = os.path.join(_HERE, "vdat_txt_converter")
sys.path.insert(0, _CODEC_DIR)

from codec import (
    batch_decode,
    compute_frame_crc,
    engine_info as _codec_engine_info,
)

# ── Frame layout ─────────────────────────────────────────────
_FRAME_HDR_FMT = ">BIdIBBI"


# ── .vtxt fast parser ────────────────────────────────────────

def _parse_vtxt(path: str):
    """
    Fast line-by-line parser.
    Returns (file_hdr dict, [frame dict, ...]).
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
            if line == "[FRAME]":         in_fr = True;  cur_fr = {}; continue
            if line == "[/FRAME]":
                required = {
                    "FRAME_ID", "FRAME_VERSION", "TIMESTAMP_MS",
                    "SAMPLE_RATE", "CHANNELS", "BIT_DEPTH",
                    "PAYLOAD_LEN", "SAMPLES_COUNT", "ORIG_CRC32", "SAMPLES_HEX"
                }
                missing = required - set(cur_fr)
                if missing:
                    raise ValueError(
                        f"Frame {cur_fr.get('FRAME_ID','?')} missing: {missing}"
                    )
                frames.append(cur_fr)
                in_fr = False; continue
            if "=" not in line:
                raise ValueError(f"Line {lineno}: unexpected: {line!r}")
            k, _, v = line.partition("=")
            if in_fh:
                file_hdr[k.strip()] = v.strip()
            elif in_fr:
                cur_fr[k.strip()] = v.strip()

    if not file_hdr:
        raise ValueError("No [FILE_HEADER] found.")
    return file_hdr, frames


def _save_wav(audio: np.ndarray, sample_rate: int, channels: int, path: str):
    """Save float32 array as 16-bit PCM WAV."""
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())


# ── Public function ──────────────────────────────────────────

def vtxt_to_wav(
    vtxt_path:  str,
    output_wav: str,
    play_audio: bool = True,
) -> dict:
    """
    Convert a .vtxt file to a reconstructed WAV using the C engine.

    Steps:
      1.  Parse .vtxt [FILE_HEADER] + [FRAME] blocks
      2.  C batch_decode() — all frames decoded in one call
      3.  C compute_frame_crc() per frame — CRC verification
      4.  Gap detection — insert silence for missing frames
      5.  Save 16-bit PCM WAV
      6.  Playback via sounddevice (optional)

    Returns stats dict.
    """
    print("=" * 64)
    print("  CONVERTER  :  .vtxt  ->  WAV  [C engine]")
    print(f"  Engine  : {_codec_engine_info()}")
    print("=" * 64)

    if not os.path.exists(vtxt_path):
        raise FileNotFoundError(f"vtxt not found: {vtxt_path}")

    vtxt_size = os.path.getsize(vtxt_path)
    print(f"  Input vtxt : {vtxt_path}")
    print(f"  Size       : {vtxt_size:,} bytes  ({vtxt_size/1024:.1f} KB)")
    print()

    t_total = time.perf_counter()

    # ── Parse ────────────────────────────────────────────────
    print("  Parsing .vtxt ...", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        file_hdr, frames = _parse_vtxt(vtxt_path)
    except ValueError as e:
        raise ValueError(f"Parse error: {e}")
    t_parse = (time.perf_counter() - t0) * 1000

    sample_rate = int(file_hdr["SAMPLE_RATE"])
    channels    = int(file_hdr["CHANNELS"])
    bit_depth   = int(file_hdr["BIT_DEPTH"])
    n           = len(frames)
    spf         = int(sample_rate * 20 / 1000)   # samples per frame

    print(f"OK  ({n} frames @ {sample_rate:,} Hz)  [{t_parse:.1f} ms]")

    # ── C batch decode all frames in ONE call ─────────────────
    print("  C batch_decode() ...", end=" ", flush=True)
    t0       = time.perf_counter()
    hex_list = [fr["SAMPLES_HEX"] for fr in frames]
    try:
        audio_flat = batch_decode(hex_list, spf)
    except ValueError as e:
        raise ValueError(f"Decode failed: {e}")
    t_decode = (time.perf_counter() - t0) * 1000
    print(f"OK  [{t_decode:.1f} ms  |  {t_decode/n*1000:.1f} us/frame]")

    # ── C CRC verify every frame ──────────────────────────────
    print("  Verifying CRC-32 (C engine) ...", end=" ", flush=True)
    t0 = time.perf_counter()

    ok_frames    = 0
    bad_frames   = 0
    bad_ids      = []
    prev_id      = -1

    # Build contiguous audio from batch_decode result, inserting
    # silence for any detected gaps in frame IDs
    audio_segments = []
    cursor = 0

    for i, meta in enumerate(frames):
        fid     = int(meta["FRAME_ID"])
        ver     = int(meta["FRAME_VERSION"])
        ts_ms   = float(meta["TIMESTAMP_MS"])
        fsr     = int(meta["SAMPLE_RATE"])
        fch     = int(meta["CHANNELS"])
        fbd     = int(meta["BIT_DEPTH"])
        plen    = int(meta["PAYLOAD_LEN"])
        orig_crc = int(meta["ORIG_CRC32"], 16)

        # Gap detection
        if prev_id >= 0 and fid != prev_id + 1:
            gap = fid - (prev_id + 1)
            silence = np.zeros(gap * spf, dtype=np.float32)
            audio_segments.append(silence)
            bad_frames += gap
        prev_id = fid

        # Frame samples from decoded flat array
        samples = audio_flat[cursor: cursor + spf]
        cursor += spf

        # CRC verify using C engine
        payload  = samples.astype(np.float32).tobytes()
        computed = compute_frame_crc(ver, fid, ts_ms, fsr, fch, fbd, payload)

        if computed != orig_crc:
            bad_ids.append(fid)
            bad_frames += 1
        else:
            ok_frames += 1

        audio_segments.append(samples)

    t_crc = (time.perf_counter() - t0) * 1000
    total_frames = ok_frames + bad_frames
    integrity    = (ok_frames / total_frames * 100) if total_frames > 0 else 0.0
    print(f"OK  [{t_crc:.1f} ms]  {ok_frames}/{n} valid")

    # ── Assemble final audio ──────────────────────────────────
    audio     = np.concatenate(audio_segments) if audio_segments else np.zeros(1, dtype=np.float32)
    duration_s = len(audio) / sample_rate
    peak       = float(np.max(np.abs(audio)))
    rms        = float(np.sqrt(np.mean(audio ** 2)))

    # ── Report ────────────────────────────────────────────────
    print()
    print("  RECONSTRUCTION REPORT")
    print(f"  |- Total frames    : {total_frames}")
    print(f"  |- Valid (CRC OK)  : {ok_frames}")
    print(f"  |- Bad / gaps      : {bad_frames}")
    print(f"  |- Integrity       : {integrity:.2f}%")
    print(f"  |- Duration        : {duration_s:.2f} s")
    print(f"  |- Peak amplitude  : {peak:.6f}")
    print(f"  |- RMS level       : {rms:.6f}")
    if bad_ids:
        shown = bad_ids[:10]
        print(f"  |- Bad frame IDs   : {shown}{'...' if len(bad_ids)>10 else ''}")

    # ── Save WAV ─────────────────────────────────────────────
    print()
    print(f"  Saving WAV -> {output_wav} ...", end=" ", flush=True)
    t0 = time.perf_counter()
    _save_wav(audio, sample_rate, channels, output_wav)
    t_wav = (time.perf_counter() - t0) * 1000
    wav_size = os.path.getsize(output_wav)
    print(f"OK  [{t_wav:.1f} ms  |  {wav_size:,} bytes]")

    total_ms = (time.perf_counter() - t_total) * 1000

    print()
    print(f"  [OK] Total pipeline : {total_ms:.1f} ms  "
          f"({total_ms/n*1000:.1f} us/frame)")
    print()

    # ── Playback ─────────────────────────────────────────────
    if play_audio:
        print("=" * 64)
        print(f"  [PLAY] Reconstructed audio  ({duration_s:.1f} s) ...")
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


def convert_audio(
    audio_path:    str,
    output_wav:    str,
    sample_rate:   int  = 48_000,
    frame_ms:      int  = 20,
    play:          bool = False,
    keep_vtxt:     bool = False,
    vtxt_path:     str  = None,
) -> dict:
    """
    ONE-CALL PIPELINE — Convert any audio file directly to a
    decoded WAV without touching a microphone.

    Pipeline:
      audio_path  →  [file_to_vtxt]  →  temp.vtxt
                  →  [vtxt_to_wav]   →  output_wav

    Parameters
    ----------
    audio_path  : input audio file (WAV built-in; FLAC/OGG/MP3 via soundfile)
    output_wav  : output WAV path
    sample_rate : target Hz (default 48000)
    frame_ms    : frame size in ms (default 20)
    play        : play output after decode (default False)
    keep_vtxt   : keep intermediate .vtxt on disk (default False — deleted)
    vtxt_path   : custom path for intermediate .vtxt (default: <output_wav>.vtxt)

    Returns
    -------
    dict with keys:
      encode   → stats dict from file_to_vtxt()
      decode   → stats dict from vtxt_to_wav()
      vtxt_path, output_wav, duration_s, integrity_pct, peak, rms
    """
    import tempfile, os as _os

    audio_path = _os.path.abspath(audio_path)
    if not _os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Intermediate .vtxt path
    if vtxt_path is None:
        vtxt_path = _os.path.splitext(output_wav)[0] + "_temp.vtxt"

    print("=" * 64)
    print("  CONVERT AUDIO  →  WAV  (one-call pipeline)")
    print(f"  {_os.path.basename(audio_path)}  →  {_os.path.basename(vtxt_path)}"
          f"  →  {_os.path.basename(output_wav)}")
    print("=" * 64)
    print()

    # ── Step 1: audio file → .vtxt ────────────────────────────
    from recorder_converter.recorder import file_to_vtxt
    enc_stats = file_to_vtxt(
        audio_path  = audio_path,
        vtxt_path   = vtxt_path,
        sample_rate = sample_rate,
        frame_ms    = frame_ms,
    )

    # ── Step 2: .vtxt → WAV ───────────────────────────────────
    dec_stats = vtxt_to_wav(
        vtxt_path  = vtxt_path,
        output_wav = output_wav,
        play_audio = play,
    )

    # ── Cleanup temp .vtxt unless keep_vtxt=True ──────────────
    if not keep_vtxt and _os.path.exists(vtxt_path):
        _os.remove(vtxt_path)
        print(f"  [OK] Temp vtxt removed: {_os.path.basename(vtxt_path)}")

    print()
    print("=" * 64)
    print(f"  DONE  →  {_os.path.basename(output_wav)}")
    print(f"  Duration   : {dec_stats['duration_s']:.2f}s")
    print(f"  Integrity  : {dec_stats['integrity_pct']:.2f}%")
    print(f"  Peak       : {dec_stats['peak']:.6f}")
    print("=" * 64)
    print()

    return {
        "encode":        enc_stats,
        "decode":        dec_stats,
        "vtxt_path":     vtxt_path,
        "output_wav":    output_wav,
        "duration_s":    dec_stats["duration_s"],
        "integrity_pct": dec_stats["integrity_pct"],
        "peak":          dec_stats["peak"],
        "rms":           dec_stats["rms"],
    }
