"""
wavcore._codec — cffi build descriptor
=======================================
Run by setuptools during  pip install  to compile
codec_core.c as a Python C extension.

The resulting module name is:
  wavcore._codec._codec_core
  (imported automatically by codec.py)
"""

import os
from cffi import FFI

HERE = os.path.dirname(os.path.abspath(__file__))

ffi = FFI()

ffi.cdef("""
    void     float32_array_to_hex(const float *samples, int n_floats, char *out_hex);
    int      hex_to_float32_array(const char *hex_str,  int n_floats, float *out_samples);

    uint32_t frame_crc32(
                 uint8_t  ver,  uint32_t fid, double ts,
                 uint32_t sr,   uint8_t  ch,  uint8_t  bd,
                 uint32_t plen, const uint8_t *payload, uint32_t psz);

    void     batch_hex_encode(const float *in_floats, int n_frames, int spf,
                              char *out_hex, int stride);
    int      batch_hex_decode(const char  *in_hex,   int n_frames, int spf,
                              float *out_floats, int stride);
""")

with open(os.path.join(HERE, "codec_core.c"), "r") as _f:
    _source = _f.read()

ffi.set_source("wavcore._codec._codec_core", _source)
