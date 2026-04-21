"""
================================================================
  VOICE EXPERIMENT 1  —  app.py
  Main Application Entry Point
================================================================

Uses the  wavcore  package (pip install wavcore).

Pipeline:
  Microphone
      |
      v  wavcore.record()
      |-- voice_data.vtxt          (text-based frame codec, CRC-32)
      |-- original_reference.wav   (raw capture, ground-truth)
      |
      v  wavcore.decode()
      |-- reconstructed.wav        (rebuilt from voice_data.vtxt)
      |-- plays audio through speakers

Dependencies installed automatically with wavcore:
  numpy, sounddevice, cffi (C engine)

Run:
  python app.py
================================================================
"""

import os
import sys
import time

# ── wavcore is installed via  pip install -e .  (or pip install wavcore)
import wavcore

# ── Output paths ─────────────────────────────────────────────
HERE       = os.path.dirname(os.path.abspath(__file__))
VTXT_FILE  = os.path.join(HERE, "voice_data.vtxt")
ORIG_WAV   = os.path.join(HERE, "original_reference.wav")
RECON_WAV  = os.path.join(HERE, "reconstructed.wav")

# ── Recording config ─────────────────────────────────────────
DURATION_SEC = 10
SAMPLE_RATE  = 48_000
FRAME_MS     = 20


def banner(text: str):
    w = 64
    print()
    print("=" * w)
    print(f"  {text}")
    print("=" * w)


def file_summary(label: str, path: str):
    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"  {label:<30} {os.path.basename(path)}")
    print(f"  {'':30} {size:,} bytes  ({size / 1024:.1f} KB)")


def main():
    print()
    print("################################################################")
    print("  VOICE EXPERIMENT 1  —  Full Pipeline")
    print(f"  wavcore v{wavcore.__version__}  |  {wavcore.engine_info()}")
    print("################################################################")
    print()
    print(f"  [1]  Record {DURATION_SEC}s from microphone")
    print( "  [2]  Encode directly to .vtxt  (CRC-32 per frame)")
    print( "  [3]  Decode .vtxt back to audio  (C engine)")
    print( "  [4]  Play reconstructed audio")
    print()
    print("  Output files:")
    print(f"    -> original_reference.wav   (raw capture)")
    print(f"    -> voice_data.vtxt          (text-encoded frames)")
    print(f"    -> reconstructed.wav        (rebuilt from vtxt)")
    print()
    input("  Press ENTER to start ...  ")
    print()

    t0 = time.time()

    # ── STEP 1: Record → .vtxt ────────────────────────────────
    banner("STEP 1 / 2  —  Record + encode to .vtxt")
    rec_stats = wavcore.record(
        vtxt_path   = VTXT_FILE,
        orig_wav    = ORIG_WAV,
        duration    = DURATION_SEC,
        sample_rate = SAMPLE_RATE,
        frame_ms    = FRAME_MS,
    )

    # ── STEP 2: .vtxt → WAV + playback ───────────────────────
    banner("STEP 2 / 2  —  Decode .vtxt → WAV + playback")
    conv_stats = wavcore.decode(
        vtxt_path  = VTXT_FILE,
        output_wav = RECON_WAV,
        play       = True,
    )

    # ── FINAL REPORT ─────────────────────────────────────────
    elapsed = time.time() - t0

    banner("EXPERIMENT 1  COMPLETE")
    print()
    print("  PIPELINE SUMMARY")
    print(f"  |- wavcore engine    : {wavcore.engine_info()}")
    print(f"  |- Total time        : {elapsed:.1f} s  (incl. recording + playback)")
    print(f"  |- Codec pipeline    : {conv_stats['total_ms']:.1f} ms")
    print(f"  |- Frames encoded    : {rec_stats['frames']}")
    print(f"  |- Frames valid      : {conv_stats['ok_frames']}")
    print(f"  |- Frames bad        : {conv_stats['bad_frames']}")
    print(f"  |- Integrity         : {conv_stats['integrity_pct']:.2f}%")
    print(f"  |- Audio duration    : {conv_stats['duration_s']:.2f} s")
    print(f"  |- Peak amplitude    : {conv_stats['peak']:.6f}")
    print()
    print("  OUTPUT FILES")
    file_summary("[1] Original WAV  ->", ORIG_WAV)
    print()
    file_summary("[2] voice_data.vtxt ->", VTXT_FILE)
    print()
    file_summary("[3] Reconstructed ->", RECON_WAV)
    print()

    if conv_stats["integrity_pct"] == 100.0:
        print("  [RESULT]  PERFECT — 100% frame integrity, lossless reconstruction.")
    elif conv_stats["integrity_pct"] >= 95.0:
        print(f"  [RESULT]  GOOD — {conv_stats['integrity_pct']:.1f}% integrity.")
    else:
        print(f"  [RESULT]  DEGRADED — {conv_stats['integrity_pct']:.1f}% integrity.")

    print()
    print("  Tip: run  diff_report.py  for a detailed quality comparison")
    print("       between original_reference.wav and reconstructed.wav")
    print()
    print("################################################################")
    print()


if __name__ == "__main__":
    main()
