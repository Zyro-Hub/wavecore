# Publishing WavCore to PyPI

> **Step-by-step guide to publishing the `wavcore` package on PyPI**  
> so anyone can install it with `pip install wavcore`.

---

## Prerequisites

1. A [PyPI account](https://pypi.org/account/register/) — free
2. A [TestPyPI account](https://test.pypi.org/account/register/) — free (for testing)
3. Python 3.9+ and pip installed
4. The wavcore source directory (this folder)

---

## Step 1 — Install Build Tools

```bash
pip install build twine
```

- **`build`** — creates the distribution packages (`.whl` and `.tar.gz`)
- **`twine`** — uploads packages to PyPI securely

---

## Step 2 — Set Up PyPI API Token

**Never use your PyPI password directly.** Use an API token instead.

1. Log in to [pypi.org](https://pypi.org)
2. Go to **Account Settings → API Tokens**
3. Click **Add API token**
4. Name it `wavcore-upload`, scope: **Entire account**
5. Copy the token (starts with `pypi-...`)

Save it in `~/.pypirc`:

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

Open `pyproject.toml` and fill in your real details:

```toml
[project]
name        = "wavcore"           # must be unique on PyPI
version     = "1.0.0"
description = "Ultra-fast lossless voice codec — real-time recording, VTXT serialization, C engine"
readme      = "README.md"
license     = { text = "MIT" }
requires-python = ">=3.9"

authors = [
    { name = "Your Name", email = "you@example.com" }
]

keywords = ["audio", "codec", "voice", "recording", "lossless", "real-time", "vtxt"]

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
Homepage    = "https://github.com/YOUR_USERNAME/wavcore"
Source      = "https://github.com/YOUR_USERNAME/wavcore"
Issues      = "https://github.com/YOUR_USERNAME/wavcore/issues"
```

> **Important:** The `name = "wavcore"` must be unique on PyPI. Check at  
> `https://pypi.org/project/wavcore/` — if taken, choose another name.

---

## Step 4 — Add `MANIFEST.in`

This tells the build system which non-Python files to include in the source distribution:

Create file `MANIFEST.in` in the root directory:

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

Before publishing, do a final local install test:

```bash
# Uninstall any existing version
pip uninstall wavcore -y

# Install fresh from source
pip install -e .

# Verify
python -c "import wavcore; print(wavcore.__version__, wavcore.engine_info())"
```

Expected output:
```
1.0.0 C engine [cffi / MSVC 64-bit .pyd]  — ultra-fast
```

---

## Step 6 — Build the Distribution

```bash
python -m build
```

This creates a `dist/` folder:

```
dist/
├── wavcore-1.0.0.tar.gz           ← source distribution (sdist)
└── wavcore-1.0.0-cp312-...whl     ← wheel (pre-compiled, platform-specific)
```

> **Note about C extensions and wheels:**  
> The `.whl` file is platform-specific (e.g., `cp312-win_amd64`).  
> Users on other platforms (Linux, macOS) will receive the `.tar.gz`  
> and compile the C engine during their `pip install` — this is automatic.

---

## Step 7 — Publish to TestPyPI First (Recommended)

Always test on TestPyPI before the real PyPI:

```bash
twine upload --repository testpypi dist/*
```

Then test the install from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ wavcore
```

Verify:
```python
import wavcore
print(wavcore.__version__)
print(wavcore.engine_info())
```

---

## Step 8 — Publish to PyPI

Once TestPyPI looks good, upload to the real PyPI:

```bash
twine upload dist/*
```

Enter your token when prompted (or it reads from `~/.pypirc`).

**Done!** Your package is now live at `https://pypi.org/project/wavcore/`.

Anyone in the world can now install it:

```bash
pip install wavcore
```

---

## Step 9 — Update `app.py` Import

Verify the app still works after publishing:

```python
# Install from PyPI (not editable)
pip install wavcore

# Run
python app.py
```

---

## Versioning for Updates

Every time you update the package, bump the version in `pyproject.toml`:

```
1.0.0  → Initial release
1.0.1  → Bug fix
1.1.0  → New feature (backward compatible)
2.0.0  → Breaking change
```

Then rebuild and re-upload:

```bash
python -m build
twine upload dist/*
```

---

## Building Wheels for Multiple Platforms

A single `python -m build` only builds for your current OS/Python.  
To distribute pre-compiled wheels for all platforms, use **GitHub Actions** with `cibuildwheel`:

### `.github/workflows/publish.yml`

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"   # triggers on git tag like v1.0.0

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

This auto-publishes on every `git tag v*` with wheels for:
- Windows (cp39, cp310, cp311, cp312)
- Linux (cp39, cp310, cp311, cp312)
- macOS (cp39, cp310, cp311, cp312)

---

## Complete Publishing Checklist

```
□  pyproject.toml — fill in your name, email, GitHub URLs
□  README.md       — looks good on PyPI (check with twine check)
□  MANIFEST.in     — includes codec_core.c so Linux/macOS can compile
□  Version bumped  — pyproject.toml [project] version = "X.Y.Z"
□  pip install -e . runs without errors
□  python app.py    runs successfully (records + decodes)
□  python -m build  completes without errors
□  twine upload --repository testpypi dist/*  (test)
□  pip install --index-url testpypi wavcore    (verify)
□  twine upload dist/*                         (real PyPI)
□  pip install wavcore                         (final verify)
```

---

## Useful Commands Reference

```bash
# Check your package for issues before upload
twine check dist/*

# List what's in the distribution
tar tzf dist/wavcore-1.0.0.tar.gz | head -30

# Uninstall and test clean install
pip uninstall wavcore -y
pip install dist/wavcore-1.0.0-*.whl

# See what version is on PyPI
pip index versions wavcore

# Force upgrade from PyPI
pip install --upgrade --force-reinstall wavcore
```

---

## Why C Extensions on PyPI Are Safe

When `pip install wavcore` is run:

1. pip downloads `wavcore-1.0.0.tar.gz` (source distribution)
2. pip installs build dependencies: `setuptools, cffi, wheel`
3. `setup.py cffi_modules` triggers: cffi reads `_build_ffi.py`
4. cffi finds the system C compiler:
   - **Windows:** MSVC (installed with Python via Visual C++ redistributable)
   - **Linux:** GCC (standard on most systems)
   - **macOS:** Clang (via Xcode command line tools)
5. `codec_core.c` is compiled to `_codec_core.cp312-win_amd64.pyd`
6. `wavcore` is installed with the C engine ready

The user never touches a compiler — it's all automatic.

---

## Troubleshooting PyPI Upload

### "Invalid package name"
- Package name must be `[A-Za-z0-9_-]` only, global uniqueness on PyPI

### "File already exists"
- You cannot re-upload the same version. Bump the version in `pyproject.toml`.

### "Compilation failed on user's machine"
- Check `MANIFEST.in` includes `codec_core.c`
- Test on a fresh VM: `pip install wavcore` from TestPyPI

### "twine: command not found"
```bash
pip install twine
```
