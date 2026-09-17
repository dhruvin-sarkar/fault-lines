import pytest
from PIL import Image

from pipeline import site_captures as sc


def test_accept_key_matches_rfc_6455_example():
    assert sc.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


@pytest.mark.parametrize("size", [0, 5, 125, 126, 1000, 70000])
def test_frame_round_trip(size):
    payload = bytes(i % 251 for i in range(size))
    frame = sc.encode_frame(payload, mask=b"\x01\x02\x03\x04")
    final, opcode, decoded, used = sc.parse_frame(frame + b"extra")
    assert final and opcode == 1
    assert decoded == payload
    assert used == len(frame)


def test_parse_frame_waits_for_complete_frame():
    frame = sc.encode_frame(b"x" * 300, mask=b"abcd")
    assert sc.parse_frame(frame[:1]) is None
    assert sc.parse_frame(frame[:3]) is None
    assert sc.parse_frame(frame[:-1]) is None


def test_parse_unmasked_server_frame():
    frame = bytes([0x81, 5]) + b"hello"
    assert sc.parse_frame(frame) == (True, 1, b"hello", 7)


def test_fit_width_keeps_aspect_ratio():
    image = Image.new("RGB", (1760, 1000))
    assert sc.fit_width(image, 880).size == (880, 500)


def test_collapse_frames_merges_identical_runs():
    black = Image.new("RGB", (4, 4))
    white = Image.new("RGB", (4, 4), (255, 255, 255))
    frames, durations = sc.collapse_frames([black, black.copy(), white, black], [100, 200, 300, 400])
    assert len(frames) == 3
    assert durations == [300, 300, 400]


def test_save_gif_writes_a_looping_animation(tmp_path):
    frames = [Image.new("RGB", (8, 8), (i * 60, 0, 0)) for i in range(3)]
    path = tmp_path / "clip.gif"
    sc.save_gif(path, frames, [100, 100, 500])
    with Image.open(path) as gif:
        assert gif.n_frames == 3
        assert gif.info["loop"] == 0


def test_strip_layout_spreads_screens_evenly():
    lefts = sc.strip_layout(3, 1760, 500, 64)
    assert lefts[0] == 64
    assert lefts[-1] + 500 == 1760 - 64
    assert lefts[1] - lefts[0] == lefts[2] - lefts[1]
    assert sc.strip_layout(1, 1760, 500, 64) == [630]
    with pytest.raises(ValueError):
        sc.strip_layout(4, 1000, 500, 64)


def test_rounded_blacks_out_corners():
    image = sc.rounded(Image.new("RGB", (100, 100), (255, 255, 255)), 20)
    assert image.getpixel((0, 0)) == sc.FIELD
    assert image.getpixel((50, 50)) == (255, 255, 255)
