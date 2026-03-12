#!/usr/bin/env python3
"""CLI tool to search for Porsche Cayenne listings via the Anthropic web search API."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

# Import the system prompt and preset queries from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import SYSTEM_PROMPT, SEARCH_PRESETS


def search(api_key, query, max_uses=10):
    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 8000,
        "system": SYSTEM_PROMPT,
        "tools": [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}
        ],
        "messages": [
            {"role": "user", "content": query + "\n\nRemember: respond with ONLY a raw JSON array. No markdown, no commentary, no apologies. Start your response with [ and end with ]."}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def extract_text(data):
    return "\n\n".join(
        block["text"]
        for block in data.get("content", [])
        if block.get("type") == "text"
    )


def extract_sources(data):
    sources = []
    for block in data.get("content", []):
        if block.get("type") in ("web_search_tool_result", "server_tool_use"):
            for item in block.get("content", []):
                if item.get("type") == "web_search_result":
                    sources.append({"title": item.get("title", ""), "url": item.get("url", "")})
    return sources


def list_presets():
    print("Available presets:")
    for i, preset in enumerate(SEARCH_PRESETS):
        if preset["query"]:
            print(f"  {i}: {preset['label']}")


def main():
    parser = argparse.ArgumentParser(description="Cayenne Finder CLI")
    parser.add_argument("query", nargs="?", help="Search query (or preset number)")
    parser.add_argument("--preset", "-p", type=int, help="Use a preset query by number")
    parser.add_argument("--list-presets", "-l", action="store_true", help="List available presets")
    parser.add_argument("--max-uses", "-m", type=int, default=10, help="Max web searches (default: 10)")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON response")
    args = parser.parse_args()

    if args.list_presets:
        list_presets()
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Error: Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    # Determine query
    if args.preset is not None:
        if args.preset < 0 or args.preset >= len(SEARCH_PRESETS) or not SEARCH_PRESETS[args.preset]["query"]:
            print(f"Error: Invalid preset number. Use --list-presets to see options.", file=sys.stderr)
            sys.exit(1)
        query = SEARCH_PRESETS[args.preset]["query"]
        print(f"Using preset: {SEARCH_PRESETS[args.preset]['label']}", file=sys.stderr)
    elif args.query:
        query = args.query
    else:
        parser.print_help()
        sys.exit(1)

    print("Searching...", file=sys.stderr)

    try:
        data = search(api_key, query, args.max_uses)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"API error ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    text = extract_text(data)
    sources = extract_sources(data)

    print(text)

    if sources:
        print("\n--- Sources ---")
        seen = set()
        for src in sources:
            if src["url"] not in seen:
                seen.add(src["url"])
                print(f"  {src['title'] or src['url']}")
                print(f"  {src['url']}")


if __name__ == "__main__":
    main()
