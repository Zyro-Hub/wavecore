"""
wavcore — Ultra-Fast Lossless Voice Codec
==========================================
Real-time audio capture, VTXT text serialization,
and bit-perfect reconstruction with a C engine.

Quick start
-----------
>>> import wavcore
>>> wavcore.record("audio.vtxt", "original.wav")
>>> wavcore.decode("audio.vtxt", "reconstructed.wav")
>>> print(wavcore.engine_info())

Version history
---------------
1.0.0  Initial release
"""

__version__ = "1.0.0"
__author__  = "WavCore Project"
__license__ = "MIT"

# ── Lazy imports (avoid loading sounddevice at import time) ──
def record(
    vtxt_path:    str,
    orig_wav:     str  = "original.wav",
    duration:     int  = 10,
    sample_rate:  int  = 48_000,
    frame_ms:     int  = 20,
) -> dict:
    """
    Record `duration` seconds from the microphone.

    Parameters
    ----------
    vtxt_path   : output .vtxt file path
    orig_wav    : output original reference WAV path
    duration    : recording length in seconds (default 10)
    sample_rate : Hz (default 48000)
    frame_ms    : frame size in milliseconds (default 20)

    Returns
    -------
    dict with keys: frames, duration_ms, sample_rate, channels,
                    peak, rms, vtxt_path, orig_wav_path,
                    created_unix, vtxt_size, encode_ms
    """
    from wavcore.recorder import record_to_vtxt
    return record_to_vtxt(vtxt_path, orig_wav, duration, sample_rate, frame_ms)


def decode(
    vtxt_path:  str,
    output_wav: str  = "reconstructed.wav",
    play:       bool = True,
) -> dict:
    """
    Decode a .vtxt file back to audio.

    Parameters
    ----------
    vtxt_path  : input .vtxt file path
    output_wav : output WAV file path
    play       : whether to play audio through speakers (default True)

    Returns
    -------
    dict with keys: ok_frames, bad_frames, integrity_pct,
                    duration_s, peak, rms, output_wav,
                    sample_rate, total_ms
    """
    from wavcore.converter import vtxt_to_wav
    return vtxt_to_wav(vtxt_path, output_wav, play)


def engine_info() -> str:
    """Return a string describing the active C engine."""
    from wavcore._codec.codec import engine_info as _ei
    return _ei()


# ── Low-level frame API ──────────────────────────────────────
def batch_encode(audio, spf: int) -> list:
    """
    Encode a float32 numpy array to a list of hex strings.

    Parameters
    ----------
    audio : np.ndarray (float32, 1-D), length = n_frames * spf
    spf   : samples per frame

    Returns
    -------
    list of n_frames uppercase hex strings (lossless IEEE-754)
    """
    from wavcore._codec.codec import batch_encode as _be
    return _be(audio, spf)


def batch_decode(hex_list: list, spf: int):
    """
    Decode a list of hex strings to a contiguous float32 array.

    Parameters
    ----------
    hex_list : list of hex strings (from batch_encode)
    spf      : samples per frame

    Returns
    -------
    np.ndarray (float32, 1-D), length = len(hex_list) * spf
    """
    from wavcore._codec.codec import batch_decode as _bd
    return _bd(hex_list, spf)


def compute_frame_crc(version, frame_id, timestamp_ms,
                      sample_rate, channels, bit_depth,
                      payload: bytes) -> int:
    """
    Compute CRC-32 for one audio frame.
    Identical result to: zlib.crc32(struct.pack(">BIdIBBI", ...) + payload)
    """
    from wavcore._codec.codec import compute_frame_crc as _crc
    return _crc(version, frame_id, timestamp_ms,
                sample_rate, channels, bit_depth, payload)


__all__ = [
    "record", "decode", "engine_info",
    "batch_encode", "batch_decode", "compute_frame_crc",
    "__version__", "__author__",
]
