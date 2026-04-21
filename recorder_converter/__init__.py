"""
recorder_converter — Voice Research Project Sub-Module
=======================================================
Sub-module that provides:
  record_to_vtxt()        — mic → .vtxt (batch, after capture)
  live_record_to_vtxt()   — mic → .vtxt (live, real-time write)
  file_to_vtxt()          — audio file → .vtxt (no mic needed)
  vtxt_to_wav()           — .vtxt → reconstructed .wav + playback
  convert_audio()         — audio file → WAV directly (one call, no mic)
"""

from .recorder  import record_to_vtxt, live_record_to_vtxt, file_to_vtxt
from .converter import vtxt_to_wav, convert_audio

__all__ = [
    "record_to_vtxt", "live_record_to_vtxt", "file_to_vtxt",
    "vtxt_to_wav", "convert_audio",
]
