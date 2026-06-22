"""Оптимайзер картинок для веб-шопа: центрирование объекта на белом квадрате."""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from rembg import remove, new_session

WHITE = (255, 255, 255)
ALPHA_THRESHOLD = 10
# Порог бинаризации маски: пиксели с альфой ниже считаются фоном (→ чистый белый),
# выше — объектом. Убирает полупрозрачную кайму/тень от rembg на белом фоне.
MASK_HARDEN_THRESHOLD = 128

VALID_INPUT_SUFFIXES = {".webp", ".jpg", ".jpeg", ".png"}
SIZE_MIN, SIZE_MAX = 1200, 1800
# isnet точнее u2net на товарных фото с тёмными деталями у границы объекта.
DEFAULT_MODEL = "isnet-general-use"

_PIL_FORMAT = {"webp": "WEBP", "jpg": "JPEG", "jpeg": "JPEG", "png": "PNG"}


def _object_bbox(mask):
    """Bounding box непрозрачных пикселей маски. None, если объекта нет."""
    arr = np.array(mask)
    ys, xs = np.where(arr > ALPHA_THRESHOLD)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def compose_square(img, mask, padding):
    """Собирает центрированный белый квадрат с объектом в натуральном масштабе.

    Геометрия без ресайза — сторона квадрата определяется размером объекта,
    что позволяет проверять центрирование и padding с точностью до пикселя.

    img:     PIL.Image (RGBA/RGB) — исходное изображение.
    mask:    PIL.Image (L) того же размера; пиксели > ALPHA_THRESHOLD — объект.
    padding: доля поля с каждой стороны (0.08 = 8%).
    Возврат: PIL.Image (RGB), квадрат, белый фон, объект по центру.
    """
    rgb = img.convert("RGB")
    bbox = _object_bbox(mask)
    if bbox is None:
        # Fallback: объект не найден — вписываем картинку в квадрат целиком.
        cropped = rgb
    else:
        # Объект на чистом белом фоне: всё вне маски становится белым.
        white_bg = Image.new("RGB", rgb.size, WHITE)
        white_bg.paste(rgb, (0, 0), mask)
        cropped = white_bg.crop(bbox)

    longest = max(cropped.width, cropped.height)
    # Сторона квадрата так, чтобы объект занял (1 - 2*padding) от неё.
    square_side = max(1, round(longest / (1 - 2 * padding)))
    canvas = Image.new("RGB", (square_side, square_side), WHITE)
    offset = ((square_side - cropped.width) // 2, (square_side - cropped.height) // 2)
    canvas.paste(cropped, offset)
    return canvas


def make_square_on_white(img, mask, size, padding):
    """Центрирует объект на белом квадрате и масштабирует до size×size.

    Возврат: PIL.Image (RGB), size×size, белый фон, объект по центру.
    """
    return compose_square(img, mask, padding).resize((size, size), Image.LANCZOS)


def segment(img, session):
    """Возвращает L-маску объекта (альфа-канал результата rembg)."""
    cutout = remove(img.convert("RGBA"), session=session)
    return cutout.split()[-1]  # альфа-канал


def harden_mask(mask, threshold=MASK_HARDEN_THRESHOLD):
    """Бинаризует маску: альфа ниже threshold → 0 (фон), иначе → 255 (объект).

    Убирает полупрозрачную кайму (тени, мягкие края), из-за которой фон под
    объектом остаётся серым после композита на белом.
    """
    return mask.point(lambda a: 255 if a >= threshold else 0)


def fill_mask_holes(mask):
    """Заливает замкнутые «дыры» внутри объекта (ошибки сегментации внутри товара).

    Фон, связанный с краями кадра, не трогается — заполняются только области
    фона, полностью окружённые объектом. Вход/выход — бинарная L-маска.
    """
    binary = np.array(mask) > 0
    filled = ndimage.binary_fill_holes(binary)
    return Image.fromarray((filled * 255).astype(np.uint8), mode="L")


def process_image(path, out_dir, session, size, padding, fmt):
    """Обрабатывает один файл; возвращает путь результата или None при ошибке чтения."""
    try:
        with Image.open(path) as opened:
            img = opened.convert("RGBA")
    except Exception as exc:  # битый файл / не картинка
        print(f"  ! пропуск {path.name}: не удалось открыть ({exc})")
        return None

    mask = fill_mask_holes(harden_mask(segment(img, session)))
    square = make_square_on_white(img, mask, size=size, padding=padding)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}.{fmt}"
    square.save(out_path, _PIL_FORMAT[fmt])
    return out_path


def _size_arg(value):
    ivalue = int(value)
    if not (SIZE_MIN <= ivalue <= SIZE_MAX):
        raise argparse.ArgumentTypeError(
            f"размер должен быть в диапазоне {SIZE_MIN}..{SIZE_MAX}"
        )
    return ivalue


def main(argv=None):
    parser = argparse.ArgumentParser(description="Оптимайзер картинок для веб-шопа.")
    parser.add_argument("--input", default="pictures", help="папка с исходниками")
    parser.add_argument("--output", default="output", help="папка для результата")
    parser.add_argument(
        "--size", type=_size_arg, default=1500, help="сторона квадрата (1200..1800)"
    )
    parser.add_argument(
        "--padding", type=float, default=0.08, help="доля поля с каждой стороны"
    )
    parser.add_argument(
        "--format", dest="fmt", default="webp",
        choices=["webp", "jpg", "png"], help="формат вывода",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="модель rembg (напр. isnet-general-use, u2net)"
    )
    args = parser.parse_args(argv)

    in_dir, out_dir = Path(args.input), Path(args.output)
    if not in_dir.is_dir():
        print(f"Папка не найдена: {in_dir}")
        return 1

    files = sorted(
        p for p in in_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VALID_INPUT_SUFFIXES
    )
    if not files:
        print(f"В {in_dir} нет поддерживаемых картинок.")
        return 0

    session = new_session(args.model)
    print(
        f"Обработка {len(files)} файлов → {out_dir}/ "
        f"({args.size}px, {args.fmt}, модель {args.model})"
    )
    ok = 0
    for path in files:
        print(f"- {path.name}")
        if process_image(path, out_dir, session, args.size, args.padding, args.fmt):
            ok += 1
    print(f"Готово: {ok}/{len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
