# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Filters the mock listings dataset (loaded via `load_listings()` from `utils/data_loader.py`) against user-specified criteria and returns the top matching results sorted by relevance.

**Input parameters:**
- `description` (str): A free-text search query matched against the listing's `title`, `description`, `style_tags`, and `category` fields. The tool lowercases both the query and the target text and checks for substring/keyword overlap.
- `size` (str, optional): A size string (e.g. "M", "W30", "One Size") matched against the listing's `size` field. If omitted, size is not filtered.
- `max_price` (float, optional): Upper price limit in dollars. Listings with `price > max_price` are excluded. If omitted, price is not filtered.
- `category` (str, optional): One of `"tops"`, `"bottoms"`, `"outerwear"`, `"shoes"`, `"accessories"`. If provided, only listings in that category are returned.
- `condition` (str, optional): One of `"excellent"`, `"good"`, `"fair"`. If provided, only listings at or above that quality level are returned.

**What it returns:**
A list of matching listing dicts (up to 5), each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or null), `platform` (str). Results are sorted by how many keywords from `description` appear in the listing's text fields, highest match count first.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a user-friendly message like "No listings matched your search. Try broadening your filters (higher price, different size, or fewer keywords)." The planning loop skips `suggest_outfit` and `create_fit_card` and returns the session with just the error message.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a new clothing item (a listing the user is considering buying) and the user's existing wardrobe, then builds an outfit by selecting complementary pieces from the wardrobe that pair well with the new item based on color coordination, style tag overlap, and category coverage (the outfit should include a top, bottom, shoes, and optionally outerwear/accessories).

**Input parameters:**
- `new_item` (dict): A single listing dict from `search_listings` results containing at minimum: `title` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]).
- `wardrobe` (dict): A wardrobe object with an `items` key containing a list of wardrobe item dicts. Each item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or null).

**What it returns:**
A dict with two keys: `outfit_pieces` — a list of dicts, each with `item_name` (str), `category` (str), `source` (str, either "wardrobe" or "new"), and `reason` (str explaining why it was chosen); and `styling_tips` — a string with 1–2 sentences of advice on how to wear the outfit.

**What happens if it fails or returns nothing:**
If the wardrobe is empty (`items` list has length 0), the agent skips pairing and instead sets `session["outfit"]` to a general styling suggestion based solely on the new item's style tags and colors (e.g., "This vintage graphic tee pairs well with baggy jeans and chunky sneakers for a streetwear look."). The planning loop still proceeds to `create_fit_card` using whatever outfit data is available.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion and the selected listing, then produces a formatted text "fit card" — a summary card the user can read that shows the listing they'd buy, what wardrobe pieces to wear it with, and styling tips.

**Input parameters:**
- `listing` (dict): The selected listing dict from `search_listings` containing `title`, `price`, `platform`, `condition`, `size`, and `colors`.
- `outfit` (dict): The outfit suggestion dict from `suggest_outfit` containing `outfit_pieces` (list of piece dicts) and `styling_tips` (str).

**What it returns:**
A formatted string (the fit card) structured as: a header with the listing title and price, a "Buy from" line with platform and condition, a "Wear it with" section listing each wardrobe piece and why it works, and a "Styling tips" section with the advice string.

**What happens if it fails or returns nothing:**
If `listing` or `outfit` is missing required fields, the agent constructs a partial fit card using whatever data is available — e.g., if `outfit_pieces` is empty, the card shows the listing info and styling tips only, without a "Wear it with" section. The agent never crashes; it degrades gracefully and still returns a readable response.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop maintains a `session` dict and walks through a fixed three-stage pipeline with early-exit checks at each stage:

1. **Parse the user query.** Extract search parameters from the user's natural language input: `description` keywords, optional `size`, optional `max_price`, optional `category`. Load the user's wardrobe via `get_example_wardrobe()` (or `get_empty_wardrobe()` if none exists) and store it in `session["wardrobe"]`.

2. **Call `search_listings(description, size, max_price, category, condition)`.** Check the return value:
   - If `results` is an empty list → set `session["error"] = "No listings matched your search. Try broadening your filters."` → **return session immediately** (skip steps 3–4).
   - If `results` is non-empty → set `session["search_results"] = results` and `session["selected_item"] = results[0]` (the top match). Proceed to step 3.

3. **Call `suggest_outfit(session["selected_item"], session["wardrobe"])`.** Check the return value:
   - If the wardrobe was empty, `suggest_outfit` returns a fallback dict with empty `outfit_pieces` and a generic `styling_tips` string → store it in `session["outfit"]` and proceed to step 4 anyway.
   - If the wardrobe had items, store the full outfit dict in `session["outfit"]`. Proceed to step 4.

4. **Call `create_fit_card(session["selected_item"], session["outfit"])`.** Store the returned string in `session["fit_card"]`. The loop is now **done** — return the session.

The loop knows it is done when either an error causes early exit (step 2 fails) or `session["fit_card"]` has been set (step 4 completes).

---

## State Management

**How does information from one tool get passed to the next?**

All inter-tool data lives in a single `session` dict created at the start of each run. The planning loop reads from and writes to this dict between tool calls. The keys are:

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `wardrobe` | dict (with `items` list) | Planning loop (loaded at init) | `suggest_outfit` |
| `search_results` | list[dict] | `search_listings` | Planning loop (to pick `selected_item`) |
| `selected_item` | dict | Planning loop (picks `results[0]`) | `suggest_outfit`, `create_fit_card` |
| `outfit` | dict (`outfit_pieces` + `styling_tips`) | `suggest_outfit` | `create_fit_card` |
| `fit_card` | str | `create_fit_card` | Returned to user |
| `error` | str or None | Any tool / planning loop | Returned to user (short-circuits the loop) |

Each tool receives only the specific keys it needs (passed as arguments), not the entire session. The planning loop is the only component that reads and writes the session dict directly.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to: "I couldn't find any listings matching 'vintage graphic tee' under $30. Try raising your budget, dropping the size filter, or searching for something broader like 'graphic tee' or 'vintage tops'." Skip `suggest_outfit` and `create_fit_card` entirely — return the session with only the error key populated. |
| search_listings | `load_listings()` throws an exception (file missing or corrupt JSON) | Catch the exception in a try/except. Set `session["error"]` to: "Something went wrong loading the listings database. Please make sure data/listings.json exists and contains valid JSON." Log the exception message to stderr for debugging. Return the session immediately — do not call any other tools. |
| suggest_outfit | Wardrobe is empty (`len(wardrobe["items"]) == 0`) | Do not crash or skip. Return `{"outfit_pieces": [], "styling_tips": "Since you haven't added wardrobe items yet, try pairing this graphic tee with relaxed straight-leg jeans and chunky sneakers for a streetwear look."}`. The planning loop stores this in `session["outfit"]` and proceeds to `create_fit_card` normally — the fit card will render without a "Wear it with" section but will still show the listing info and the styling tip. |
| suggest_outfit | `new_item` is missing `category` or `style_tags` keys | Guard with `new_item.get("category", "unknown")` and `new_item.get("style_tags", [])`. If category is unknown, skip wardrobe-matching entirely and return `{"outfit_pieces": [], "styling_tips": "We couldn't determine the item type, but it could work as a layering piece with neutral basics."}`. The loop continues to `create_fit_card`. |
| create_fit_card | `outfit` is None or `outfit_pieces` is missing | Use `outfit.get("outfit_pieces", [])` and `outfit.get("styling_tips", "")`. If `outfit_pieces` is empty, omit the "Wear it with" section entirely (don't print an empty list). If `styling_tips` is empty, omit that section too. The card still renders with the listing header (title + price) and "Buy from" line. |
| create_fit_card | `listing` is missing `price`, `platform`, or other fields | Use `.get()` with readable defaults: `listing.get("price", "Price unavailable")`, `listing.get("platform", "Unknown platform")`. The card always renders — it just shows the default text in place of the missing value. |

---

## Architecture

```
User query: "Find me a vintage graphic tee under $30, style it with my wardrobe"
    │
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PLANNING LOOP                                                       │
│                                                                      │
│  1. Parse query → extract description, size, max_price, category     │
│     Load wardrobe → session["wardrobe"]                              │
│     │                                                                │
│     ▼                                                                │
│  2. search_listings(description, size, max_price, category)          │
│     │                                                                │
│     ├── results == [] ──► session["error"] = "No listings found..."  │
│     │                      │                                         │
│     │                      ▼                                         │
│     │                   RETURN SESSION (early exit) ─────────────►  USER
│     │                                                                │
│     ├── results != []                                                │
│     │   session["search_results"] = results                          │
│     │   session["selected_item"] = results[0]                        │
│     │   │                                                            │
│     │   ▼                                                            │
│  3. suggest_outfit(selected_item, wardrobe)                          │
│     │                                                                │
│     ├── wardrobe empty → fallback styling_tips, outfit_pieces = []   │
│     ├── wardrobe has items → full outfit with pieces + tips          │
│     │                                                                │
│     │   session["outfit"] = { outfit_pieces, styling_tips }          │
│     │   │                                                            │
│     │   ▼                                                            │
│  4. create_fit_card(selected_item, outfit)                           │
│     │                                                                │
│     ├── missing data → partial card (degrade gracefully)             │
│     ├── all data present → full fit card                             │
│     │                                                                │
│     │   session["fit_card"] = formatted string                       │
│     │                                                                │
│     ▼                                                                │
│  RETURN SESSION ──────────────────────────────────────────────────► USER
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

Data stores:
  ┌─────────────────────────┐     ┌──────────────────────────┐
  │  data/listings.json     │     │  data/wardrobe_schema.json│
  │  (loaded by             │     │  (loaded by               │
  │   load_listings())      │     │   get_example_wardrobe()) │
  └─────────────────────────┘     └──────────────────────────┘
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **search_listings:** I'll give Claude the Tool 1 block from planning.md (all five input parameters with types, the return format listing all 11 fields, and both failure modes) plus the full source of `utils/data_loader.py`. I'll ask it to implement `search_listings()` as a standalone function that calls `load_listings()`, filters by category/size/max_price/condition, scores remaining listings by counting how many keywords from `description` appear in the listing's title + description + style_tags (lowercased), sorts descending by score, and returns the top 5. Before running the generated code, I'll read through it and check: (a) it imports and calls `load_listings()` rather than reading the JSON itself, (b) it handles all five parameters including when optional ones are None, (c) it returns `[]` (not an exception) when nothing matches. Then I'll test with 3 queries: (1) `description="vintage graphic tee", max_price=30, category="tops"` → expect lst_006 in results; (2) `description="shoes"` with all other params None → expect shoe-category listings; (3) `description="xyznoexist"` → expect empty list.

- **suggest_outfit:** I'll give Claude the Tool 2 block from planning.md (input schema for `new_item` and `wardrobe`, the return dict structure with `outfit_pieces` and `styling_tips`, and both failure modes) plus the `example_wardrobe` object from `wardrobe_schema.json`. I'll ask it to implement `suggest_outfit()` that determines which categories are missing (if the new item is a top, it needs bottoms + shoes + optional outerwear/accessories), scores each wardrobe item by counting shared style_tags with the new item, picks the highest-scoring item per category, and builds the return dict. Before running, I'll check: (a) it handles the empty-wardrobe case by returning `{"outfit_pieces": [], "styling_tips": "<generic tip>"}` instead of crashing, (b) it never picks a wardrobe item from the same category as the new item (no two tops). Then I'll test: (1) pass lst_006 (a top) + example wardrobe → expect it picks w_001 (jeans, shares "streetwear") and w_007 (sneakers, shares "streetwear"); (2) pass lst_006 + empty wardrobe → expect empty `outfit_pieces` and a non-empty `styling_tips` string.

- **create_fit_card:** I'll give Claude the Tool 3 block from planning.md (the two input dicts with their fields, the output format with header/buy-from/wear-with/tips sections, and the graceful-degradation failure mode). I'll ask it to implement `create_fit_card()` that builds a formatted multi-line string. Before running, I'll check: (a) it uses `.get()` with defaults for every field access so missing keys don't crash, (b) it conditionally omits the "Wear it with" section when `outfit_pieces` is empty rather than printing an empty list. Then I'll test: (1) pass full sample data → visually confirm all four sections appear; (2) pass an outfit with empty `outfit_pieces` → confirm the card still renders with listing info and tips but no "Wear it with" block; (3) pass a listing missing `brand` (null) → confirm it doesn't print "None".

**Milestone 4 — Planning loop and state management:**

- I'll give Claude three sections from planning.md: the Planning Loop (with the four numbered steps and branching logic), the State Management table (all six session keys with types and who sets/reads them), and the Architecture diagram. I'll ask it to implement `run_agent(user_query)` that initializes `session = {}`, loads the wardrobe, calls the three tool functions in sequence with the exact early-exit branches described, and returns the session dict. Before running, I'll check: (a) it wraps `search_listings` in a try/except that catches `load_listings()` failures, (b) it checks `if not results` after `search_listings` and sets `session["error"]` + returns immediately without calling `suggest_outfit`, (c) it passes `session["selected_item"]` (not the full results list) to `suggest_outfit`. Then I'll test: (1) the example query "vintage graphic tee under $30" end-to-end → confirm `session["fit_card"]` is a non-empty string and `session["error"]` is None; (2) a query that matches nothing ("purple leather kilt size XXS max $5") → confirm `session["error"]` is set, `session.get("outfit")` is None, and `session.get("fit_card")` is None.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**What FitFindr does:** FitFindr is a conversational shopping agent that helps users find secondhand clothing by searching a listings dataset (filtered by category, style, size, price, etc.) via `search_listings`, then uses `suggest_outfit` to pair matching items with pieces already in the user's wardrobe, and finally calls `create_fit_card` to produce a styled visual summary of the recommended outfit. When `search_listings` returns no matches, the agent should broaden filters or tell the user nothing was found; when `suggest_outfit` receives an empty wardrobe, it should fall back to general styling advice; and when `create_fit_card` gets incomplete data, it should skip the card and present the outfit as text instead.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1: Parse query and load wardrobe**
The planning loop extracts: `description="vintage graphic tee"`, `max_price=30.0`, `category="tops"`. Size is not specified so it's left as None. The user mentions baggy jeans and chunky sneakers, which map to wardrobe items, so the agent loads the example wardrobe via `get_example_wardrobe()` and stores it in `session["wardrobe"]`.

**Step 2: Call `search_listings(description="vintage graphic tee", max_price=30.0, category="tops")`**
The tool loads all listings, filters to category=="tops" and price<=30, then scores by keyword overlap with "vintage graphic tee". It returns a list like:
- `lst_006`: "Graphic Tee — 2003 Tour Bootleg Style" ($24, good condition, depop) — matches "vintage", "graphic tee"
- `lst_002`: "Y2K Baby Tee — Butterfly Print" ($18, excellent, depop) — matches "vintage"

Results are non-empty, so the loop sets `session["search_results"] = results` and `session["selected_item"] = lst_006` (the top match).

**Step 3: Call `suggest_outfit(new_item=lst_006, wardrobe=session["wardrobe"])`**
The new item is a top (category: "tops"), so the tool needs to pick a bottom, shoes, and optionally outerwear/accessories from the wardrobe. It selects:
- **Bottom:** w_001 "Baggy straight-leg jeans, dark wash" — shares "streetwear" style tag with the tee, and the user mentioned baggy jeans.
- **Shoes:** w_007 "Chunky white sneakers" — shares "streetwear" tag, user mentioned chunky sneakers.
- **Outerwear:** w_006 "Vintage black denim jacket" — shares "vintage" tag, black complements the black tee.

Returns: `{ outfit_pieces: [{item_name: "Baggy straight-leg jeans", category: "bottoms", source: "wardrobe", reason: "Streetwear tag match + relaxed silhouette balances the boxy tee"}, ...], styling_tips: "Layer the denim jacket open over the graphic tee and cuff the jeans slightly above the sneakers for a clean streetwear look." }`

The loop stores this in `session["outfit"]`.

**Step 4: Call `create_fit_card(listing=session["selected_item"], outfit=session["outfit"])`**
The tool formats the fit card string and stores it in `session["fit_card"]`. The loop is done — return the session.

**Final output to user:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Graphic Tee — 2003 Tour Bootleg Style
  $24.00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Buy from: depop · Condition: good

  Wear it with:
  • Baggy straight-leg jeans, dark wash (your wardrobe)
    → Streetwear tag match + relaxed silhouette balances the boxy tee
  • Chunky white sneakers (your wardrobe)
    → Streetwear match, white sneakers pop against dark denim
  • Vintage black denim jacket (your wardrobe)
    → Vintage tag match, layer it open for a complete look

  Styling tips:
  Layer the denim jacket open over the graphic tee and cuff the
  jeans slightly above the sneakers for a clean streetwear look.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
