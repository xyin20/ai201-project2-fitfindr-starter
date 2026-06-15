"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    # 1. Load all listings
    listings = load_listings()

    # 2. Filter by max_price (if provided)
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # 3. Filter by size (if provided) — case-insensitive substring match
    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # 4. Score each listing by keyword overlap with description
    keywords = description.lower().split()
    scored = []
    for listing in listings:
        # Build a single searchable text blob from the listing
        search_text = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            " ".join(listing.get("style_tags", [])),
            listing.get("category", ""),
        ]).lower()
        score = sum(1 for kw in keywords if kw in search_text)
        if score > 0:
            scored.append((score, listing))

    # 5. Sort by score descending, return top 5
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:5]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_name = new_item.get("title", "unknown item")
    item_category = new_item.get("category", "unknown")
    item_colors = ", ".join(new_item.get("colors", []))
    item_tags = ", ".join(new_item.get("style_tags", []))

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        # Empty wardrobe — ask for general styling advice
        prompt = (
            f"I just found a thrifted {item_name} (category: {item_category}, "
            f"colors: {item_colors}, style: {item_tags}). "
            f"I don't have a wardrobe logged yet. Suggest 1-2 complete outfit ideas "
            f"using generic pieces that would pair well with this item. "
            f"Be specific about colors, silhouettes, and shoe types. Keep it under 150 words."
        )
    else:
        # Format wardrobe items for the prompt
        wardrobe_text = "\n".join(
            f"- {w['name']} (category: {w['category']}, colors: {', '.join(w.get('colors', []))}, "
            f"style: {', '.join(w.get('style_tags', []))})"
            for w in wardrobe_items
        )
        prompt = (
            f"I'm considering buying: {item_name} (category: {item_category}, "
            f"colors: {item_colors}, style: {item_tags}).\n\n"
            f"Here's what I already own:\n{wardrobe_text}\n\n"
            f"Suggest 1-2 complete outfits using the new item plus pieces from my wardrobe. "
            f"For each outfit, name the specific wardrobe pieces by name and explain why they "
            f"work together (color coordination, style match, silhouette balance). "
            f"Keep it under 200 words."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a fashion stylist who specializes in thrifted and secondhand fashion. Give specific, actionable outfit advice."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.
    """
    # Guard against empty or whitespace-only outfit
    if not outfit or not outfit.strip():
        return "Could not generate a fit card — no outfit suggestion was provided. Try searching for an item first."

    item_name = new_item.get("title", "a thrifted find")
    item_price = new_item.get("price", "unknown price")
    item_platform = new_item.get("platform", "unknown platform")

    prompt = (
        f"Write a 2-4 sentence Instagram/TikTok OOTD caption for this thrifted outfit.\n\n"
        f"The key piece: {item_name}, ${item_price} from {item_platform}.\n"
        f"The full outfit: {outfit}\n\n"
        f"Guidelines:\n"
        f"- Sound casual and authentic, like a real person posting their fit\n"
        f"- Mention the item name, price, and platform naturally (once each)\n"
        f"- Capture the outfit vibe with specific style terms\n"
        f"- Do NOT use hashtags\n"
        f"- Keep it to 2-4 sentences max"
    )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You write short, authentic social media captions for thrifted outfits. No hashtags, no emojis, no product-description tone."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=150,
    )

    return response.choices[0].message.content.strip()
