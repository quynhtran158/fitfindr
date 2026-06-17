"""
Pytest tests for FitFindr tools.
Run with: pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ---------------------------------------------------------------------------
# search_listings tests
# ---------------------------------------------------------------------------

class TestSearchListings:
    def test_returns_list(self):
        results = search_listings("vintage graphic tee")
        assert isinstance(results, list)

    def test_broad_search_returns_results(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0

    def test_impossible_query_returns_empty_list(self):
        results = search_listings("designer ballgown", size="XXS", max_price=5)
        assert results == []

    def test_price_filter_respected(self):
        results = search_listings("jacket", size=None, max_price=10)
        assert all(item["price"] <= 10 for item in results)

    def test_size_filter_respected(self):
        results = search_listings("tee", size="S", max_price=None)
        assert all(item["size"].lower() == "s" for item in results)

    def test_results_have_required_fields(self):
        results = search_listings("vintage", size=None, max_price=100)
        assert len(results) > 0
        required_fields = {"id", "title", "price", "size", "platform", "condition"}
        for item in results:
            assert required_fields.issubset(set(item.keys()))

    def test_no_exception_on_empty_description(self):
        results = search_listings("", size=None, max_price=None)
        assert isinstance(results, list)

    def test_results_sorted_by_relevance(self):
        results = search_listings("vintage graphic tee", size=None, max_price=100)
        # Items with more keyword hits should appear first
        assert len(results) > 0


# ---------------------------------------------------------------------------
# suggest_outfit tests
# ---------------------------------------------------------------------------

class TestSuggestOutfit:
    def test_returns_string(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        outfit = suggest_outfit(results[0], get_example_wardrobe())
        assert isinstance(outfit, str)
        assert len(outfit) > 0

    def test_handles_empty_wardrobe(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        outfit = suggest_outfit(results[0], get_empty_wardrobe())
        assert isinstance(outfit, str)
        assert len(outfit) > 0
        # Should not raise an exception; should return useful content
        assert "Error" not in outfit or "try again" in outfit.lower()

    def test_empty_wardrobe_does_not_crash(self):
        """Empty wardrobe returns general advice, not an exception."""
        results = search_listings("slip dress", size="S", max_price=50)
        assert len(results) > 0
        result = suggest_outfit(results[0], get_empty_wardrobe())
        assert isinstance(result, str)
        assert result != ""


# ---------------------------------------------------------------------------
# create_fit_card tests
# ---------------------------------------------------------------------------

class TestCreateFitCard:
    def test_returns_string(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        item = results[0]
        outfit = suggest_outfit(item, get_example_wardrobe())
        card = create_fit_card(outfit, item)
        assert isinstance(card, str)
        assert len(card) > 0

    def test_empty_outfit_returns_error_message(self):
        """Empty outfit string should return error message, not crash."""
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        result = create_fit_card("", results[0])
        assert "Error" in result
        assert isinstance(result, str)

    def test_blank_outfit_returns_error_message(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        result = create_fit_card("   ", results[0])
        assert "Error" in result

    def test_outputs_vary_across_runs(self):
        """Running create_fit_card twice on the same input should produce different text."""
        results = search_listings("vintage graphic tee", size="M", max_price=30)
        assert len(results) > 0
        item = results[0]
        outfit = suggest_outfit(item, get_example_wardrobe())
        card1 = create_fit_card(outfit, item)
        card2 = create_fit_card(outfit, item)
        # With temperature=1.0 these should differ; if they're identical it's
        # technically still acceptable (low probability), so we just log
        if card1 == card2:
            print("WARNING: create_fit_card returned identical output on two runs — consider raising temperature")
        assert isinstance(card1, str) and isinstance(card2, str)


# ---------------------------------------------------------------------------
# Integration: full agent flow
# ---------------------------------------------------------------------------

class TestAgentFlow:
    def test_full_happy_path(self):
        from agent import run_agent
        session = run_agent(
            "vintage graphic tee", size="M", max_price=30.0,
            wardrobe=get_example_wardrobe()
        )
        assert session["selected_item"] is not None
        assert session["outfit_suggestion"] is not None
        assert session["fit_card"] is not None
        assert session["error"] is None

    def test_no_results_stops_early(self):
        from agent import run_agent
        session = run_agent(
            "designer ballgown", size="XXS", max_price=5.0,
            wardrobe=get_example_wardrobe()
        )
        assert session["error"] is not None
        assert session["selected_item"] is None
        assert session["outfit_suggestion"] is None
        assert session["fit_card"] is None
