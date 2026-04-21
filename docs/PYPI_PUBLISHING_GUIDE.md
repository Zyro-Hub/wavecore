# Publishing WavCore to PyPI

> **Step-by-step guide to publishing the `wavcore` package on PyPI**
> so anyone can install it with `pip install wavcore`.

---

## Prerequisites

1. A [PyPI account](https://pypi.org/account/register/) — free
2. A [TestPyPI account](https://test.pypi.org/account/register/) — free (for testing)
3. Python 3.9+ and pip installed
4. The wavcore source directory

---

## Step 1 — Install Build Tools

```bash
pip install build twine
```

- **`build`** — creates the distribution packages (`.whl` and `.tar.gz`)
- **`twine`** — uploads packages to PyPI securely

---

## Step 2 — Set Up PyPI API Token

**Never use your PyPI password directly.** Use an API token.

1. Log in to [pypi.org](https://pypi.org)
2. Go to **Account Settings → API Tokens**
3. Click **Add API token** → name it `wavcore-upload`, scope: Entire account
4. Copy the token (starts with `pypi-...`)

Save to `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TEST_TOKEN_HERE
repository = https://test.pypi.org/legacy/
```

> **Security:** Never commit `.pypirc` to Git. Add it to `.gitignore`.

---

## Step 3 — Verify `pyproject.toml`

```toml
[project]
name        = "wavcore"
version     = "2.0.0"
description = "Ultra-fast lossless voice codec — real-time recording, live VTXT writing, C engine."
readme      = "README.md"
license     = { text = "MIT" }
requires-python = ">=3.9"

authors = [
    { name = "Prashant Pandey", email = "technical121@gmail.com" }
]

keywords = ["audio", "codec", "voice", "recording", "lossless", "real-time", "vtxt", "live"]

classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: C",
    "Topic :: Multimedia :: Sound/Audio",
    "Topic :: Multimedia :: Sound/Audio :: Capture/Recording",
    "Topic :: Multimedia :: Sound/Audio :: Conversion",
]

dependencies = [
    "numpy>=1.21.0",
    "sounddevice>=0.4.5",
    "cffi>=1.15.0",
]

[project.urls]
Homepage = "https://github.com/Zyro-Hub/wavecore"
Source   = "https://github.com/Zyro-Hub/wavecore"
Issues   = "https://github.com/Zyro-Hub/wavecore/issues"
```

---

## Step 4 — Add `MANIFEST.in`

```
include README.md
include pyproject.toml
include setup.py
recursive-include wavcore *.py *.c *.h
recursive-include docs *.md
recursive-exclude * __pycache__
recursive-exclude * *.pyd
recursive-exclude * *.so
recursive-exclude * *.pyc
```

---

## Step 5 — Test Locally First

```bash
pip uninstall wavcore -y
pip install -e .
python -c "import wavcore; print(wavcore.__version__, wavcore.engine_info())"
```

Expected:
```
2.0.0 C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast
```

Also verify both recording modes work:

```python
import wavcore

# Test Normal mode
print("Testing normal mode...")
wavcore.record("test.vtxt", "test_orig.wav", duration=2)
wavcore.decode("test.vtxt", "test_recon.wav", play=False)

# Test Live mode import
print("Testing live_record import...")
from wavcore.recorder import live_record_to_vtxt
print("live_record_to_vtxt:", live_record_to_vtxt.__doc__[:40])

print("All OK")
```

---

## Step 6 — Build the Distribution

```bash
python -m build
```

Creates:
```
dist/
├── wavcore-2.0.0.tar.gz           ← source distribution
└── wavcore-2.0.0-cp312-...whl     ← wheel (platform-specific)
```

---

## Step 7 — Check the Package

```bash
twine check dist/*
```

Must show:
```
PASSED wavcore-2.0.0.tar.gz
PASSED wavcore-2.0.0-cp312-...whl
```

---

## Step 8 — Publish to TestPyPI First

```bash
twine upload --repository testpypi dist/*
```

Test install:
```bash
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ wavcore
```

Verify:
```python
import wavcore
print(wavcore.__version__)      # 2.0.0
print(wavcore.engine_info())
print(dir(wavcore))             # should include 'live_record'
```

---

## Step 9 — Publish to PyPI

```bash
twine upload dist/*
```

**Done!** Live at `https://pypi.org/project/wavcore/2.0.0/`

Anyone can now install:
```bash
pip install wavcore
```

---

## Versioning History

| Version | Changes |
|---|---|
| `1.0.0` | Initial release — `record()`, `decode()`, C engine |
| `1.0.1` | Bug fixes |
| `1.0.2` | PyPI metadata improvements |
| **`2.0.0`** | **`live_record()` — real-time per-frame .vtxt writing; mode selection in app.py** |

To release a future update:

1. Bump `version` in `pyproject.toml` and `__init__.py`
2. Update `README.md` "What's New" section
3. `python -m build`
4. `twine upload dist/*`

---

## Building Wheels for Multiple Platforms

Use **GitHub Actions** with `cibuildwheel` to auto-publish on every git tag:

### `.github/workflows/publish.yml`

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  build_wheels:
    name: Build ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - name: Build wheels
        uses: pypa/cibuildwheel@v2.19
        env:
          CIBW_BUILD: "cp39-* cp310-* cp311-* cp312-*"
      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: ./wheelhouse/*.whl

  upload_pypi:
    needs: build_wheels
    runs-on: ubuntu-latest
    environment: pypi
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: wheels-*
          merge-multiple: true
          path: dist
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

This builds wheels for Windows, Linux, macOS × Python 3.9–3.12 automatically.

---

## Complete Publishing Checklist

```
□  pyproject.toml — version = "2.0.0", correct name/email/URLs
□  __init__.py    — __version__ = "2.0.0"
□  README.md      — "What's New" section updated
□  pip install -e .  runs without errors
□  wavcore.live_record exists in dir(wavcore)
□  python app.py   shows mode selection menu
□  python -m build  completes without errors
□  twine check dist/*  shows PASSED
□  twine upload --repository testpypi dist/*
□  pip install from testpypi → verify
□  twine upload dist/*  (real PyPI)
□  pip install wavcore → final verify
```

---

## Useful Commands Reference

```bash
# Check package before upload
twine check dist/*

# List contents of source distribution
tar tzf dist/wavcore-2.0.0.tar.gz | head -30

# Clean reinstall test
pip uninstall wavcore -y
pip install dist/wavcore-2.0.0-*.whl

# Check what's on PyPI
pip index versions wavcore

# Force upgrade from PyPI
pip install --upgrade --force-reinstall wavcore
```

---

## Troubleshooting PyPI Upload

### "File already exists"
Cannot re-upload the same version. Bump the version in `pyproject.toml`.

### "Invalid package name"
Package name must be `[A-Za-z0-9_-]` only, globally unique on PyPI.

### "Compilation failed on user's machine"
Check `MANIFEST.in` includes `codec_core.c`. Test on a fresh VM.

### "twine: command not found"
```bash
pip install twine
```
