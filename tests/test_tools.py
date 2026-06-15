"""
Tests for FitFindr tools.

Run with: pytest tests/ -v
LLM tests auto-skip if Groq API is unreachable.
"""

import os
import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── Helper: detect if Groq API is reachable ───────────────────────────────────

_GROQ_REACHABLE = None

def groq_reachable():
    global _GROQ_REACHABLE
    if _GROQ_REACHABLE is None:
        try:
            from groq import Groq
            key = os.environ.get("GROQ_API_KEY", "")
            if not key:
                _GROQ_REACHABLE = False
            else:
                client = Groq(api_key=key)
                client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=1,
                )
                _GROQ_REACHABLE = True
        except Exception:
            _GROQ_REACHABLE = False
    return _GROQ_REACHABLE


requires_llm = pytest.mark.skipif(
    "not groq_reachable()",
    reason="Groq API not reachable",
)


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "title" in results[0]
    assert "price" in results[0]


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("jeans", size="W30", max_price=None)
    assert isinstance(results, list)
    for item in results:
        assert "w30" in item["size"].lower()


def test_search_returns_max_five():
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) <= 5


def test_search_sorted_by_relevance():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    if len(results) >= 2:
        keywords = ["vintage", "graphic", "tee"]
        def score(item):
            text = " ".join([
                item.get("title", ""), item.get("description", ""),
                " ".join(item.get("style_tags", [])), item.get("category", ""),
            ]).lower()
            return sum(1 for kw in keywords if kw in text)
        assert score(results[0]) >= score(results[-1])


# ── suggest_outfit tests ──────────────────────────────────────────────────────

@requires_llm
def test_suggest_outfit_with_wardrobe():
    new_item = {
        "title": "Graphic Tee",
        "category": "tops",
        "colors": ["black"],
        "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
    }
    wardrobe = get_example_wardrobe()
    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


@requires_llm
def test_suggest_outfit_empty_wardrobe():
    new_item = {
        "title": "Vintage Jeans",
        "category": "bottoms",
        "colors": ["blue", "indigo"],
        "style_tags": ["vintage", "classic", "denim"],
    }
    wardrobe = get_empty_wardrobe()
    result = suggest_outfit(new_item, wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0


# ── create_fit_card tests ─────────────────────────────────────────────────────

@requires_llm
def test_create_fit_card_returns_string():
    outfit = "Pair the graphic tee with baggy jeans and chunky sneakers."
    new_item = {"title": "Graphic Tee", "price": 24.00, "platform": "depop"}
    result = create_fit_card(outfit, new_item)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit():
    new_item = {"title": "Some Item", "price": 10.00, "platform": "depop"}
    result = create_fit_card("", new_item)
    assert isinstance(result, str)
    assert "could not" in result.lower() or "no outfit" in result.lower()


def test_create_fit_card_whitespace_outfit():
    new_item = {"title": "Test Item", "price": 5.00, "platform": "poshmark"}
    result = create_fit_card("   ", new_item)
    assert isinstance(result, str)
    assert "could not" in result.lower() or "no outfit" in result.lower()
