import pytest
from PIL import Image

import optimize
from optimize import compose_square, fill_mask_holes, harden_mask, make_square_on_white


def _img_with_centered_box(canvas=400, box=100, color=(0, 0, 0)):
    """RGBA-картинка с непрозрачным прямоугольником в центре + маска объекта."""
    img = Image.new("RGBA", (canvas, canvas), (128, 128, 128, 255))
    mask = Image.new("L", (canvas, canvas), 0)
    x0 = (canvas - box) // 2
    for x in range(x0, x0 + box):
        for y in range(x0, x0 + box):
            img.putpixel((x, y), (*color, 255))
            mask.putpixel((x, y), 255)
    return img, mask


def test_result_is_square_of_requested_size():
    img, mask = _img_with_centered_box()
    out = make_square_on_white(img, mask, size=1500, padding=0.08)
    assert out.size == (1500, 1500)
    assert out.mode == "RGB"


def test_corners_are_pure_white():
    img, mask = _img_with_centered_box()
    out = make_square_on_white(img, mask, size=1500, padding=0.08)
    assert out.getpixel((0, 0)) == (255, 255, 255)
    assert out.getpixel((1499, 1499)) == (255, 255, 255)


def test_object_is_centered():
    # Объект-прямоугольник смещён в левый верхний угол, но в результате центрирован.
    # Проверяем compose_square (натуральный масштаб, без ресайз-артефактов).
    canvas = 400
    img = Image.new("RGBA", (canvas, canvas), (200, 200, 200, 255))
    mask = Image.new("L", (canvas, canvas), 0)
    for x in range(20, 120):
        for y in range(20, 120):
            img.putpixel((x, y), (0, 0, 0, 255))
            mask.putpixel((x, y), 255)
    out = compose_square(img, mask, padding=0.10)
    # Поля слева и справа от чёрного объекта равны (симметрия по центру).
    row = out.height // 2
    left = next(i for i in range(out.width) if out.getpixel((i, row)) != (255, 255, 255))
    right = next(
        i for i in range(out.width - 1, -1, -1) if out.getpixel((i, row)) != (255, 255, 255)
    )
    assert abs(left - (out.width - 1 - right)) <= 1


def test_padding_controls_object_fraction():
    # При padding=0.1 объект (квадратный) занимает ~80% стороны квадрата.
    # Проверяем compose_square в натуральном масштабе: 200 / 0.8 = 250 → объект 200/250.
    img, mask = _img_with_centered_box(canvas=400, box=200)
    out = compose_square(img, mask, padding=0.10)
    row = out.height // 2
    non_white = [i for i in range(out.width) if out.getpixel((i, row)) != (255, 255, 255)]
    width = non_white[-1] - non_white[0] + 1
    fraction = width / out.width
    assert abs(fraction - 0.8) <= 0.01  # объект занимает ~80% стороны


def test_background_inside_bbox_is_preserved_not_whitened():
    # Фон НЕ вырезается: исходные пиксели внутри bbox объекта сохраняются.
    # Маска неточная (уже самого объекта) — но обрезка идёт по bbox исходника,
    # поэтому часть объекта/фона рядом не теряется и не белится.
    canvas = 400
    bg = (130, 125, 115)
    img = Image.new("RGBA", (canvas, canvas), (*bg, 255))  # цветной фон
    mask = Image.new("L", (canvas, canvas), 0)
    # Объект — красный квадрат 150..250; маска покрывает только его центр 180..220.
    for x in range(150, 250):
        for y in range(150, 250):
            img.putpixel((x, y), (200, 30, 30, 255))
    for x in range(180, 220):
        for y in range(180, 220):
            mask.putpixel((x, y), 255)
    out = compose_square(img, mask, padding=0.08)
    # Внутри bbox (по маске 180..220) красные пиксели объекта сохранены — не побелены.
    assert out.getpixel((out.width // 2, out.height // 2)) == (200, 30, 30)
    # Углы квадрата — белая рамка-padding (вне исходного кропа).
    assert out.getpixel((0, 0)) == (255, 255, 255)


def test_compose_square_does_not_whiten_pixels_outside_mask_inside_bbox():
    # Ключевая гарантия фикса: пиксель, который НЕ в маске, но попадает в bbox,
    # остаётся оригинальным (раньше он белился наложением на белый фон).
    canvas = 200
    img = Image.new("RGB", (canvas, canvas), (40, 90, 160))  # синий «фон-товар»
    mask = Image.new("L", (canvas, canvas), 0)
    # L-образная маска: объект в углу bbox, противоположный угол bbox — вне маски.
    for x in range(50, 150):
        mask.putpixel((x, 50), 255)
    for y in range(50, 150):
        mask.putpixel((50, y), 255)
    # bbox маски = (50,50)-(150,150). Точка (149,149) внутри bbox, но вне маски.
    out = compose_square(img, mask, padding=0.0)
    # Эта точка должна сохранить исходный синий, а не стать белой.
    assert (149 - 50, 149 - 50) and out.getpixel((149 - 50, 149 - 50)) == (40, 90, 160)


def test_harden_mask_binarizes_around_threshold():
    mask = Image.new("L", (4, 1), 0)
    for i, v in enumerate([0, 127, 128, 255]):
        mask.putpixel((i, 0), v)
    hardened = harden_mask(mask, threshold=128)
    assert [hardened.getpixel((i, 0)) for i in range(4)] == [0, 0, 255, 255]


def test_fill_mask_holes_fills_interior_hole():
    # Сплошной квадрат объекта с дырой в центре → дыра заполняется.
    mask = Image.new("L", (20, 20), 0)
    for x in range(4, 16):
        for y in range(4, 16):
            mask.putpixel((x, y), 255)
    for x in range(9, 11):  # дыра в центре
        for y in range(9, 11):
            mask.putpixel((x, y), 0)
    filled = fill_mask_holes(mask)
    assert filled.getpixel((9, 9)) == 255   # дыра залита
    assert filled.getpixel((10, 10)) == 255
    assert filled.getpixel((0, 0)) == 0     # внешний фон не тронут


def test_fill_mask_holes_keeps_background_connected_to_edge():
    # Залив (бухта), открытый к краю, остаётся фоном — заливаются только замкнутые дыры.
    mask = Image.new("L", (20, 20), 0)
    for x in range(4, 16):
        for y in range(4, 16):
            mask.putpixel((x, y), 255)
    for x in range(8, 12):  # прорезь от центра до нижнего края
        for y in range(8, 20):
            mask.putpixel((x, y), 0)
    filled = fill_mask_holes(mask)
    assert filled.getpixel((10, 18)) == 0  # связан с краем — остаётся фоном


def test_harden_mask_removes_semitransparent_halo():
    # Полупрозрачная кайма (alpha=80) превращается в фон при пороге 128.
    mask = Image.new("L", (3, 1), 0)
    mask.putpixel((0, 0), 255)  # объект
    mask.putpixel((1, 0), 80)   # кайма/тень
    mask.putpixel((2, 0), 0)    # фон
    hardened = harden_mask(mask)
    assert hardened.getpixel((1, 0)) == 0


def test_empty_mask_fallback_does_not_crash():
    img = Image.new("RGBA", (300, 200), (50, 50, 50, 255))
    mask = Image.new("L", (300, 200), 0)  # пустая маска
    out = make_square_on_white(img, mask, size=1200, padding=0.08)
    assert out.size == (1200, 1200)
    assert out.mode == "RGB"


def test_process_image_saves_output(tmp_path, monkeypatch):
    # Готовим входной файл.
    src = tmp_path / "in.png"
    img = Image.new("RGBA", (300, 200), (10, 10, 10, 255))
    img.save(src)

    # Подменяем сегментацию: вся картинка — объект.
    monkeypatch.setattr(optimize, "segment", lambda im, sess: Image.new("L", im.size, 255))

    out_dir = tmp_path / "out"
    result = optimize.process_image(
        src, out_dir, session=None, size=1200, padding=0.08, fmt="webp"
    )

    assert result is not None
    assert result.exists()
    assert result.suffix == ".webp"
    with Image.open(result) as saved:
        assert saved.size == (1200, 1200)


def test_process_image_raises_for_non_image(tmp_path):
    # process_image не глотает ошибки чтения: битый файл бросает исключение.
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image")
    out_dir = tmp_path / "out"
    with pytest.raises(Exception):
        optimize.process_image(
            bad, out_dir, session=None, size=1200, padding=0.08, fmt="webp"
        )


def test_main_rejects_size_out_of_range():
    with pytest.raises(SystemExit) as e:
        optimize.main(["--size", "999"])
    assert e.value.code == 2


def test_main_rejects_size_above_max():
    with pytest.raises(SystemExit) as e:
        optimize.main(["--size", "2000"])
    assert e.value.code == 2
