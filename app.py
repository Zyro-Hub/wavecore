"""
================================================================
  VOICE EXPERIMENT 1  —  app.py
  Main Application Entry Point
================================================================

Uses the  wavcore  package (pip install wavcore).

Modes:
  [1] NORMAL MODE — Record full audio first, then encode to .vtxt
      (existing behaviour, batch C processing)

  [2] LIVE MODE   — Encode and write each frame to .vtxt in
      real-time while you speak. File grows on disk live.
      Press ENTER to stop early.

Pipeline (both modes):
  Microphone
      |
      v  record / live_record
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
DURATION_SEC     = 10      # Normal mode fixed duration
MAX_DURATION_SEC = 10     # Live mode max duration (press ENTER to stop early)
SAMPLE_RATE      = 48_000
FRAME_MS         = 20


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


def pick_mode() -> int:
    """Display mode menu and return 1 (Normal) or 2 (Live)."""
    print()
    print("################################################################")
    print("  VOICE EXPERIMENT 1  —  Select Recording Mode")
    print(f"  wavcore v{wavcore.__version__}  |  {wavcore.engine_info()}")
    print("################################################################")
    print()
    print("  ┌────────────────────────────────────────────────────────┐")
    print("  │  [1]  NORMAL MODE                                      │")
    print("  │       Record full audio, then encode all at once.      │")
    print("  │       (batch C processing — existing behaviour)        │")
    print("  │                                                        │")
    print("  │  [2]  LIVE MODE                                        │")
    print("  │       Each frame is encoded + written to .vtxt         │")
    print("  │       in real-time as you speak.                       │")
    print("  │       File grows on disk while recording.              │")
    print("  │       Press ENTER at any time to stop early.           │")
    print("  └────────────────────────────────────────────────────────┘")
    print()

    while True:
        choice = input("  Enter 1 or 2: ").strip()
        if choice in ("1", "2"):
            return int(choice)
        print("  [!] Please enter 1 or 2.")


def main():
    mode = pick_mode()

    if mode == 1:
        # ── NORMAL MODE ──────────────────────────────────────
        print()
        print("################################################################")
        print("  NORMAL MODE")
        print(f"  Record {DURATION_SEC}s → encode all → decode → play")
        print("################################################################")
        print()
        print(f"  [1]  Record {DURATION_SEC}s from microphone")
        print( "  [2]  Encode all frames to .vtxt  (batch C engine)")
        print( "  [3]  Decode .vtxt back to audio  (C engine)")
        print( "  [4]  Play reconstructed audio")
        print()
        print("  Output files:")
        print(f"    -> original_reference.wav   (raw capture)")
        print(f"    -> voice_data.vtxt          (text-encoded frames)")
        print(f"    -> reconstructed.wav        (rebuilt from vtxt)")
        print()
        input("  Press ENTER to start ...  ")

        t0 = time.time()

        banner("STEP 1 / 2  —  Record + encode to .vtxt  [NORMAL]")
        rec_stats = wavcore.record(
            vtxt_path   = VTXT_FILE,
            orig_wav    = ORIG_WAV,
            duration    = DURATION_SEC,
            sample_rate = SAMPLE_RATE,
            frame_ms    = FRAME_MS,
        )

    else:
        # ── LIVE MODE ────────────────────────────────────────
        print()
        print("################################################################")
        print("  LIVE MODE")
        print("  Frames written to .vtxt in real-time while you speak")
        print(f"  Max duration: {MAX_DURATION_SEC}s  |  Press ENTER to stop early")
        print("################################################################")
        print()
        print("  [1]  Open audio stream from microphone")
        print("  [2]  Each 20ms frame → C encode → CRC → write to .vtxt LIVE")
        print("  [3]  Press ENTER to stop, then decode → play")
        print()
        print("  Output files:")
        print(f"    -> original_reference.wav   (raw capture)")
        print(f"    -> voice_data.vtxt          (live-written frames)")
        print(f"    -> reconstructed.wav        (rebuilt from vtxt)")
        print()
        input("  Press ENTER to start ...  ")

        t0 = time.time()

        banner("STEP 1 / 2  —  Live recording → .vtxt  [LIVE]")
        rec_stats = wavcore.live_record(
            vtxt_path        = VTXT_FILE,
            orig_wav         = ORIG_WAV,
            max_duration     = MAX_DURATION_SEC,
            sample_rate      = SAMPLE_RATE,
            frame_ms         = FRAME_MS,
        )

    # ── STEP 2: .vtxt → WAV + playback (same for both modes) ─
    banner("STEP 2 / 2  —  Decode .vtxt → WAV + playback")
    conv_stats = wavcore.decode(
        vtxt_path  = VTXT_FILE,
        output_wav = RECON_WAV,
        play       = True,
    )

    # ── FINAL REPORT ─────────────────────────────────────────
    elapsed = time.time() - t0
    mode_label = "NORMAL" if mode == 1 else "LIVE"

    banner(f"EXPERIMENT 1  COMPLETE  [{mode_label} MODE]")
    print()
    print("  PIPELINE SUMMARY")
    print(f"  |- Mode              : {'Normal (batch)' if mode == 1 else 'Live (real-time write)'}")
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
