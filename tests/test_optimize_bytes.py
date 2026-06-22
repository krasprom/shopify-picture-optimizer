import io
from PIL import Image
import optimize


def _img_with_box(canvas=(400, 300), box=(120, 90, 280, 210), color=(200, 30, 30)):
    img = Image.new("RGB", canvas, (123, 123, 123))
    mask = Image.new("L", canvas, 0)
    for x in range(box[0], box[2]):
        for y in range(box[1], box[3]):
            img.putpixel((x, y), color)
            mask.putpixel((x, y), 255)
    return img, mask


def test_make_square_on_white_is_square_and_white_corners():
    img, mask = _img_with_box()
    out = optimize.make_square_on_white(img, mask, 1500, 0.08)
    assert out.size == (1500, 1500)
    rgb = out.convert("RGB")
    assert rgb.getpixel((0, 0)) == (255, 255, 255)
    assert rgb.getpixel((1499, 1499)) == (255, 255, 255)


def test_optimize_bytes_square_jpg_via_fake_segment(monkeypatch):
    img, mask = _img_with_box()
    monkeypatch.setattr(optimize, "segment", lambda image, session: mask.resize(image.size))
    src = io.BytesIO(); img.save(src, format="PNG")
    out, detected = optimize.optimize_bytes(src.getvalue(), 1500, 0.08, "jpg", session=None)
    result = Image.open(io.BytesIO(out))
    assert result.format == "JPEG"
    assert result.size == (1500, 1500)
    assert detected is True
    assert result.convert("RGB").getpixel((0, 0)) == (255, 255, 255)
