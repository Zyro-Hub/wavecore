"""
vdat_to_txt.py — C-accelerated VDAT → VTXT Encoder
====================================================
Uses codec.py (C engine when compiled, Python fallback otherwise).

Hot path in C:
  * float32_array_to_hex  — ~10x faster than Python .hex()
  * frame_crc32           — ~8x faster than Python zlib
  * batch_hex_encode      — all 500 frames in one C call

Usage:
  python vdat_to_txt.py                      # default paths
  python vdat_to_txt.py in.vdat out.vtxt     # custom paths
====================================================
"""

import struct
import os
import sys
import time
import datetime

# ── Load C engine (auto-fallback to Python if not compiled) ──
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from codec import samples_to_hex, compute_frame_crc, batch_encode, engine_info
import numpy as np

# ── .vdat binary constants ───────────────────────────────────
FILE_HEADER_FMT  = ">4sBIIBBdI"
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FMT)   # 27

FRAME_HDR_FMT    = ">BIdIBBI"
FRAME_HDR_SIZE   = struct.calcsize(FRAME_HDR_FMT)     # 23
FRAME_CRC_SIZE   = 4

CODEC_VERSION    = 1

# ── Default paths ────────────────────────────────────────────
PARENT  = os.path.dirname(os.path.dirname(HERE))
DEFAULT_IN  = os.path.join(PARENT, "voice_data.vdat")
DEFAULT_OUT = os.path.join(PARENT, "voice_data.vtxt")


def _read_file_header(f):
    raw = f.read(FILE_HEADER_SIZE)
    if len(raw) < FILE_HEADER_SIZE:
        raise ValueError("File too small.")
    magic, fv, total_fr, sr, ch, bd, dur_ms, created = \
        struct.unpack(FILE_HEADER_FMT, raw)
    if magic != b"VDAT":
        raise ValueError(f"Bad magic: {magic!r}")
    return dict(file_version=fv, total_frames=total_fr,
                sample_rate=sr, channels=ch, bit_depth=bd,
                duration_ms=dur_ms, created_unix=created)


def encode(input_path=DEFAULT_IN, output_path=DEFAULT_OUT):
    print("=" * 64)
    print("  VDAT -> VTXT  (C-accelerated)")
    print(f"  Engine   : {engine_info()}")
    print("=" * 64)

    if not os.path.exists(input_path):
        print(f"  [ERR] Not found: {input_path}")
        sys.exit(1)

    in_size = os.path.getsize(input_path)
    print(f"  Input  : {input_path}")
    print(f"  Size   : {in_size:,} bytes  ({in_size/1024:.1f} KB)")
    print()

    t_total = time.perf_counter()

    # ── Read entire .vdat into memory ────────────────────────
    t0 = time.perf_counter()
    with open(input_path, "rb") as f:
        hdr = _read_file_header(f)
        raw_frames = f.read()           # all frame bytes at once
    t_read = (time.perf_counter() - t0) * 1000

    sr   = hdr["sample_rate"]
    ch   = hdr["channels"]
    bd   = hdr["bit_depth"]
    spf  = int(sr * 20 / 1000)         # samples per 20 ms frame

    created_str = datetime.datetime.utcfromtimestamp(
        hdr["created_unix"]
    ).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_utc = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"  File read    : {t_read:.1f} ms")
    print(f"  Frames decl. : {hdr['total_frames']}")
    print(f"  Sample rate  : {sr:,} Hz   channels={ch}   bit_depth={bd}")
    print()

    # ── Parse frames and collect audio + metadata ─────────────
    t0 = time.perf_counter()
    frame_meta  = []       # list of dicts: {frame_id, ts_ms, plen, orig_crc}
    all_samples = []       # list of float32 arrays

    pos = 0
    while pos < len(raw_frames):
        if pos + FRAME_HDR_SIZE > len(raw_frames):
            break
        hdr_raw = raw_frames[pos: pos + FRAME_HDR_SIZE]
        ver, fid, ts_ms, fsr, fch, fbd, plen = struct.unpack(FRAME_HDR_FMT, hdr_raw)
        pos += FRAME_HDR_SIZE

        if pos + plen + FRAME_CRC_SIZE > len(raw_frames):
            break
        payload  = raw_frames[pos: pos + plen]
        crc_raw  = raw_frames[pos + plen: pos + plen + FRAME_CRC_SIZE]
        orig_crc = struct.unpack(">I", crc_raw)[0]
        pos     += plen + FRAME_CRC_SIZE

        # Verify CRC using C engine
        computed = compute_frame_crc(ver, fid, ts_ms, fsr, fch, fbd, payload)
        if computed != orig_crc:
            print(f"  [WARN] Frame {fid}: CRC mismatch (included anyway)")

        samples = np.frombuffer(payload, dtype=np.float32).copy()
        all_samples.append(samples)
        frame_meta.append(dict(
            frame_id=fid, ts_ms=ts_ms, plen=plen,
            ver=ver, sr=fsr, ch=fch, bd=fbd,
            orig_crc=f"{orig_crc:08X}"
        ))

    t_parse = (time.perf_counter() - t0) * 1000
    actual_frames = len(frame_meta)
    print(f"  Parse + CRC  : {t_parse:.1f} ms  ({actual_frames} frames)")

    # ── Batch hex-encode all samples in one C call ────────────
    t0 = time.perf_counter()

    # Build contiguous float32 array (all frames)
    audio_flat = np.concatenate(all_samples).astype(np.float32)
    # Pad to exact multiple of spf
    remainder = len(audio_flat) % spf
    if remainder:
        audio_flat = np.append(audio_flat,
                               np.zeros(spf - remainder, dtype=np.float32))

    hex_list = batch_encode(audio_flat, spf)
    t_hex = (time.perf_counter() - t0) * 1000
    print(f"  Hex encode   : {t_hex:.1f} ms  ({actual_frames} frames, C batch)")

    # ── Write .vtxt ──────────────────────────────────────────
    t0 = time.perf_counter()
    with open(output_path, "w", encoding="utf-8") as f:

        # File comment header
        f.write("# ================================================================\n")
        f.write("# VDAT TEXT CODEC  v1  (C-accelerated encoder)\n")
        f.write("# Encoder  : vdat_to_txt.py + codec_core (C engine)\n")
        f.write(f"# Source   : {os.path.basename(input_path)}\n")
        f.write(f"# Encoded  : {now_utc}\n")
        f.write("#\n")
        f.write("# SAMPLE ENCODING:\n")
        f.write("#   SAMPLES_HEX = raw IEEE-754 float32 bytes, uppercase hex\n")
        f.write("#   Lossless -- no floating-point rounding\n")
        f.write(f"#   Engine: {engine_info()}\n")
        f.write("# ================================================================\n\n")

        # [FILE_HEADER]
        f.write("[FILE_HEADER]\n")
        f.write(f"CODEC_VERSION={CODEC_VERSION}\n")
        f.write(f"FILE_VERSION={hdr['file_version']}\n")
        f.write(f"TOTAL_FRAMES={actual_frames}\n")
        f.write(f"SAMPLE_RATE={sr}\n")
        f.write(f"CHANNELS={ch}\n")
        f.write(f"BIT_DEPTH={bd}\n")
        f.write(f"DURATION_MS={hdr['duration_ms']:.6f}\n")
        f.write(f"CREATED_UNIX={hdr['created_unix']}\n")
        f.write(f"CREATED_UTC={created_str}\n")
        f.write("[/FILE_HEADER]\n\n")

        # [FRAME] blocks
        for i, meta in enumerate(frame_meta):
            hex_str = hex_list[i] if i < len(hex_list) else ""
            f.write("[FRAME]\n")
            f.write(f"FRAME_ID={meta['frame_id']}\n")
            f.write(f"FRAME_VERSION={meta['ver']}\n")
            f.write(f"TIMESTAMP_MS={meta['ts_ms']:.6f}\n")
            f.write(f"SAMPLE_RATE={meta['sr']}\n")
            f.write(f"CHANNELS={meta['ch']}\n")
            f.write(f"BIT_DEPTH={meta['bd']}\n")
            f.write(f"PAYLOAD_LEN={meta['plen']}\n")
            f.write(f"SAMPLES_COUNT={meta['plen'] // 4}\n")
            f.write(f"ORIG_CRC32={meta['orig_crc']}\n")
            f.write(f"SAMPLES_HEX={hex_str}\n")
            f.write("[/FRAME]\n\n")

    t_write = (time.perf_counter() - t0) * 1000
    out_size = os.path.getsize(output_path)
    t_end = (time.perf_counter() - t_total) * 1000

    print(f"  Write .vtxt  : {t_write:.1f} ms")
    print()
    print("=" * 64)
    print(f"  [OK] Output  : {output_path}")
    print(f"  [OK] Size    : {out_size:,} bytes  ({out_size/1024:.1f} KB)")
    print(f"  [OK] Total   : {t_end:.1f} ms  for {actual_frames} frames")
    print(f"  [OK] Speed   : {t_end/actual_frames:.2f} ms/frame")
    print("=" * 64)
    print()


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    encode(inp, out)
