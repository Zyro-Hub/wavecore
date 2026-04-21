"""
recorder_converter — Voice Research Project Sub-Module
=======================================================
Sub-module that provides:
  record_to_vtxt()   — mic → .vtxt (direct, no intermediate .vdat)
  vtxt_to_wav()      — .vtxt → reconstructed .wav + playback
"""

from .recorder  import record_to_vtxt
from .converter import vtxt_to_wav

__all__ = ["record_to_vtxt", "vtxt_to_wav"]
