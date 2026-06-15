# FitFindr

A conversational shopping agent that searches secondhand clothing listings, suggests outfits using your existing wardrobe, and generates shareable fit cards.

## Setup

```bash
pip install -r requirements.txt
```

Add your Groq API key to `.env` (free at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the app:
```bash
python app.py
```

Run tests:
```bash
pytest tests/ -v
```

---

## Tool Inventory

### 1. search_listings

**Purpose:** Filters the mock listings dataset against user criteria and returns the best matches.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords to match against listing title, description, style_tags, and category |
| `size` | `str \| None` | Size filter (case-insensitive substring match against listing size field) |
| `max_price` | `float \| None` | Maximum price ceiling (inclusive) |

**Returns:** `list[dict]` — Up to 5 listing dicts sorted by keyword-overlap score (descending). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches.

### 2. suggest_outfit

**Purpose:** Uses an LLM to suggest 1–2 complete outfits pairing a new listing with pieces from the user's wardrobe.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict (the item the user is considering) |
| `wardrobe` | `dict` | Wardrobe object with an `items` list of wardrobe item dicts |

**Returns:** `str` — Outfit suggestions as a natural-language string. If wardrobe is empty, returns general styling advice instead.

### 3. create_fit_card

**Purpose:** Generates a short, shareable OOTD caption for the thrifted outfit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit()` |
| `new_item` | `dict` | The listing dict for the item |

**Returns:** `str` — A 2–4 sentence Instagram/TikTok-style caption. If `outfit` is empty/whitespace, returns an error message string instead of crashing.

---

## Planning Loop

The agent uses a fixed three-stage pipeline with early-exit on failure:

1. **Parse query** — Extract `description`, `size`, and `max_price` from natural language using regex. Store in `session["parsed"]`.

2. **Search** — Call `search_listings(description, size, max_price)`.
   - If results are empty → set `session["error"]` with actionable advice → **return immediately** (never call tools 2 or 3).
   - If results exist → set `session["selected_item"] = results[0]`.

3. **Suggest outfit** — Call `suggest_outfit(selected_item, wardrobe)`. Store result in `session["outfit_suggestion"]`.

4. **Create fit card** — Call `create_fit_card(outfit_suggestion, selected_item)`. Store result in `session["fit_card"]`. Return the session.

The loop terminates when either an error causes early exit (step 2) or the fit card is generated (step 4).

---

## State Management

All state lives in a single `session` dict initialized at the start of each run:

| Key | Type | Set by | Used by |
|-----|------|--------|---------|
| `query` | str | init | parser |
| `parsed` | dict | parser | search_listings call |
| `search_results` | list[dict] | search_listings | planning loop |
| `selected_item` | dict | planning loop (`results[0]`) | suggest_outfit, create_fit_card |
| `wardrobe` | dict | init (loaded from data) | suggest_outfit |
| `outfit_suggestion` | str | suggest_outfit | create_fit_card |
| `fit_card` | str | create_fit_card | returned to user |
| `error` | str \| None | any failure point | returned to user |

Each tool receives only its specific arguments — not the full session. The planning loop is the only component that reads/writes the session directly.

---

## Error Handling

### search_listings — No results

**Trigger:** Query "designer ballgown size XXS under $5"

**Observed behavior:**
```
>>> from agent import run_agent
>>> from utils.data_loader import get_example_wardrobe
>>> session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
>>> print(session["error"])
No listings matched your search. Try broadening your filters (higher price, different size, or fewer keywords).
>>> print(session["outfit_suggestion"])
None
>>> print(session["fit_card"])
None
```

The agent returns a helpful message and does NOT call `suggest_outfit` or `create_fit_card`.

### suggest_outfit — Empty wardrobe

**Trigger:** Pass `get_empty_wardrobe()` (items list is `[]`)

**Observed behavior:** The function does not crash. It sends the LLM a prompt asking for general styling advice without referencing any wardrobe pieces, and returns a useful string like "This vintage graphic tee pairs well with relaxed-fit denim and chunky sneakers for a streetwear look."

### create_fit_card — Empty outfit string

**Trigger:** `create_fit_card("", results[0])`

**Observed behavior:**
```
>>> print(create_fit_card("", results[0]))
Could not generate a fit card — no outfit suggestion was provided. Try searching for an item first.
```

Returns a descriptive error string. No exception raised. The guard checks for both empty string and whitespace-only input.

---

## Spec Reflection

The final implementation closely matches the planning.md spec with a few deviations:

- **suggest_outfit return type:** The planning.md spec described returning a structured dict (`outfit_pieces` + `styling_tips`). The actual stub signature returns a plain string. I followed the stub — the LLM produces natural-language outfit suggestions as a single string, which flows directly into `create_fit_card`. The structured approach would have been more testable but the string approach is simpler and matches the existing file contract.

- **Query parsing:** I originally planned to potentially use the LLM for parsing. I chose regex instead — it's faster, free (no API call), and handles the common patterns (under $X, size Y) reliably. The tradeoff is it won't understand creative phrasings like "nothing too expensive" but it covers the project's test cases.

- **Top-result selection:** The spec described potentially showing multiple results and letting the user pick. For simplicity, the agent auto-selects `results[0]` (highest relevance score). This keeps the pipeline deterministic and single-turn.

---

## AI Usage

### Instance 1: Implementing search_listings

**Input to AI:** I gave Claude the Tool 1 spec block from planning.md (all five parameters with types, the return format listing all 11 fields, both failure modes) plus the full source of `utils/data_loader.py`.

**What it produced:** A function that loads listings, filters by max_price and size, scores by keyword overlap, sorts descending, and returns top 5.

**What I reviewed/changed:** Verified it calls `load_listings()` (not raw JSON reads), handles None for optional params, uses case-insensitive matching for size (substring rather than exact match — important since sizes like "S/M" need to match "S"), and returns `[]` on no matches rather than raising. I accepted the implementation after confirming these checks against my spec.

### Instance 2: Implementing the planning loop

**Input to AI:** I provided the Planning Loop section (4 numbered steps with branching), the State Management table (all 8 session keys with types and who sets/reads them), the Error Handling table, and the Architecture diagram.

**What it produced:** A `run_agent()` function that initializes the session, parses the query, calls tools in sequence with the early-exit branch on empty results, and stores each result in the correct session key.

**What I reviewed/changed:** Confirmed that: (a) it checks `if not results` after `search_listings` and returns early without calling `suggest_outfit`, (b) it passes `session["selected_item"]` (not the full results list) to `suggest_outfit`, (c) it wraps `search_listings` in try/except for the file-not-found case. I also added the `_parse_query` helper separately since the generated code left that as a placeholder — I specified regex-based extraction for price ("under $X") and size ("size Y") patterns.

### Instance 3: Writing tests

**Input to AI:** The tool specs (expected inputs/outputs/failure modes) and the requirement to test each failure mode.

**What it produced:** 11 tests covering happy paths and failure modes for all three tools.

**What I changed:** Added the `groq_reachable()` skip mechanism so LLM tests auto-skip in environments without API access. The original tests assumed network access was always available and would have failed in CI or sandboxed environments.
