"""Tests for ripple service — country code resolution and evaluation logic."""

from __future__ import annotations

import pytest

from app.services.ripple_service import _codes_from_text


class TestCountryCodeResolution:
    """Verify location text → ISO-3 code fallback."""

    def test_russia_from_title(self):
        codes = _codes_from_text("M 5.8 earthquake — 240 km ESE of Petropavlovsk-Kamchatsky, Russia")
        assert "RUS" in codes

    def test_ukraine_conflict(self):
        codes = _codes_from_text("Russia launches airstrikes on Ukraine capital Kyiv")
        assert "UKR" in codes

    def test_iran_strait_hormuz(self):
        codes = _codes_from_text("Iran tensions escalate in Strait of Hormuz")
        assert "IRN" in codes

    def test_turkey_earthquake(self):
        codes = _codes_from_text("M 7.8 earthquake strikes Türkiye near Syrian border")
        # Both Turkey (Türkiye) and Syria should be found
        assert "TUR" in codes or "SYR" in codes

    def test_no_match_returns_empty(self):
        codes = _codes_from_text("Market rally as interest rates fall")
        assert codes == []

    def test_multiple_countries_conflict(self):
        codes = _codes_from_text("Ukraine-Russia war: Egypt faces wheat shortage as supply routes disrupted")
        # Should find both UKR (or RUS) and EGY
        assert "EGY" in codes
        assert "UKR" in codes or "RUS" in codes

    def test_saudi_arabia_alias(self):
        codes = _codes_from_text("Saudi Arabia cuts oil production amid Gulf tensions")
        assert "SAU" in codes

    def test_uae_alias(self):
        codes = _codes_from_text("UAE port disruption affects LPG shipments")
        assert "ARE" in codes

    def test_usa_alias(self):
        codes = _codes_from_text("United States imposes new sanctions on Iran")
        assert "USA" in codes

    def test_gaza_conflict(self):
        codes = _codes_from_text("Gaza faces severe medicine shortage amid conflict")
        assert "PSE" in codes
