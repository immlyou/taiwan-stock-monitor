"""
Example: Anthropic Claude tool use with taiwan-stock-monitor.

Loads tool_catalog.json, hands it to Claude as tools, and dispatches
tool calls to the Railway REST backend.

Run:
    pip install anthropic requests
    export ANTHROPIC_API_KEY=sk-ant-...
    python anthropic_tool_use.py
"""
import json
import os
import sys
from pathlib import Path


try:
    import anthropic
except ImportError:
    print("Install with: pip install anthropic requests")
    sys.exit(1)

# Share dispatch table with openai example
sys.path.insert(0, str(Path(__file__).resolve().parent))
from openai_function_calling import DISPATCH, dispatch, BASE, HEADERS  # noqa: E402,F401

CATALOG_PATH = Path(__file__).resolve().parent.parent / "tool_catalog.json"


def load_anthropic_tools() -> list[dict]:
    """Anthropic tool format is almost identical to MCP — no transformation needed."""
    catalog = json.loads(CATALOG_PATH.read_text())
    return [
        {
            "name": t["name"],
            "description": t["description"].strip(),
            "input_schema": t["input_schema"],
        }
        for t in catalog["tools"]
    ]


def main() -> int:
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Set ANTHROPIC_API_KEY to run this example.")
        return 1

    client = anthropic.Anthropic()
    tools = load_anthropic_tools()
    print(f"Loaded {len(tools)} tools from catalog.\n")

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Give me a quick read on the Taiwan stock market today. "
                "Include TAIEX move, top institutional money flow, "
                "and one interesting stock to watch. Reply in Traditional Chinese."
            ),
        }
    ]

    system = (
        "You are a Taiwan stock market analyst. "
        "Use the provided tools to fetch real data before answering. "
        "Keep responses concise and cite specific numbers."
    )

    # Tool-use loop
    for round_num in range(5):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Collect tool calls from this assistant turn
        tool_uses = [b for b in resp.content if b.type == "tool_use"]

        # Record assistant message with ALL content blocks
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn" or not tool_uses:
            # Final answer — extract text blocks
            final = "".join(b.text for b in resp.content if b.type == "text")
            print("=" * 60)
            print(final)
            print("=" * 60)
            return 0

        # Execute all tool calls and feed results back
        tool_results = []
        for tu in tool_uses:
            print(f"→ Calling {tu.name}({tu.input})")
            result = dispatch(tu.name, tu.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        messages.append({"role": "user", "content": tool_results})

    print("Reached max rounds without final answer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
