"""Quick test of the installed wavcore package."""
import wavcore, time

print("wavcore version :", wavcore.__version__)
print("Engine          :", wavcore.engine_info())
print()

t0    = time.perf_counter()
stats = wavcore.decode(
    "voice_data.vtxt",
    "wavcore_reconstructed.wav",
    play=True,
)
wall  = (time.perf_counter() - t0) * 1000

print()
print("=" * 40)
print("  wavcore.decode() — results")
print("=" * 40)
for k, v in stats.items():
    if isinstance(v, float):
        print(f"  {k:<18}: {v:.4f}")
    else:
        print(f"  {k:<18}: {v}")
print(f"  {'wall time':<18}: {wall:.1f} ms")
print()
print("[ALL DONE]")
