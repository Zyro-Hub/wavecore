"""
recorder_converter — Voice Research Project Sub-Module
=======================================================
Sub-module that provides:
  record_to_vtxt()        — mic → .vtxt (batch, after capture)
  live_record_to_vtxt()   — mic → .vtxt (live, real-time write)
  vtxt_to_wav()           — .vtxt → reconstructed .wav + playback
"""

from .recorder  import record_to_vtxt, live_record_to_vtxt
from .converter import vtxt_to_wav

__all__ = ["record_to_vtxt", "live_record_to_vtxt", "vtxt_to_wav"]
