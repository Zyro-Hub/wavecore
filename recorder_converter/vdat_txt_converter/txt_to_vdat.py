"""
txt_to_vdat.py — C-accelerated VTXT → VDAT Decoder
====================================================
Uses codec.py (C engine when compiled, Python fallback otherwise).

Hot path in C:
  * hex_to_float32_array  — ~10x faster than bytes.fromhex()
  * frame_crc32           — ~8x faster than Python zlib
  * batch_hex_decode      — all 500 frames in one C call

Usage:
  python txt_to_vdat.py                      # default paths
  python txt_to_vdat.py in.vtxt out.vdat     # custom paths
====================================================
"""

import struct
import zlib
import os
import sys
import time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from codec import hex_to_samples, compute_frame_crc, batch_decode, engine_info

# ── .vdat binary constants ───────────────────────────────────
FILE_HEADER_FMT  = ">4sBIIBBdI"
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FMT)

FRAME_HDR_FMT    = ">BIdIBBI"
FRAME_CRC_SIZE   = 4

# ── Default paths ────────────────────────────────────────────
PARENT      = os.path.dirname(os.path.dirname(HERE))
DEFAULT_IN  = os.path.join(PARENT, "voice_data.vtxt")
DEFAULT_OUT = os.path.join(PARENT, "voice_data_rebuilt.vdat")


def _parse_vtxt(path: str):
    """Parse .vtxt into (file_hdr dict, [frame dict, ...])."""
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
                required = {"FRAME_ID","FRAME_VERSION","TIMESTAMP_MS",
                            "SAMPLE_RATE","CHANNELS","BIT_DEPTH",
                            "PAYLOAD_LEN","SAMPLES_COUNT","ORIG_CRC32","SAMPLES_HEX"}
                missing = required - set(cur_fr)
                if missing:
                    raise ValueError(f"Frame {cur_fr.get('FRAME_ID','?')} missing: {missing}")
                frames.append(cur_fr)
                in_fr = False; continue
            if "=" not in line:
                raise ValueError(f"Line {lineno}: unexpected: {line!r}")
            k, _, v = line.partition("=")
            if in_fh: file_hdr[k.strip()] = v.strip()
            elif in_fr: cur_fr[k.strip()] = v.strip()

    if not file_hdr:
        raise ValueError("No [FILE_HEADER] found.")
    return file_hdr, frames


def decode(input_path=DEFAULT_IN, output_path=DEFAULT_OUT):
    print("=" * 64)
    print("  VTXT -> VDAT  (C-accelerated)")
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

    # ── Parse .vtxt ─────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        file_hdr, frames = _parse_vtxt(input_path)
    except ValueError as e:
        print(f"  [ERR] {e}")
        sys.exit(1)
    t_parse = (time.perf_counter() - t0) * 1000

    sr  = int(file_hdr["SAMPLE_RATE"])
    ch  = int(file_hdr["CHANNELS"])
    bd  = int(file_hdr["BIT_DEPTH"])
    spf = int(sr * 20 / 1000)
    n   = len(frames)

    print(f"  Parse .vtxt  : {t_parse:.1f} ms  ({n} frames)")
    print(f"  Sample rate  : {sr:,} Hz   channels={ch}   bit_depth={bd}")
    print()

    # ── Batch hex-decode all frames in one C call ─────────────
    t0 = time.perf_counter()
    hex_list = [fr["SAMPLES_HEX"] for fr in frames]
    try:
        audio_flat = batch_decode(hex_list, spf)
    except ValueError as e:
        print(f"  [ERR] Hex decode failed: {e}")
        sys.exit(1)
    t_decode = (time.perf_counter() - t0) * 1000
    print(f"  Hex decode   : {t_decode:.1f} ms  ({n} frames, C batch)")

    # ── Verify CRC per frame and build binary frames ──────────
    t0 = time.perf_counter()
    frame_bins   = []
    crc_ok_count = 0
    crc_bad_ids  = []

    for i, meta in enumerate(frames):
        ver   = int(meta["FRAME_VERSION"])
        fid   = int(meta["FRAME_ID"])
        ts_ms = float(meta["TIMESTAMP_MS"])
        fsr   = int(meta["SAMPLE_RATE"])
        fch   = int(meta["CHANNELS"])
        fbd   = int(meta["BIT_DEPTH"])
        plen  = int(meta["PAYLOAD_LEN"])
        orig_crc = int(meta["ORIG_CRC32"], 16)

        samples  = audio_flat[i * spf: (i + 1) * spf]
        payload  = samples.astype(np.float32).tobytes()

        # Recompute CRC using C engine
        computed = compute_frame_crc(ver, fid, ts_ms, fsr, fch, fbd, payload)

        if computed != orig_crc:
            crc_bad_ids.append(fid)
        else:
            crc_ok_count += 1

        # Build binary frame: header + payload + crc
        hdr_bytes = struct.pack(FRAME_HDR_FMT, ver, fid, ts_ms, fsr, fch, fbd, plen)
        frame_bins.append(hdr_bytes + payload + struct.pack(">I", computed))

    t_crc = (time.perf_counter() - t0) * 1000
    print(f"  CRC verify   : {t_crc:.1f} ms  ({crc_ok_count}/{n} OK)")
    if crc_bad_ids:
        print(f"  [WARN] CRC mismatches: {crc_bad_ids[:10]}")

    # ── Write .vdat ──────────────────────────────────────────
    t0 = time.perf_counter()
    file_hdr_bytes = struct.pack(
        FILE_HEADER_FMT,
        b"VDAT",
        int(file_hdr["FILE_VERSION"]),
        n,
        sr, ch, bd,
        float(file_hdr["DURATION_MS"]),
        int(file_hdr["CREATED_UNIX"]),
    )
    with open(output_path, "wb") as f:
        f.write(file_hdr_bytes)
        for fb in frame_bins:
            f.write(fb)
    t_write = (time.perf_counter() - t0) * 1000

    # ── Bit-perfect check against original ───────────────────
    orig_path   = os.path.join(PARENT, "voice_data.vdat")
    bit_perfect = None
    out_size    = os.path.getsize(output_path)

    if os.path.exists(orig_path) and output_path != orig_path:
        orig_size = os.path.getsize(orig_path)
        if orig_size == out_size:
            with open(orig_path, "rb") as f1, open(output_path, "rb") as f2:
                bit_perfect = f1.read() == f2.read()
        else:
            bit_perfect = False

    t_end = (time.perf_counter() - t_total) * 1000

    print(f"  Write .vdat  : {t_write:.1f} ms")
    print()
    print("=" * 64)
    print(f"  [OK] Output     : {output_path}")
    print(f"  [OK] Size       : {out_size:,} bytes  ({out_size/1024:.1f} KB)")
    print(f"  [OK] CRC intact : {crc_ok_count}/{n} frames")
    if bit_perfect is True:
        print(f"  [OK] Bit-perfect: YES — identical to original .vdat")
    elif bit_perfect is False:
        print(f"  [!!] Bit-perfect: NO  — differs from original")
    print(f"  [OK] Total time : {t_end:.1f} ms  ({t_end/n:.2f} ms/frame)")
    print("=" * 64)
    print()


if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    decode(inp, out)
