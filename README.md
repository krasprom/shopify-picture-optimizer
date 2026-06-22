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

## Tests

```bash
python3 -m pytest tests/ -v
```

## Project structure

```
picture-optimizer/
├── optimize.py          # CLI and processing pipeline
├── requirements.txt     # dependencies
├── tests/               # unit tests for geometry and processing
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
