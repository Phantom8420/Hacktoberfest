import io

from PIL import Image

from effort import gemma


def test_clean_strips_gps_and_shrinks():
    img = Image.new("RGB", (4000, 3000), "white")
    exif = Image.Exif()
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPSInfo: latitude
    exif[0x0112] = 1
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert Image.open(buf).getexif()  # the fixture really has EXIF

    out = Image.open(io.BytesIO(gemma.clean(buf.getvalue())))
    assert not out.getexif()
    assert max(out.size) == gemma.SIDE


def test_clean_applies_rotation():
    img = Image.new("RGB", (400, 200))
    exif = Image.Exif()
    exif[0x0112] = 6  # phone held upright: stored sideways
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(gemma.clean(buf.getvalue()))).size == (200, 400)
