"""List the Gemini models your API key can use for content generation.

Run from the repo root:

    python -m src.list_models

Useful when you hit a 404 "model no longer available" error - it shows the
exact model IDs to put in the Streamlit sidebar or in DEFAULT_MODEL.
"""

from src.rag import build_client, has_api_key, load_env


def main() -> None:
    load_env()
    if not has_api_key():
        print("No GEMINI_API_KEY found. Set it in .env or your shell first.")
        return

    client = build_client()
    print("Models that support generateContent:\n")
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if "generateContent" in actions:
            print(f"  {model.name}")


if __name__ == "__main__":
    main()
