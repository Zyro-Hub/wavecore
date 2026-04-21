"""
=============================================================
  EXPERIMENT 1 — VOICE DIFFERENCE REPORT
  Voice Research Project | Phase 2: Quality Analysis
=============================================================

Compares:
  original_reference.wav   ← direct capture (ground-truth)
  reconstructed.wav        ← decoded from voice_data.vdat

Metrics computed:
  TIME DOMAIN
  ─────────────────────────────────────────────────────────
  [+]  RMSE           Root Mean Square Error
  [+]  MAE            Mean Absolute Error
  [+]  Max Error      Worst single-sample deviation
  [+]  Pearson r      Waveform correlation (-1 to +1)
  [+]  SNR            Signal-to-Noise Ratio (dB)
  [+]  PSNR           Peak SNR (dB)

  FREQUENCY DOMAIN
  ─────────────────────────────────────────────────────────
  [+]  FFT Magnitude Correlation    (how similar the spectrum is)
  [+]  Spectral Centroid Δ          (shift in "brightness")
  [+]  Spectral Energy Loss (dB)    (total energy preserved)

  PERCEPTUAL
  ─────────────────────────────────────────────────────────
  [+]  Dynamic Range comparison (dB)
  [+]  RMS per-second energy profile

  OUTPUT
  ─────────────────────────────────────────────────────────
  [+]  Prints full report to terminal
  [+]  Saves diff_report.png  (4-panel comparison plot)
=============================================================
"""

import wave
import numpy as np
import os
import sys

# ── Optional matplotlib ───────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")           # headless / no-GUI backend
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

# ─── Config ───────────────────────────────────────────────────
ORIG_WAV   = "original_reference.wav"
RECON_WAV  = "reconstructed.wav"
REPORT_PNG = "diff_report.png"


# ─── Helpers ──────────────────────────────────────────────────

def load_wav(path: str) -> tuple[np.ndarray, int]:
    """Load a WAV file. Returns (float32 array in [-1,1], sample_rate)."""
    if not os.path.exists(path):
        print(f"  [ERR]  File not found: {path}")
        sys.exit(1)

    with wave.open(path, "r") as wf:
        sr      = wf.getframerate()
        n_ch    = wf.getnchannels()
        sw      = wf.getsampwidth()
        n_fr    = wf.getnframes()
        raw     = wf.readframes(n_fr)

    # Decode PCM bytes
    if sw == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
    elif sw == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483647.0
    else:
        raise ValueError(f"Unsupported sample width: {sw}")

    # Mono: collapse channels
    if n_ch > 1:
        samples = samples.reshape(-1, n_ch).mean(axis=1)

    return samples, sr


def align(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Trim both arrays to the same length."""
    n = min(len(a), len(b))
    return a[:n], b[:n]


def snr_db(signal: np.ndarray, noise: np.ndarray) -> float:
    """SNR in dB.  noise = signal - reconstructed."""
    sig_power   = np.mean(signal ** 2)
    noise_power = np.mean(noise ** 2)
    if noise_power < 1e-12:
        return float("inf")
    return 10.0 * np.log10(sig_power / noise_power)


def psnr_db(signal: np.ndarray, noise: np.ndarray) -> float:
    """Peak SNR in dB."""
    peak        = float(np.max(np.abs(signal)))
    noise_power = np.mean(noise ** 2)
    if noise_power < 1e-12:
        return float("inf")
    return 10.0 * np.log10((peak ** 2) / noise_power)


def fft_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation between FFT magnitude spectra."""
    A = np.abs(np.fft.rfft(a))
    B = np.abs(np.fft.rfft(b))
    if A.std() < 1e-10 or B.std() < 1e-10:
        return 0.0
    return float(np.corrcoef(A, B)[0, 1])


def spectral_centroid(samples: np.ndarray, sr: int) -> float:
    """Spectral centroid in Hz."""
    mag   = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), 1.0 / sr)
    total = mag.sum()
    if total < 1e-10:
        return 0.0
    return float(np.dot(freqs, mag) / total)


def spectral_energy_loss_db(orig: np.ndarray, recon: np.ndarray) -> float:
    """How much total spectral energy was gained/lost (dB >0 = preserved)."""
    e_orig  = np.sum(np.abs(np.fft.rfft(orig)) ** 2)
    e_recon = np.sum(np.abs(np.fft.rfft(recon)) ** 2)
    if e_orig < 1e-12:
        return 0.0
    return 10.0 * np.log10(e_recon / e_orig)


def dynamic_range_db(samples: np.ndarray) -> float:
    """Dynamic range in dB (peak / RMS)."""
    rms = float(np.sqrt(np.mean(samples ** 2)))
    pk  = float(np.max(np.abs(samples)))
    if rms < 1e-12:
        return 0.0
    return 20.0 * np.log10(pk / rms)


def rms_per_second(samples: np.ndarray, sr: int) -> np.ndarray:
    """RMS energy in each 1-second window."""
    n_sec = len(samples) // sr
    out   = []
    for i in range(n_sec):
        chunk = samples[i * sr:(i + 1) * sr]
        out.append(float(np.sqrt(np.mean(chunk ** 2))))
    return np.array(out)


def quality_grade(snr: float) -> str:
    if snr == float("inf"): return "PERFECT  ★★★★★"
    if snr >= 60:  return "Excellent ★★★★★"
    if snr >= 40:  return "Very Good ★★★★☆"
    if snr >= 30:  return "Good      ★★★☆☆"
    if snr >= 20:  return "Fair      ★★☆☆☆"
    if snr >= 10:  return "Poor      ★☆☆☆☆"
    return          "Bad       ☆☆☆☆☆"


# ─── Plot ─────────────────────────────────────────────────────

def make_plot(orig, recon, diff, sr, corr_r, snr, rms_orig, rms_recon):
    fig = plt.figure(figsize=(16, 10), facecolor="#0d1117")
    fig.suptitle(
        "Voice Experiment 1 — Difference Report",
        fontsize=16, fontweight="bold", color="white", y=0.98
    )

    gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.52, wspace=0.35)

    t = np.linspace(0, len(orig) / sr, len(orig))

    # Colour theme
    C_ORIG  = "#58a6ff"
    C_RECON = "#3fb950"
    C_DIFF  = "#f85149"
    C_GRID  = "#21262d"
    C_TEXT  = "#c9d1d9"

    def style(ax, title, xlabel, ylabel):
        ax.set_facecolor("#161b22")
        ax.set_title(title, color=C_TEXT, fontsize=10, pad=6)
        ax.set_xlabel(xlabel, color=C_TEXT, fontsize=8)
        ax.set_ylabel(ylabel, color=C_TEXT, fontsize=8)
        ax.tick_params(colors=C_TEXT, labelsize=7)
        ax.grid(True, color=C_GRID, linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_edgecolor(C_GRID)

    # ── Panel 1: Waveform overlay ─────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(t, orig,  color=C_ORIG,  linewidth=0.5, alpha=0.9, label="Original")
    ax1.plot(t, recon, color=C_RECON, linewidth=0.5, alpha=0.75, label="Reconstructed")
    ax1.legend(loc="upper right", fontsize=8, facecolor="#21262d",
               labelcolor=C_TEXT, edgecolor=C_GRID)
    style(ax1, "Waveform — Original vs Reconstructed", "Time (s)", "Amplitude")

    # ── Panel 2: Difference signal ────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(t, diff, color=C_DIFF, linewidth=0.5, alpha=0.9)
    ax2.axhline(0, color="#555", linewidth=0.4)
    style(ax2, f"Difference Signal  (RMSE = {np.sqrt(np.mean(diff**2)):.5f})",
          "Time (s)", "Error")

    # ── Panel 3: FFT Spectrum ─────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    freqs   = np.fft.rfftfreq(len(orig), 1.0 / sr)
    mag_o   = 20 * np.log10(np.abs(np.fft.rfft(orig))   + 1e-12)
    mag_r   = 20 * np.log10(np.abs(np.fft.rfft(recon))  + 1e-12)
    ax3.plot(freqs / 1000, mag_o, color=C_ORIG,  linewidth=0.7, alpha=0.9, label="Original")
    ax3.plot(freqs / 1000, mag_r, color=C_RECON, linewidth=0.7, alpha=0.75, label="Reconstructed")
    ax3.set_xlim(0, sr / 2000)
    ax3.legend(loc="upper right", fontsize=7, facecolor="#21262d",
               labelcolor=C_TEXT, edgecolor=C_GRID)
    style(ax3, f"FFT Spectrum  (corr = {corr_r:.4f})", "Frequency (kHz)", "Magnitude (dB)")

    # ── Panel 4: RMS per-second energy ───────────────────────
    ax4 = fig.add_subplot(gs[2, :])
    secs = np.arange(len(rms_orig))
    ax4.bar(secs - 0.2, rms_orig,  0.38, color=C_ORIG,  alpha=0.85, label="Original")
    ax4.bar(secs + 0.2, rms_recon, 0.38, color=C_RECON, alpha=0.85, label="Reconstructed")
    ax4.legend(loc="upper right", fontsize=8, facecolor="#21262d",
               labelcolor=C_TEXT, edgecolor=C_GRID)
    style(ax4, "RMS Energy per Second", "Second", "RMS")

    # ── Watermark SNR ─────────────────────────────────────────
    fig.text(
        0.5, 0.01,
        f"SNR = {snr:.2f} dB   |   Pearson r = {corr_r:.6f}   |   {quality_grade(snr)}",
        ha="center", fontsize=10, color="#8b949e", style="italic"
    )

    plt.savefig(REPORT_PNG, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [CHART]  Plot saved → {REPORT_PNG}")


# ─── Main ─────────────────────────────────────────────────────

def run_report():
    print("=" * 62)
    print("  VOICE DIFFERENCE REPORT  —  Experiment 1")
    print("=" * 62)

    orig,  sr1 = load_wav(ORIG_WAV)
    recon, sr2 = load_wav(RECON_WAV)

    print(f"  Original WAV    : {ORIG_WAV}  ({len(orig):,} samples @ {sr1:,} Hz)")
    print(f"  Reconstructed   : {RECON_WAV}  ({len(recon):,} samples @ {sr2:,} Hz)")

    if sr1 != sr2:
        print(f"  [WARN]  Sample rate mismatch ({sr1} vs {sr2}) — report may be inaccurate.")

    orig, recon = align(orig, recon)
    diff = orig - recon

    n   = len(orig)
    sr  = sr1

    # ── Time-domain metrics ───────────────────────────────────
    rmse  = float(np.sqrt(np.mean(diff ** 2)))
    mae   = float(np.mean(np.abs(diff)))
    max_e = float(np.max(np.abs(diff)))
    corr  = float(np.corrcoef(orig, recon)[0, 1]) if orig.std() > 1e-10 else 0.0
    snr   = snr_db(orig, diff)
    psnr  = psnr_db(orig, diff)

    # ── Freq-domain metrics ───────────────────────────────────
    fft_corr  = fft_correlation(orig, recon)
    sc_orig   = spectral_centroid(orig,  sr)
    sc_recon  = spectral_centroid(recon, sr)
    sc_delta  = sc_recon - sc_orig
    spec_loss = spectral_energy_loss_db(orig, recon)

    # ── Perceptual metrics ────────────────────────────────────
    dr_orig  = dynamic_range_db(orig)
    dr_recon = dynamic_range_db(recon)
    rms_o    = rms_per_second(orig,  sr)
    rms_r    = rms_per_second(recon, sr)

    # ── Print report ──────────────────────────────────────────
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │             TIME-DOMAIN  METRICS                    │")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  RMSE            : {rmse:.8f}                      ")
    print(f"  │  MAE             : {mae:.8f}                       ")
    print(f"  │  Max Error       : {max_e:.8f}                     ")
    print(f"  │  Pearson r       : {corr:.8f}  (1.0 = identical)   ")
    print(f"  │  SNR             : {snr:>10.4f} dB                 ")
    print(f"  │  PSNR            : {psnr:>10.4f} dB                ")
    print("  ├─────────────────────────────────────────────────────┤")
    print("  │             FREQUENCY-DOMAIN  METRICS               │")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  FFT Corr        : {fft_corr:.8f}  (1.0 = identical spectrum)")
    print(f"  │  Spectral Cent.  : {sc_orig:>9.2f} Hz  →  {sc_recon:.2f} Hz  (Δ {sc_delta:+.2f} Hz)")
    print(f"  │  Spectral Energy : {spec_loss:>+.4f} dB  (0 = no loss)  ")
    print("  ├─────────────────────────────────────────────────────┤")
    print("  │             PERCEPTUAL  METRICS                     │")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  Dyn. Range Orig : {dr_orig:>8.3f} dB              ")
    print(f"  │  Dyn. Range Rcon : {dr_recon:>8.3f} dB              ")
    print(f"  │  DR Δ            : {dr_recon - dr_orig:>+8.3f} dB              ")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  Samples compared: {n:,}                            ")
    print(f"  │  Duration        : {n/sr:.2f} s                    ")
    print("  ├─────────────────────────────────────────────────────┤")
    print(f"  │  QUALITY GRADE   :  {quality_grade(snr):<35}│")
    print("  └─────────────────────────────────────────────────────┘")

    # ── Interpretation ───────────────────────────────────────
    print()
    print("  INTERPRETATION")
    print("  ─────────────────────────────────────────────")

    if snr == float("inf"):
        print("  [OK]  Bit-perfect reconstruction. Zero difference.")
    elif snr >= 60:
        print("  [OK]  Inaudible difference. Human ear cannot distinguish.")
    elif snr >= 40:
        print("  [OK]  Excellent. Very minor quantisation noise only.")
    elif snr >= 30:
        print("  [WARN]  Good. Slight noise floor, acceptable for voice.")
    elif snr >= 20:
        print("  [WARN]  Fair. Audible noise. Encoding pipeline lossy.")
    else:
        print("  [ERR]  Poor. Significant signal loss during encode/decode.")

    if abs(sc_delta) < 50:
        print("  [OK]  Spectral centroid match: tonal character preserved.")
    else:
        print(f"  [WARN]  Spectral centroid shifted {sc_delta:+.1f} Hz (timbral change).")

    if fft_corr > 0.999:
        print("  [OK]  FFT spectrum near-identical.")
    elif fft_corr > 0.99:
        print("  [OK]  FFT spectrum highly correlated.")
    else:
        print(f"  [WARN]  FFT correlation only {fft_corr:.4f} — spectral content changed.")

    # ── Plot ─────────────────────────────────────────────────
    print()
    if HAS_PLOT:
        print("  Generating comparison plot ...")
        make_plot(orig, recon, diff, sr, fft_corr, snr, rms_o, rms_r)
    else:
        print("  [i]️  matplotlib not found — skipping plot.")
        print("     Install with:  pip install matplotlib")

    print()
    print("=" * 62)
    print("  [OK]  Report complete.")
    print("=" * 62)
    print()


if __name__ == "__main__":
    run_report()
