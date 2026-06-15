"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ─────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    parsed = {"description": query, "size": None, "max_price": None}

    price_match = re.search(
        r'(?:under|below|max|less than|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)',
        query, re.IGNORECASE
    )
    if not price_match:
        price_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(?:or less|max)', query, re.IGNORECASE)
    if price_match:
        parsed["max_price"] = float(price_match.group(1))

    size_match = re.search(r'size\s+([A-Za-z0-9/]+)', query, re.IGNORECASE)
    if size_match:
        parsed["size"] = size_match.group(1)

    desc = query
    if price_match:
        desc = re.sub(
            r'(?:under|below|max|less than|up to|<)\s*\$?\s*\d+(?:\.\d+)?',
            '', desc, flags=re.IGNORECASE
        )
        desc = re.sub(r'\$\d+(?:\.\d+)?\s*(?:or less|max)', '', desc, flags=re.IGNORECASE)
    if size_match:
        desc = re.sub(r'size\s+[A-Za-z0-9/]+', '', desc, flags=re.IGNORECASE)

    desc = re.sub(r'[,\s]+', ' ', desc).strip()
    desc = re.sub(r'^(?:looking for|find me|i want|i need|get me|show me)\s+(?:a\s+|an\s+)?',
                  '', desc, flags=re.IGNORECASE).strip()
    parsed["description"] = desc if desc else query

    return parsed


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query
    session["parsed"] = _parse_query(query)
    desc = session["parsed"]["description"]
    size = session["parsed"]["size"]
    max_price = session["parsed"]["max_price"]

    # Step 3: Call search_listings and check for empty results
    try:
        results = search_listings(desc, size=size, max_price=max_price)
    except Exception as e:
        session["error"] = f"Could not load listings data: {e}"
        return session

    session["search_results"] = results

    if not results:
        session["error"] = (
            "No listings matched your search. "
            "Try broadening your filters (higher price, different size, or fewer keywords)."
        )
        return session  # Early exit

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Call suggest_outfit
    session["outfit_suggestion"] = suggest_outfit(session["selected_item"], session["wardrobe"])

    # Step 6: Call create_fit_card
    session["fit_card"] = create_fit_card(session["outfit_suggestion"], session["selected_item"])

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
