"""
wavcore._codec.codec — Python bridge for the C engine
======================================================
Engine priority (highest first):
  1. wavcore._codec._codec_core  — cffi .pyd, compiled during pip install
  2. _codec_cffi                 — legacy local build (.pyd in same directory)
  3. Pure Python                 — binascii + numpy, already C-backed internally

All three tiers produce IDENTICAL results.
The C engine is ~10× faster on the hex encode/decode hot-path.
"""

import os
import sys
import zlib
import struct
import binascii
import numpy as np

# ── Engine discovery ─────────────────────────────────────────
_ffi = None
_lib = None
_ENGINE = "pure-python"

# Tier 1: package-installed cffi module
try:
    from wavcore._codec._codec_core import ffi as _ffi, lib as _lib  # type: ignore
    _ENGINE = "cffi-installed"
except ImportError:
    pass

# Tier 2: legacy local build (from previous vdat_txt_converter session)
if _ENGINE == "pure-python":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _HERE)
    try:
        from _codec_cffi import ffi as _ffi, lib as _lib  # type: ignore
        _ENGINE = "cffi-local"
    except ImportError:
        pass

# Tier 3: ctypes DLL fallback
_ctypes_lib = None
if _ENGINE == "pure-python":
    try:
        import ctypes, platform
        _sys = platform.system()
        _dll = ("codec_core.dll" if _sys == "Windows" else
                "codec_core.dylib" if _sys == "Darwin" else "codec_core.so")
        _dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), _dll)
        if os.path.exists(_dll_path):
            _L = ctypes.CDLL(_dll_path)
            _L.float32_array_to_hex.restype = None
            _ctypes_lib = _L
            _ENGINE = "ctypes"
    except (OSError, AttributeError):
        pass


# ── Status ────────────────────────────────────────────────────

def engine_info() -> str:
    labels = {
        "cffi-installed": "C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast",
        "cffi-local":     "C engine [cffi / local build .pyd]  — ultra-fast",
        "ctypes":         "C engine [ctypes DLL]  — fast",
        "pure-python":    "Pure-Python fallback (pip install wavcore to compile C engine)",
    }
    return labels.get(_ENGINE, _ENGINE)


# ── Internal cffi helpers ─────────────────────────────────────

def _is_cffi() -> bool:
    return _ENGINE in ("cffi-installed", "cffi-local")


# ── samples_to_hex ────────────────────────────────────────────

def samples_to_hex(samples: np.ndarray) -> str:
    """
    Convert a float32 numpy array → uppercase hex string.
    Lossless: encodes raw IEEE-754 bytes, no decimal rounding.
    """
    arr = np.ascontiguousarray(samples, dtype=np.float32)
    n   = len(arr)

    if _is_cffi():
        buf = _ffi.new("char[]", n * 8 + 1)
        ptr = _ffi.cast("float *", _ffi.from_buffer(arr))
        _lib.float32_array_to_hex(ptr, n, buf)
        return _ffi.string(buf).decode("ascii")

    if _ctypes_lib:
        import ctypes
        buf = ctypes.create_string_buffer(n * 8 + 1)
        ptr = arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        _ctypes_lib.float32_array_to_hex(ptr, n, buf)
        return buf.value.decode("ascii")

    return binascii.hexlify(arr.tobytes()).decode("ascii").upper()


# ── hex_to_samples ────────────────────────────────────────────

def hex_to_samples(hex_str: str, n_floats: int) -> np.ndarray:
    """Lossless inverse of samples_to_hex."""
    out = np.empty(n_floats, dtype=np.float32)

    if _is_cffi():
        ptr = _ffi.cast("float *", _ffi.from_buffer(out))
        ret = _lib.hex_to_float32_array(hex_str.encode("ascii"), n_floats, ptr)
        if ret != 0:
            raise ValueError("hex_to_samples: invalid hex character in input")
        return out

    if _ctypes_lib:
        import ctypes
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        ret = _ctypes_lib.hex_to_float32_array(
            hex_str.encode("ascii"), n_floats, ptr)
        if ret != 0:
            raise ValueError("hex_to_samples: invalid hex character in input")
        return out

    return np.frombuffer(binascii.unhexlify(hex_str), dtype=np.float32).copy()


# ── compute_frame_crc ─────────────────────────────────────────

def compute_frame_crc(version: int, frame_id: int, timestamp_ms: float,
                      sample_rate: int, channels: int, bit_depth: int,
                      payload: bytes) -> int:
    """
    CRC-32 over a packed .vdat frame header + payload bytes.
    Identical to: zlib.crc32(struct.pack(">BIdIBBI",...) + payload) & 0xFFFFFFFF
    """
    if _is_cffi():
        p = _ffi.from_buffer(payload)
        return int(_lib.frame_crc32(
            version, frame_id, timestamp_ms,
            sample_rate, channels, bit_depth,
            len(payload), _ffi.cast("uint8_t *", p), len(payload),
        ))

    if _ctypes_lib:
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

    hdr = struct.pack(">BIdIBBI",
                      version, frame_id, timestamp_ms,
                      sample_rate, channels, bit_depth, len(payload))
    return zlib.crc32(hdr + payload) & 0xFFFFFFFF


# ── batch_encode ─────────────────────────────────────────────

def batch_encode(audio: np.ndarray, spf: int) -> list:
    """
    Batch-encode all frames in a single C call.

    Parameters
    ----------
    audio : float32 1-D array; length must be >= n_frames * spf
    spf   : samples per frame (e.g. 960 for 20ms @ 48kHz)

    Returns
    -------
    list of n_frames uppercase hex strings
    """
    audio    = np.ascontiguousarray(audio, dtype=np.float32)
    n_frames = len(audio) // spf
    if n_frames == 0:
        return []
    stride = spf * 8 + 1

    if _is_cffi():
        buf = _ffi.new("char[]", n_frames * stride)
        ptr = _ffi.cast("float *", _ffi.from_buffer(audio))
        _lib.batch_hex_encode(ptr, n_frames, spf, buf, stride)
        raw = bytes(_ffi.buffer(buf, n_frames * stride))
        return [raw[i * stride: i * stride + spf * 8].decode("ascii")
                for i in range(n_frames)]

    if _ctypes_lib:
        import ctypes
        buf = ctypes.create_string_buffer(n_frames * stride)
        ptr = audio.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        _ctypes_lib.batch_hex_encode(ptr, n_frames, spf, buf, stride)
        raw = buf.raw
        return [raw[i * stride: i * stride + spf * 8].decode("ascii")
                for i in range(n_frames)]

    frames = audio[:n_frames * spf].reshape(n_frames, spf)
    return [binascii.hexlify(row.tobytes()).decode("ascii").upper()
            for row in frames]


# ── batch_decode ─────────────────────────────────────────────

def batch_decode(hex_list: list, spf: int) -> np.ndarray:
    """
    Batch-decode all frames in a single C call.

    Parameters
    ----------
    hex_list : list of hex strings (each exactly spf * 8 chars)
    spf      : samples per frame

    Returns
    -------
    float32 1-D array of length len(hex_list) * spf
    """
    n_frames = len(hex_list)
    out      = np.empty(n_frames * spf, dtype=np.float32)
    if n_frames == 0:
        return out
    stride = spf * 8 + 1

    if _is_cffi() and n_frames > 0:
        buf = _ffi.new("char[]", n_frames * stride)
        base = _ffi.cast("char *", buf)
        for i, hs in enumerate(hex_list):
            b = hs.encode("ascii")
            _ffi.memmove(base + i * stride, b, len(b))
        out_ptr = _ffi.cast("float *", _ffi.from_buffer(out))
        err = _lib.batch_hex_decode(base, n_frames, spf, out_ptr, stride)
        if err != 0:
            raise ValueError(f"batch_decode: invalid hex at frame index {err - 1}")
        return out

    if _ctypes_lib and n_frames > 0:
        import ctypes
        buf = ctypes.create_string_buffer(n_frames * stride)
        for i, hs in enumerate(hex_list):
            b = hs.encode("ascii")
            ctypes.memmove(ctypes.addressof(buf) + i * stride, b, len(b))
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        err = _ctypes_lib.batch_hex_decode(buf, n_frames, spf, ptr, stride)
        if err != 0:
            raise ValueError(f"batch_decode: invalid hex at frame index {err - 1}")
        return out

    for i, hs in enumerate(hex_list):
        chunk = np.frombuffer(binascii.unhexlify(hs), dtype=np.float32)
        out[i * spf: (i + 1) * spf] = chunk
    return out


# ── Self-test ─────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("=" * 58)
    print("  wavcore._codec.codec  —  self test")
    print(f"  Engine : {engine_info()}")
    print("=" * 58)

    N      = 960
    FRAMES = 500

    rng  = np.random.default_rng(42)
    orig = rng.standard_normal(N).astype(np.float32)

    # Round-trip
    t0 = time.perf_counter()
    h  = samples_to_hex(orig)
    t1 = time.perf_counter()
    back = hex_to_samples(h, N)
    t2 = time.perf_counter()
    assert np.array_equal(orig, back), "FAIL: single round-trip"
    print(f"  Single encode : {(t1-t0)*1e6:.1f} µs")
    print(f"  Single decode : {(t2-t1)*1e6:.1f} µs")
    print(f"  Round-trip    : PASSED")

    # CRC
    payload = orig.tobytes()
    crc_py  = zlib.crc32(struct.pack(">BIdIBBI",1,0,1000.,48000,1,32,len(payload))
                         + payload) & 0xFFFFFFFF
    crc_c   = compute_frame_crc(1, 0, 1000., 48000, 1, 32, payload)
    assert crc_py == crc_c, f"FAIL: CRC {crc_py:#010x} != {crc_c:#010x}"
    print(f"  CRC-32        : PASSED  ({crc_c:#010x})")

    # Batch
    big = rng.standard_normal(FRAMES * N).astype(np.float32)
    t0  = time.perf_counter()
    hl  = batch_encode(big, N)
    t1  = time.perf_counter()
    rec = batch_decode(hl, N)
    t2  = time.perf_counter()
    assert np.array_equal(big, rec), "FAIL: batch round-trip"
    enc_ms = (t1 - t0) * 1000
    dec_ms = (t2 - t1) * 1000
    print(f"  Batch encode  : PASSED  {FRAMES} frames → {enc_ms:.2f} ms  "
          f"({enc_ms/FRAMES*1000:.1f} µs/frame)")
    print(f"  Batch decode  : PASSED  {FRAMES} frames → {dec_ms:.2f} ms  "
          f"({dec_ms/FRAMES*1000:.1f} µs/frame)")
    print(f"  Real-time budget : 20,000 µs/frame")
    print(f"  Encode headroom  : {20000/(enc_ms/FRAMES*1000):.0f}×")
    print()
    print("  All tests PASSED.")
