# Picture Optimizer

Product photo optimizer for web shops. Takes images from a folder, isolates the
central object, places it on a pure white background, centers it, and produces a
square image of a fixed size.

## What it does

For every image in the input folder:

1. Isolates the object with a neural network (`rembg`).
2. Binarizes and fills holes in the mask — the background becomes pure white `#FFFFFF`.
3. Crops to the object, centers it, and adds an even padding margin.
4. Fits it into a square (1500×1500 by default) and saves it to `output/`.

Source files in `pictures/` are never modified.

## Installation

Requires Python 3.10+.

```bash
pip3 install -r requirements.txt
```

On first run, `rembg` automatically downloads the model (~170 MB).

## Usage

Process all images from `pictures/` into `output/` with default settings:

```bash
python3 optimize.py
```

Examples with parameters:

```bash
# Custom input/output folders
python3 optimize.py --input ./photos --output ./ready

# Size 1800, JPG format, 5% padding
python3 optimize.py --size 1800 --format jpg --padding 0.05

# Switch the segmentation model
python3 optimize.py --model u2net
```

## Parameters

| Parameter    | Default             | Description                                                              |
|--------------|---------------------|--------------------------------------------------------------------------|
| `--input`    | `pictures`          | Folder with source images.                                               |
| `--output`   | `output`            | Output folder (created automatically).                                   |
| `--size`     | `1500`              | Side of the output square, in pixels. Allowed range: `1200`–`1800`.      |
| `--padding`  | `0.08`              | White margin fraction on each side (0.08 = 8%).                          |
| `--format`   | `webp`              | Output format: `webp`, `jpg`, or `png`.                                  |
| `--model`    | `isnet-general-use` | `rembg` model. Alternative: `u2net`. `isnet` is more accurate on hard shots. |

Parameter help:

```bash
python3 optimize.py --help
```

## Supported formats

Input: `.webp`, `.jpg`, `.jpeg`, `.png` (extension case is ignored).
Output: `webp` / `jpg` / `png` (via the `--format` flag).

## Run as an HTTP service

The optimizer also runs as a long-lived FastAPI service (`app.py`) bound to
`127.0.0.1:8077`. It downloads a source image by URL, optimizes it in memory,
caches the result on disk, and returns the raw image bytes.

Start it locally:

```bash
uvicorn app:app --host 127.0.0.1 --port 8077 --workers 1
```

On first request the `rembg` model (~170 MB) is downloaded and loaded into
memory; it is reused for all subsequent requests.

### Endpoints

- `POST /optimize` — body `{"url": "<str>", "size": 1500, "padding": 0.08, "format": "jpg"}`
  (`size`/`padding`/`format` optional, defaults `1500 / 0.08 / jpg`). On success
  returns the **raw optimized image bytes** with `Content-Type: image/jpeg`
  (or `image/png` / `image/webp`), plus `X-Cache: hit|miss` and
  `X-Object-Detected: true|false|unknown` headers. Download error → HTTP 502
  JSON `{"error": "..."}`; optimization error → HTTP 500 JSON `{"error": "..."}`.
- `GET /health` — HTTP 200 JSON `{"status": "ok", "model": "<model name>"}`.

Configuration via environment variables: `OPTIMIZER_CACHE_DIR`
(default `/var/cache/shopify-optimizer`), `OPTIMIZER_MODEL`
(default `isnet-general-use`).

### Deploy as a systemd service

```bash
git clone https://github.com/krasprom/shopify-picture-optimizer.git /opt/shopify-optimizer
cd /opt/shopify-optimizer
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
mkdir -p /var/cache/shopify-optimizer
cp deploy/shopify-optimizer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now shopify-optimizer
curl -s http://127.0.0.1:8077/health
```

## Tests

```bash
python3 -m pytest tests/ -v
```

## Project structure

```
picture-optimizer/
├── optimize.py          # CLI and processing pipeline + in-memory optimize_bytes()
├── app.py               # FastAPI HTTP service (/optimize, /health)
├── deploy/              # systemd unit
├── requirements.txt     # dependencies
├── tests/               # unit tests for geometry, optimize_bytes and the service
├── pictures/            # input (not modified)
├── output/              # output (created on run)
└── docs/superpowers/    # spec and implementation plan
```

## Notes

- The square size is validated: a value outside the `1200`–`1800` range
  aborts the run with an argument error.
- If no object is found in a photo, the whole image is fitted into a white
  square (fallback); the run is not interrupted.
- A corrupt or unreadable file is skipped with a warning — the rest are still
  processed.
- The `rembg` model is loaded once per run and reused for all files in the batch.
