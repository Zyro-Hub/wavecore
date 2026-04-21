"""
setup.py — cffi C extension build for wavcore._codec._codec_core
=================================================================
Only needed for the C extension compilation step.
All project metadata lives in pyproject.toml.

Install (development / editable):
  pip install -e .

Install (production):
  pip install .
  pip install wavcore          # once published to PyPI
=================================================================
"""

from setuptools import setup

setup(
    cffi_modules=["wavcore/_codec/_build_ffi.py:ffi"],
)
