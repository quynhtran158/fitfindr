# FitFindr — Planning Document

## A Complete Interaction

FitFindr is an AI agent that helps users discover secondhand clothing and style it with what they already own. When a user submits a natural-language query (e.g., "I want a vintage graphic tee under $30, size M — I mostly wear baggy jeans and chunky boots"), the agent:

1. Searches mock listings for matching items using `search_listings`.
2. If results are found, passes the top result and the user's wardrobe to `suggest_outfit` for styling advice.
3. Uses that styling suggestion and the selected item to generate a shareable caption via `create_fit_card`.
4. If any step returns nothing useful, the agent communicates the failure to the user and stops — it never passes empty data forward.

**Example query trace:**

- **User input:** "Looking for a vintage graphic tee under $30, size M. I wear baggy jeans and chunky boots."
- **Step 1 — search_listings("vintage graphic tee", size="M", max_price=30.0)**
  - Returns: `[{"id":"1","title":"Faded Band Tee","price":22.0,"platform":"Depop",...}, {"id":"8",...}, {"id":"15",...}]`
  - Agent picks `results[0]` → `selected_item = {"id":"1","title":"Faded Band Tee","price":22.0,...}`
- **Step 2 — suggest_outfit(new_item=selected_item, wardrobe=user_wardrobe)**
  - Returns: `"Pair the Faded Band Tee with your baggy Levi's and chunky platform boots. Tuck the front corner slightly and roll the sleeves once for that effortless 90s grunge look."`
  - Agent stores: `outfit_suggestion = "Pair the Faded Band Tee..."`
- **Step 3 — create_fit_card(outfit=outfit_suggestion, new_item=selected_item)**
  - Returns: `"thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"`
- **Error path:** If `search_listings` returns `[]`, agent sets `session["error"]` and returns without calling the other two tools.

---

## Tool Specs

### Tool 1: search_listings

**What it does:** Filters the mock listings dataset and returns items that match the user's description, size, and price ceiling.

**Inputs:**
| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Natural language query (e.g., "vintage graphic tee"). Matched against title, description, style_tags, category, brand. |
| `size` | `str \| None` | Clothing size (e.g., "M", "S", "L"). `None` means no size filter. |
| `max_price` | `float \| None` | Maximum acceptable price. `None` means no price ceiling. |

**Returns:** `list[dict]` — A list of listing dicts matching all provided filters, sorted so the closest match comes first. Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` (empty list) when nothing matches — never raises an exception.

**Failure mode:** If the list is empty, the agent sets `session["error"] = "No listings found for '[description]' in size [size] under $[max_price]. Try a broader description or higher price."` and returns early without calling subsequent tools.

---

### Tool 2: suggest_outfit

**What it does:** Given a new item and the user's existing wardrobe, asks the LLM to suggest one or more complete outfit combinations.

**Inputs:**
| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | A single listing dict (same structure as returned by search_listings). |
| `wardrobe` | `dict` | User wardrobe with keys: `size` (str), `style_preferences` (list[str]), `items` (list[dict]). Each item has: `id`, `title`, `category`, `style_tags`, `colors`, `fit_notes`. |

**Returns:** `str` — A natural-language outfit suggestion (2–4 sentences) describing how to wear the new item with specific wardrobe pieces. If the wardrobe is empty or has no items, returns general styling advice for the item based on its style tags.

**Failure mode:** If `wardrobe["items"]` is empty, the LLM prompt changes to ask for general styling advice rather than wardrobe-specific combos — returns a string with standalone styling tips. If the LLM call fails, returns `"Could not generate outfit suggestion — please try again."`.

---

### Tool 3: create_fit_card

**What it does:** Generates a short, shareable social-media-style caption (the kind someone would use on Instagram or TikTok) describing the complete outfit.

**Inputs:**
| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The outfit suggestion from suggest_outfit. |
| `new_item` | `dict` | The listing dict for the thrifted piece (used to reference platform, price, title). |

**Returns:** `str` — A 1–3 sentence caption that sounds authentic, casual, and shareable. Different runs on the same inputs should produce varied outputs (temperature > 0.9). Never returns an empty string.

**Failure mode:** If `outfit` is empty or blank, returns `"Error: cannot generate fit card without outfit details."` without calling the LLM. If the LLM call fails, returns `"Could not generate fit card — please try again."`.

---

## Planning Loop

The planning loop is implemented as a sequential conditional flow in `run_agent()`:

```
1. Call search_listings(description, size, max_price)
   → IF results == []:
       session["error"] = "No listings found for..."
       RETURN session  ← early exit, do not call further tools
   → IF results != []:
       session["selected_item"] = results[0]

2. Call suggest_outfit(session["selected_item"], wardrobe)
   → IF return value starts with "Error" or "Could not":
       session["error"] = <return value>
       session["outfit_suggestion"] = None
       RETURN session  ← early exit
   → IF return value is a valid string:
       session["outfit_suggestion"] = <return value>

3. Call create_fit_card(session["outfit_suggestion"], session["selected_item"])
   → session["fit_card"] = <return value>

4. RETURN session  ← all three tools succeeded
```

The loop never calls `suggest_outfit` if `search_listings` returns nothing. It never calls `create_fit_card` if `suggest_outfit` fails. Each tool's return value is inspected before proceeding.

---

## Architecture

```
User query (description, size, max_price, wardrobe)
    │
    ▼
Planning Loop (run_agent in agent.py)
    │
    ├─► search_listings(description, size, max_price)
    │       │
    │       ├── results == []  ──► session["error"] = "No listings found..."
    │       │                                │
    │       │                                └──► RETURN session (early exit)
    │       │
    │       └── results != []
    │               │
    │           session["selected_item"] = results[0]
    │               │
    ├─► suggest_outfit(selected_item, wardrobe)
    │       │
    │       ├── LLM error / empty wardrobe fallback
    │       │       └── returns general advice string (no early exit)
    │       │
    │       └── success
    │               │
    │           session["outfit_suggestion"] = <LLM response>
    │               │
    └─► create_fit_card(outfit_suggestion, selected_item)
            │
        session["fit_card"] = <LLM caption>
            │
            ▼
        RETURN session
```

---

## State Management

All state lives in a single `session` dict that is created at the start of `run_agent()` and passed through each step:

| Key | Type | Set by | Used by |
|---|---|---|---|
| `session["query"]` | str | run_agent init | logging / display |
| `session["selected_item"]` | dict | after search_listings | suggest_outfit, create_fit_card |
| `session["outfit_suggestion"]` | str | after suggest_outfit | create_fit_card |
| `session["fit_card"]` | str | after create_fit_card | app.py display |
| `session["error"]` | str or None | any tool failure | app.py display |
| `session["all_results"]` | list | after search_listings | optional display |

No tool receives the entire session — each tool receives only the specific values it needs. `app.py` reads from the session at the end to populate the three output panels.

---

## Error Handling Strategy

| Tool | Failure mode | What the agent does |
|---|---|---|
| `search_listings` | No matches found | Returns `[]`; agent sets `session["error"]` with specific message including the query params; stops and shows error to user |
| `search_listings` | File read error | Catches exception, returns `[]`; treated the same as no results |
| `suggest_outfit` | Empty wardrobe | Changes LLM prompt to ask for general styling advice; returns a valid string |
| `suggest_outfit` | LLM API failure | Catches exception, returns `"Could not generate outfit suggestion — please try again."` |
| `create_fit_card` | Empty outfit string | Returns `"Error: cannot generate fit card without outfit details."` immediately, no LLM call |
| `create_fit_card` | LLM API failure | Catches exception, returns `"Could not generate fit card — please try again."` |

---

## AI Tool Plan

**For search_listings (Milestone 3):**
I will give Claude the Tool 1 spec block (inputs, return value, failure mode) from this planning.md and ask it to implement the function using `load_listings()`. Before using the output I will verify: (1) all three filter parameters are applied, (2) the empty case returns `[]` not `None`, (3) no exceptions are raised. Then I will test with 3 queries: one broad, one size-filtered, and one impossible.

**For suggest_outfit (Milestone 3):**
I will give Claude the Tool 2 spec and ask it to implement using the Groq API. I will verify: (1) it handles empty `wardrobe["items"]`, (2) it uses the correct model (`llama-3.3-70b-versatile`), (3) it catches API exceptions. I will test with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

**For create_fit_card (Milestone 3):**
I will give Claude the Tool 3 spec and run it 5 times on the same input — if all outputs are identical I will increase temperature. I will verify it handles the empty-outfit guard before any LLM call.

**For the planning loop (Milestone 4):**
I will share the full Architecture diagram above plus the Planning Loop section with Claude and ask it to implement `run_agent()` in `agent.py`. I will review that: (1) it branches on the `search_listings` result, (2) state flows through the session dict, (3) it does not call all three tools unconditionally.

---

## Complete Interaction Walkthrough

**Query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

1. `run_agent()` initializes session with `query`, `error=None`, `selected_item=None`, etc.
2. Calls `search_listings("vintage graphic tee", size="M", max_price=30.0)`.
   - Matches: id=1 (Faded Band Tee, $22, M), id=8 (Vintage Graphic Tee — Sun Print, $25, M), id=15 (Graphic Tee — Vintage Sports, $20, M).
   - Returns list of 3 dicts sorted by relevance (keyword match score).
   - `session["selected_item"] = results[0]` (Faded Band Tee).
3. Calls `suggest_outfit(selected_item={"title":"Faded Band Tee",...}, wardrobe=user_wardrobe)`.
   - LLM sees the item's style_tags (vintage, grunge) and wardrobe pieces.
   - Returns: "Pair the Faded Band Tee with your baggy Levi's and chunky boots — roll the sleeves once and tuck the front corner slightly for that effortless 90s look."
   - `session["outfit_suggestion"] = <above string>`.
4. Calls `create_fit_card(outfit=<outfit_suggestion>, new_item=selected_item)`.
   - LLM generates a casual Instagram-style caption referencing the Depop platform and $22 price.
   - Returns: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"
   - `session["fit_card"] = <above string>`.
5. `app.py` reads session and populates: Search Results panel, Outfit Suggestion panel, Fit Card panel.
