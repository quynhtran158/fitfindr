"""
FitFindr Gradio app — UI for the multi-tool AI agent.
"""

import gradio as gr
from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def handle_query(
    description: str,
    size: str,
    max_price: str,
    use_example_wardrobe: bool,
) -> tuple[str, str, str]:
    """Run the agent and return text for each of the three output panels.

    Args:
        description (str): Item description from the user.
        size (str): Size input ("Any" means no filter).
        max_price (str): Max price as string (empty means no filter).
        use_example_wardrobe (bool): Whether to use the example wardrobe.

    Returns:
        tuple[str, str, str]: (search_results_text, outfit_suggestion_text, fit_card_text)
    """
    # Validate inputs
    if not description.strip():
        return "Please enter an item description.", "", ""

    size_val = None if size.strip().lower() in ("", "any") else size.strip()

    max_price_val = None
    if max_price.strip():
        try:
            max_price_val = float(max_price.strip().replace("$", ""))
        except ValueError:
            return "Invalid max price — please enter a number (e.g. 30).", "", ""

    wardrobe = get_example_wardrobe() if use_example_wardrobe else get_empty_wardrobe()

    # Run the planning loop
    session = run_agent(
        description=description.strip(),
        size=size_val,
        max_price=max_price_val,
        wardrobe=wardrobe,
    )

    # Build search results panel
    if session["error"] and not session["all_results"]:
        search_text = f"⚠️ {session['error']}"
    elif session["all_results"]:
        lines = [f"Found {len(session['all_results'])} result(s). Top pick:\n"]
        item = session["selected_item"]
        lines.append(f"**{item['title']}**")
        lines.append(f"Price: ${item['price']:.0f}  |  Size: {item['size']}  |  Platform: {item['platform']}")
        lines.append(f"Condition: {item['condition']}")
        lines.append(f"Style tags: {', '.join(item.get('style_tags', []))}")
        lines.append(f"Colors: {', '.join(item.get('colors', []))}")
        if len(session["all_results"]) > 1:
            lines.append(f"\nOther matches: " + ", ".join(
                r["title"] for r in session["all_results"][1:4]
            ))
        search_text = "\n".join(lines)
    else:
        search_text = "No results."

    # Build outfit suggestion panel
    if session["outfit_suggestion"]:
        outfit_text = session["outfit_suggestion"]
    elif session["error"] and session["selected_item"]:
        outfit_text = f"⚠️ {session['error']}"
    else:
        outfit_text = ""

    # Build fit card panel
    if session["fit_card"]:
        fit_card_text = session["fit_card"]
    else:
        fit_card_text = ""

    return search_text, outfit_text, fit_card_text


# ---------------------------------------------------------------------------
# Gradio layout
# ---------------------------------------------------------------------------
with gr.Blocks(title="FitFindr") as demo:
    gr.Markdown(
        """
        # 👗 FitFindr
        ### Find secondhand pieces and get AI-powered outfit suggestions.
        Describe what you're looking for, optionally filter by size and price,
        then let the agent search listings, style the find, and generate a shareable fit card.
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            description_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee, cropped moto jacket, 90s slip dress",
                lines=2,
            )
        with gr.Column(scale=1):
            size_input = gr.Textbox(
                label="Size (optional)",
                placeholder="S, M, L, XS — or leave blank for any",
            )
            max_price_input = gr.Textbox(
                label="Max price (optional)",
                placeholder="e.g. 30",
            )

    wardrobe_toggle = gr.Checkbox(
        label="Use example wardrobe (baggy jeans, chunky boots, white tank, oversized hoodie)",
        value=True,
    )

    run_btn = gr.Button("Find My Fit ✨", variant="primary")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🔍 Search Results")
            search_output = gr.Markdown()
        with gr.Column():
            gr.Markdown("### 👚 Outfit Suggestion")
            outfit_output = gr.Markdown()
        with gr.Column():
            gr.Markdown("### 📱 Fit Card")
            fit_card_output = gr.Markdown()

    run_btn.click(
        fn=handle_query,
        inputs=[description_input, size_input, max_price_input, wardrobe_toggle],
        outputs=[search_output, outfit_output, fit_card_output],
    )

    gr.Examples(
        examples=[
            ["vintage graphic tee", "M", "30", True],
            ["cropped moto jacket", "M", "", True],
            ["90s slip dress", "S", "50", False],
            ["designer ballgown", "XXS", "5", True],
        ],
        inputs=[description_input, size_input, max_price_input, wardrobe_toggle],
    )


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
