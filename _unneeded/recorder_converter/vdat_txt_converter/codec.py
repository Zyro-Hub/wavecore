"""
codec.py — C-engine wrapper for VDAT/VTXT codec
=================================================
Engine priority:
  1. _codec_cffi   (cffi-compiled 64-bit .pyd — fastest, MSVC/clang)
  2. codec_core.dll (ctypes 64-bit DLL — fast, needs matching arch)
  3. Pure Python    (numpy + binascii — already C-backed, ~5ms/500fr)

Build:
  Run  build_codec.py  once to compile _codec_cffi.pyd.
  No rebuild needed until codec_core.c changes.

Public API (same regardless of engine):
  engine_info()  -> str
  samples_to_hex(np.ndarray)         -> str
  hex_to_samples(str, int)           -> np.ndarray
  compute_frame_crc(...)             -> int
  batch_encode(np.ndarray, int)      -> list[str]
  batch_decode(list[str], int)       -> np.ndarray
=================================================
"""

import os
import sys
import zlib
import struct
import binascii
import platform
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ── Try engine 1: cffi-compiled .pyd (best — 64-bit, MSVC) ──
_cffi_ffi = None
_cffi_lib = None
_ENGINE   = "pure-python"

try:
    sys.path.insert(0, HERE)
    from _codec_cffi import ffi as _cffi_ffi, lib as _cffi_lib
    _ENGINE = "cffi"
except ImportError:
    pass

# ── Try engine 2: ctypes DLL (fallback if cffi not built) ────
_ctypes_lib = None
if _ENGINE == "pure-python":
    try:
        import ctypes
        _SYSTEM   = platform.system()
        _dll_name = "codec_core.dll" if _SYSTEM == "Windows" else \
                    ("codec_core.dylib" if _SYSTEM == "Darwin" else "codec_core.so")
        _dll_path = os.path.join(HERE, _dll_name)
        if os.path.exists(_dll_path):
            _L = ctypes.CDLL(_dll_path)
            # Quick sanity — will throw AttributeError if wrong arch
            _L.float32_array_to_hex.restype = None
            _ctypes_lib = _L
            import ctypes as _ct
            _ENGINE = "ctypes"
    except (OSError, AttributeError):
        pass


# ── Status ────────────────────────────────────────────────────

def engine_info() -> str:
    if _ENGINE == "cffi":
        return "C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast"
    if _ENGINE == "ctypes":
        return "C engine [ctypes DLL]  — fast"
    return ("Pure-Python fallback  "
            "[run build_codec.py for C engine]")


# ─── samples_to_hex ──────────────────────────────────────────

def samples_to_hex(samples: np.ndarray) -> str:
    """float32 array  →  uppercase hex string  (lossless IEEE-754)."""
    arr = np.ascontiguousarray(samples, dtype=np.float32)
    n   = len(arr)

    if _ENGINE == "cffi":
        buf = _cffi_ffi.new("char[]", n * 8 + 1)
        ptr = _cffi_ffi.cast("float *", _cffi_ffi.from_buffer(arr))
        _cffi_lib.float32_array_to_hex(ptr, n, buf)
        return _cffi_ffi.string(buf).decode("ascii")

    if _ENGINE == "ctypes":
        import ctypes
        buf = ctypes.create_string_buffer(n * 8 + 1)
        ptr = arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        _ctypes_lib.float32_array_to_hex(ptr, n, buf)
        return buf.value.decode("ascii")

    # Pure-Python (Python's .hex() is C-implemented)
    return binascii.hexlify(arr.tobytes()).decode("ascii").upper()


# ─── hex_to_samples ──────────────────────────────────────────

def hex_to_samples(hex_str: str, n_floats: int) -> np.ndarray:
    """Lossless inverse of samples_to_hex."""
    out = np.empty(n_floats, dtype=np.float32)

    if _ENGINE == "cffi":
        ptr = _cffi_ffi.cast("float *", _cffi_ffi.from_buffer(out))
        ret = _cffi_lib.hex_to_float32_array(
            hex_str.encode("ascii"), n_floats, ptr)
        if ret != 0:
            raise ValueError("hex_to_float32_array: invalid hex char")
        return out

    if _ENGINE == "ctypes":
        import ctypes
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ret = _ctypes_lib.hex_to_float32_array(
            hex_str.encode("ascii"), n_floats, ptr)
        if ret != 0:
            raise ValueError("hex_to_float32_array: invalid hex char")
        return out

    # Pure-Python
    return np.frombuffer(binascii.unhexlify(hex_str), dtype=np.float32).copy()


# ─── compute_frame_crc ───────────────────────────────────────

def compute_frame_crc(version, frame_id, timestamp_ms,
                      sample_rate, channels, bit_depth,
                      payload: bytes) -> int:
    """
    CRC-32 for one .vdat frame — identical to:
      zlib.crc32(struct.pack(">BIdIBBI", ...) + payload) & 0xFFFFFFFF
    """
    if _ENGINE == "cffi":
        p = _cffi_ffi.from_buffer(payload)
        return int(_cffi_lib.frame_crc32(
            version, frame_id, timestamp_ms,
            sample_rate, channels, bit_depth,
            len(payload),
            _cffi_ffi.cast("uint8_t *", p),
            len(payload),
        ))

    if _ENGINE == "ctypes":
        import ctypes
        return int(_ctypes_lib.frame_crc32(
            ctypes.c_uint8(version),
            ctypes.c_uint32(frame_id),
            ctypes.c_double(timestamp_ms),
            ctypes.c_uint32(sample_rate),
            ctypes.c_uint8(channels),
            ctypes.c_uint8(bit_depth),
            ctypes.c_uint32(len(payload)),
            payload,
            ctypes.c_uint32(len(payload)),
        ))

    # Pure-Python
    hdr = struct.pack(">BIdIBBI",
                      version, frame_id, timestamp_ms,
                      sample_rate, channels, bit_depth, len(payload))
    return zlib.crc32(hdr + payload) & 0xFFFFFFFF


# ─── batch_encode ────────────────────────────────────────────

def batch_encode(audio: np.ndarray, spf: int) -> list:
    """
    Encode all frames in one call.
    audio    : 1-D float32, length = n_frames * spf
    spf      : samples per frame
    Returns  : list of n_frames hex strings
    """
    audio    = np.ascontiguousarray(audio, dtype=np.float32)
    n_frames = len(audio) // spf
    stride   = spf * 8 + 1

    if _ENGINE == "cffi":
        buf = _cffi_ffi.new("char[]", n_frames * stride)
        ptr = _cffi_ffi.cast("float *", _cffi_ffi.from_buffer(audio))
        _cffi_lib.batch_hex_encode(ptr, n_frames, spf, buf, stride)
        raw = bytes(_cffi_ffi.buffer(buf, n_frames * stride))
        return [raw[i*stride: i*stride + spf*8].decode("ascii")
                for i in range(n_frames)]

    if _ENGINE == "ctypes":
        import ctypes
        buf = ctypes.create_string_buffer(n_frames * stride)
        ptr = audio.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        _ctypes_lib.batch_hex_encode(ptr, n_frames, spf, buf, stride)
        raw = buf.raw
        return [raw[i*stride: i*stride + spf*8].decode("ascii")
                for i in range(n_frames)]

    # Pure-Python batch (numpy reshape is O(0): view only)
    frames = audio[:n_frames * spf].reshape(n_frames, spf)
    return [binascii.hexlify(row.tobytes()).decode("ascii").upper()
            for row in frames]


# ─── batch_decode ────────────────────────────────────────────

def batch_decode(hex_list: list, spf: int) -> np.ndarray:
    """
    Decode a list of hex strings back to a contiguous float32 array.
    Inverse of batch_encode. Returns 1-D float32 array.
    """
    n_frames = len(hex_list)
    out      = np.empty(n_frames * spf, dtype=np.float32)
    stride   = spf * 8 + 1

    if _ENGINE == "cffi" and n_frames > 0:
        buf = _cffi_ffi.new("char[]", n_frames * stride)
        for i, hs in enumerate(hex_list):
            b = hs.encode("ascii")
            _cffi_ffi.memmove(
                _cffi_ffi.cast("char *", buf) + i * stride,
                b, len(b)
            )
        raw_ptr = _cffi_ffi.cast("char *", buf)
        out_ptr = _cffi_ffi.cast("float *", _cffi_ffi.from_buffer(out))
        err = _cffi_lib.batch_hex_decode(raw_ptr, n_frames, spf, out_ptr, stride)
        if err != 0:
            raise ValueError(f"batch_hex_decode: bad hex at frame {err}")
        return out

    if _ENGINE == "ctypes" and n_frames > 0:
        import ctypes
        buf = ctypes.create_string_buffer(n_frames * stride)
        for i, hs in enumerate(hex_list):
            b = hs.encode("ascii")
            ctypes.memmove(
                ctypes.addressof(buf) + i * stride, b, len(b))
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        err = _ctypes_lib.batch_hex_decode(buf, n_frames, spf, ptr, stride)
        if err != 0:
            raise ValueError(f"batch_hex_decode: bad hex at frame {err}")
        return out

    # Pure-Python
    for i, hs in enumerate(hex_list):
        chunk = np.frombuffer(binascii.unhexlify(hs), dtype=np.float32)
        out[i*spf: (i+1)*spf] = chunk
    return out


# ── Self-test ─────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    print("=" * 56)
    print("  codec.py  —  self test")
    print(f"  Engine : {engine_info()}")
    print("=" * 56)

    N = 960  # one 20ms frame @ 48kHz

    # ── Round-trip single frame ───────────────────────────────
    orig    = np.random.randn(N).astype(np.float32)
    t0      = time.perf_counter()
    hex_str = samples_to_hex(orig)
    t1      = time.perf_counter()
    back    = hex_to_samples(hex_str, N)
    t2      = time.perf_counter()

    assert np.array_equal(orig, back), "FAIL: round-trip mismatch"
    print(f"  Round-trip     : PASSED")
    print(f"  Encode 1 frame : {(t1-t0)*1e6:.1f} us")
    print(f"  Decode 1 frame : {(t2-t1)*1e6:.1f} us")

    # ── CRC check ─────────────────────────────────────────────
    payload = orig.tobytes()
    crc_py  = zlib.crc32(
        struct.pack(">BIdIBBI", 1, 0, 1000.0, 48000, 1, 32, len(payload))
        + payload
    ) & 0xFFFFFFFF
    crc_c   = compute_frame_crc(1, 0, 1000.0, 48000, 1, 32, payload)
    assert crc_py == crc_c, f"FAIL: CRC {crc_py:#010x} != {crc_c:#010x}"
    print(f"  CRC-32 check   : PASSED  ({crc_c:#010x})")

    # ── Batch (500 frames = full 10s recording) ───────────────
    FRAMES = 500
    big    = np.random.randn(FRAMES * N).astype(np.float32)

    t0       = time.perf_counter()
    hex_list = batch_encode(big, N)
    t1       = time.perf_counter()
    recovered= batch_decode(hex_list, N)
    t2       = time.perf_counter()

    assert np.array_equal(big, recovered), "FAIL: batch round-trip"
    enc_ms = (t1 - t0) * 1000
    dec_ms = (t2 - t1) * 1000

    print(f"  Batch encode   : PASSED  {FRAMES} frames -> {enc_ms:.2f} ms  "
          f"({enc_ms/FRAMES*1000:.1f} us/frame)")
    print(f"  Batch decode   : PASSED  {FRAMES} frames -> {dec_ms:.2f} ms  "
          f"({dec_ms/FRAMES*1000:.1f} us/frame)")
    print()
    print(f"  Real-time budget per frame : 20,000 us")
    print(f"  Encode uses                : {enc_ms/FRAMES*1000:.1f} us  "
          f"({20000/(enc_ms/FRAMES*1000):.0f}x faster than real-time)")
    print()
    print("  All tests PASSED.")
    print()
