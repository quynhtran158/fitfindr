"""
FitFindr planning loop — run_agent() orchestrates the three tools and manages
session state across tool calls.
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def run_agent(
    description: str,
    size: str | None,
    max_price: float | None,
    wardrobe: dict,
) -> dict:
    """Run the FitFindr planning loop for a single user query.

    Planning logic:
    1. Call search_listings. If empty → set error and return early.
    2. Call suggest_outfit with selected_item and wardrobe.
       If it returns an error string → set error and return early.
    3. Call create_fit_card with outfit suggestion and selected_item.
    4. Return completed session.

    Args:
        description (str): Natural language item description.
        size (str | None): User's size, or None for no filter.
        max_price (float | None): Price ceiling, or None for no filter.
        wardrobe (dict): User wardrobe dict (see wardrobe_schema.json).

    Returns:
        dict: Session state with keys:
            - query (str)
            - all_results (list[dict])
            - selected_item (dict | None)
            - outfit_suggestion (str | None)
            - fit_card (str | None)
            - error (str | None)
    """
    session = {
        "query": description,
        "all_results": [],
        "selected_item": None,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }

    # Step 1: Search listings
    results = search_listings(description, size=size, max_price=max_price)
    session["all_results"] = results

    if not results:
        size_str = f" in size {size}" if size else ""
        price_str = f" under ${max_price:.0f}" if max_price is not None else ""
        session["error"] = (
            f"No listings found for '{description}'{size_str}{price_str}. "
            f"Try a broader description, a different size, or a higher price."
        )
        return session

    session["selected_item"] = results[0]

    # Step 2: Suggest outfit
    outfit = suggest_outfit(session["selected_item"], wardrobe)

    if outfit.startswith("Could not") or outfit.startswith("Error"):
        session["error"] = outfit
        return session

    session["outfit_suggestion"] = outfit

    # Step 3: Create fit card
    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = fit_card

    return session


# ---------------------------------------------------------------------------
# Manual test harness (run with: python agent.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    wardrobe = get_example_wardrobe()

    print("=" * 60)
    print("TEST 1: Happy path — vintage graphic tee")
    print("=" * 60)
    result = run_agent("vintage graphic tee", size="M", max_price=30.0, wardrobe=wardrobe)
    print(f"Selected item:      {result['selected_item']}")
    print(f"Outfit suggestion:  {result['outfit_suggestion']}")
    print(f"Fit card:           {result['fit_card']}")
    print(f"Error:              {result['error']}")

    print()
    print("=" * 60)
    print("TEST 2: No-results path — impossible query")
    print("=" * 60)
    result2 = run_agent("designer ballgown", size="XXS", max_price=5.0, wardrobe=wardrobe)
    print(f"Selected item:      {result2['selected_item']}")
    print(f"Fit card:           {result2['fit_card']}")
    print(f"Error:              {result2['error']}")
