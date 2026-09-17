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


def test_rounded_uses_the_given_ground():
    image = sc.rounded(Image.new("RGB", (100, 100), (255, 255, 255)), 20, sc.STRIP_FIELD)
    assert image.getpixel((0, 0)) == sc.STRIP_FIELD


def test_band_pads_and_rounds_outward():
    rect = {"left": 40.4, "top": 100.6, "right": 1224.2, "bottom": 699.3}
    assert sc.band(rect, 0, -16, 0) == [40, 116, 1225, 700]
    assert sc.band(rect, 24, 28, 20) == [16, 72, 1249, 720]


def test_stack_bands_crops_at_device_scale_and_stacks():
    image = Image.new("RGB", (40, 40), (10, 10, 10))
    image.paste((200, 0, 0), (0, 0, 40, 10))
    image.paste((0, 200, 0), (0, 30, 40, 40))
    stacked = sc.stack_bands(image, [[0, 0, 20, 5], [0, 15, 20, 20]], 2)
    assert stacked.size == (40, 20)
    assert stacked.getpixel((5, 5)) == (200, 0, 0)
    assert stacked.getpixel((5, 15)) == (0, 200, 0)


def test_save_gif_frames_decode_to_their_source(tmp_path):
    frames = []
    for i in range(4):
        frame = Image.new("RGB", (32, 24), (20, 20, 20))
        frame.paste((230, 90, 40), (i * 6, 4, i * 6 + 8, 12))
        frame.paste((60, 140, 230), (0, 18, 32, 24))
        frames.append(frame)
    path = tmp_path / "clip.gif"
    sc.save_gif(path, frames, [100, 100, 100, 900])
    with Image.open(path) as gif:
        assert gif.n_frames == 4
        for i, frame in enumerate(frames):
            gif.seek(i)
            assert sc.same_frame(gif.convert("RGB"), frame)


def test_save_gif_rejects_a_full_palette(tmp_path):
    with pytest.raises(ValueError):
        sc.save_gif(tmp_path / "clip.gif", [Image.new("RGB", (4, 4))], [100], colors=256)


def test_assemble_builds_gif_and_strip_from_plans(tmp_path):
    frames, out = tmp_path / "frames", tmp_path / "out"
    out.mkdir()
    clip, phones = frames / "clip", frames / "phones"
    clip.mkdir(parents=True)
    phones.mkdir()
    for i in range(3):
        Image.new("RGB", (80, 60), (i * 80, 20, 20)).save(clip / f"f{i}.png")
        Image.new("RGB", (39, 84), (240, 240, 240)).save(phones / f"p{i}.png")
    sc.write_plan(clip, {"output": "clip.gif", "scale": 2, "bands": [[0, 0, 40, 10], [0, 20, 40, 30]],
                         "frames": [["f0.png", 500], ["f1.png", 100], ["f2.png", 1500]]})
    sc.write_plan(phones, {"output": "strip.png", "shots": ["p0.png", "p1.png", "p2.png"]})
    written = sc.assemble(frames, out, ["clip", "phones"])
    assert [p.name for p in written] == ["clip.gif", "strip.png"]
    with Image.open(out / "clip.gif") as gif:
        assert gif.size == (sc.GIF_WIDTH, sc.GIF_WIDTH // 2)
        assert gif.n_frames == 3
        assert gif.info["loop"] == 0
    with Image.open(out / "strip.png") as strip:
        assert strip.width == sc.STRIP_WIDTH
        assert strip.getpixel((0, 0)) == sc.STRIP_FIELD
