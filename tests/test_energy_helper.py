"""Tests for produzre.orchestrate.energy.resolve_section_energy."""

import pytest

from produzre.orchestrate.energy import resolve_section_energy


class TestAutoDetectFromSectionType:
    def test_verse(self):
        assert resolve_section_energy(None, "verse") == 0.3

    def test_chorus(self):
        assert resolve_section_energy(None, "chorus") == 0.9

    def test_bridge(self):
        assert resolve_section_energy(None, "bridge") == 0.6

    def test_solo(self):
        assert resolve_section_energy(None, "solo") == 0.7

    def test_unknown_type_defaults(self):
        assert resolve_section_energy(None, "interlude") == 0.5

    def test_case_insensitive(self):
        assert resolve_section_energy(None, "CHORUS") == 0.9
        assert resolve_section_energy(None, "Verse") == 0.3


class TestNamedStrings:
    def test_low(self):
        assert resolve_section_energy("low", "verse") == 0.3

    def test_mid(self):
        assert resolve_section_energy("mid", "verse") == 0.6

    def test_medium(self):
        assert resolve_section_energy("medium", "verse") == 0.6

    def test_high(self):
        assert resolve_section_energy("high", "verse") == 0.9

    def test_case_insensitive(self):
        assert resolve_section_energy("HIGH", "verse") == 0.9

    def test_whitespace_stripped(self):
        assert resolve_section_energy("  low  ", "verse") == 0.3


class TestNumericValues:
    def test_float_in_range(self):
        assert resolve_section_energy(0.42, "verse") == pytest.approx(0.42)

    def test_int_value(self):
        assert resolve_section_energy(1, "verse") == 1.0

    def test_clamped_high(self):
        assert resolve_section_energy(1.5, "verse") == 1.0

    def test_clamped_low(self):
        assert resolve_section_energy(-0.3, "verse") == 0.0

    def test_numeric_string(self):
        assert resolve_section_energy("0.75", "verse") == pytest.approx(0.75)

    def test_numeric_string_clamped(self):
        assert resolve_section_energy("2.0", "verse") == 1.0


class TestEdgeCases:
    def test_garbage_string(self):
        assert resolve_section_energy("garbage", "verse") == 0.5

    def test_empty_string(self):
        assert resolve_section_energy("", "verse") == 0.5
