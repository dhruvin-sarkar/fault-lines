import numpy as np
import pytest

from pipeline.qr_code import (
    choose_version,
    data_capacity,
    data_codewords,
    encode,
    format_bits,
    gf_multiply,
    reed_solomon_remainder,
    version_bits,
)


def test_reed_solomon_matches_the_worked_hello_world_example():
    data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
    assert reed_solomon_remainder(data, 10) == [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]


def test_field_multiplication_wraps_by_the_primitive_polynomial():
    assert gf_multiply(0, 7) == 0
    assert gf_multiply(1, 200) == 200
    assert gf_multiply(128, 2) == 0x1D


def test_format_and_version_information_match_the_standard_tables():
    assert format(format_bits("M", 0), "015b") == "101010000010010"
    assert format(format_bits("L", 0), "015b") == "111011111000100"
    assert format(format_bits("H", 7), "015b") == "000100000111011"
    assert format(version_bits(7), "018b") == "000111110010010100"


def test_version_is_the_smallest_that_holds_the_payload():
    assert data_capacity(1, "M") == 16
    assert choose_version(14, "M") == 1
    assert choose_version(15, "M") == 2
    with pytest.raises(ValueError):
        choose_version(1000, "H")


def test_data_codewords_carry_mode_length_and_alternating_padding():
    words = data_codewords(b"A", 1, "M")
    assert len(words) == 16
    assert words[:3] == [0x40, 0x14, 0x10]
    assert words[3:7] == [0xEC, 0x11, 0xEC, 0x11]


def test_symbol_has_finder_patterns_timing_lines_and_the_dark_module():
    modules = encode("https://dhruvin-sarkar.github.io/fault-lines/", "M")
    size = len(modules)
    assert modules.shape == (size, size) and (size - 17) % 4 == 0
    finder = np.array([[r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4) for c in range(7)]
                       for r in range(7)])
    assert np.array_equal(modules[:7, :7], finder)
    assert np.array_equal(modules[:7, -7:], finder)
    assert np.array_equal(modules[-7:, :7], finder)
    assert modules[6, 8:size - 8].tolist() == [i % 2 == 0 for i in range(8, size - 8)]
    assert modules[8:size - 8, 6].tolist() == [i % 2 == 0 for i in range(8, size - 8)]
    assert modules[size - 8, 8]


def test_both_copies_of_the_format_information_agree():
    modules = encode("HELLO", "Q")
    size = len(modules)
    first = [modules[i, 8] for i in range(6)] + [modules[7, 8], modules[8, 8], modules[8, 7]]
    first += [modules[8, 14 - i] for i in range(9, 15)]
    second = [modules[8, size - 1 - i] for i in range(8)] + [modules[size - 15 + i, 8] for i in range(8, 15)]
    assert first == second
    value = sum(int(bit) << i for i, bit in enumerate(first))
    assert value in {format_bits("Q", mask) for mask in range(8)}
