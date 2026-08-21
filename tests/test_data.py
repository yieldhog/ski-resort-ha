"""Tests for the bundled OpenSkiMap index / crosswalk access."""

from __future__ import annotations

from custom_components.ski_resort import data


def test_search_finds_vail():
    results = data.search_areas("vail", country="United States", limit=5)
    assert results
    vail = results[0]
    assert vail["name"] == "Vail"
    assert vail["region"] == "Colorado"
    assert vail["lifts"] > 0


def test_search_no_match():
    assert data.search_areas("zzzznotarealresort") == []


def test_country_filter():
    res = data.search_areas("whistler")
    assert any(a["country"] == "Canada" for a in res)


def test_get_area_and_slug():
    vail = data.search_areas("vail", country="United States")[0]
    assert data.get_area(vail["id"])["name"] == "Vail"
    assert data.liftie_slug_for(vail["id"]) == "vail"
    assert data.get_area("no-such-id") is None


def test_countries_nonempty():
    countries = data.countries()
    assert "United States" in countries and "Canada" in countries
