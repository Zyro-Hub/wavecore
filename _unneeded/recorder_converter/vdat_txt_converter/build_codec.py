"""
build_codec.py — Compile the C engine via cffi
================================================
Uses Python's cffi (cffi 2.0+) which auto-selects the correct
64-bit compiler for YOUR Python installation:
  - Windows : MSVC  (used to build Python itself)
  - Linux   : gcc
  - macOS   : clang

Output:  _codec_cffi.cp312-win_amd64.pyd  (or platform equivalent)
         Loaded automatically by codec.py — no manual steps needed.

Usage:
  python build_codec.py
================================================
"""

import os
import sys

HERE   = os.path.dirname(os.path.abspath(__file__))
C_SRC  = os.path.join(HERE, "codec_core.c")

if not os.path.exists(C_SRC):
    print(f"[ERR] Source not found: {C_SRC}")
    sys.exit(1)

print("=" * 60)
print("  CODEC BUILDER  —  codec_core.c  via cffi")
print("=" * 60)
print(f"  Source : {C_SRC}")

try:
    from cffi import FFI
except ImportError:
    print()
    print("  [ERR] cffi not installed.")
    print("  Fix : pip install cffi")
    sys.exit(1)

ffi = FFI()

ffi.cdef("""
    void     float32_array_to_hex(const float *samples, int n_floats, char *out_hex);
    int      hex_to_float32_array(const char *hex_str, int n_floats, float *out_samples);
    uint32_t frame_crc32(uint8_t ver, uint32_t fid, double ts, uint32_t sr,
                         uint8_t ch, uint8_t bd, uint32_t plen,
                         const uint8_t *payload, uint32_t psz);
    void     batch_hex_encode(const float *in_floats, int n_frames, int spf,
                              char *out_hex, int stride);
    int      batch_hex_decode(const char *in_hex, int n_frames, int spf,
                              float *out_floats, int stride);
""")

with open(C_SRC, "r") as f:
    source = f.read()

ffi.set_source("_codec_cffi", source)

print("  Compiling via cffi (uses MSVC/gcc/clang) ...", flush=True)
try:
    output = ffi.compile(tmpdir=HERE, verbose=True)
    size   = os.path.getsize(output)
    print()
    print("=" * 60)
    print(f"  [OK] Built  : {os.path.basename(output)}")
    print(f"  [OK] Size   : {size:,} bytes  ({size/1024:.1f} KB)")
    print(f"  [OK] Path   : {output}")
    print("=" * 60)
    print()
    print("  codec.py will now use the C engine automatically.")
    print("  Run  codec.py  to verify:  python codec.py")
    print()
except Exception as e:
    print(f"\n  [ERR] Build failed: {e}")
    print()
    print("  Make sure you have a C compiler:")
    print("    Windows : Visual Studio Build Tools")
    print("              https://visualstudio.microsoft.com/visual-cpp-build-tools/")
    print("    Linux   : sudo apt install gcc")
    print("    macOS   : xcode-select --install")
    sys.exit(1)
