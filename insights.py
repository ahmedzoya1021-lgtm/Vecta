"""
Generates plain-English "geopolitical context" summaries for a stock using
Claude. This is informational context, not investment advice — the prompt
below deliberately asks Claude to inform, not recommend buying/selling.
"""
import os
from anthropic import Anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        _client = Anthropic(api_key=api_key)
    return _client


def _extract_summary_and_sources(message):
    # The final answer can be split across multiple text blocks if Claude
    # pauses mid-sentence to search again. So: find the last search-result
    # block, then join every text block that comes AFTER it — that's the
    # complete final answer. Text blocks before it are just Claude thinking
    # out loud before searching, which we discard.
    last_search_index = max(
        (i for i, b in enumerate(message.content) if b.type == "web_search_tool_result"),
        default=-1,
    )
    text_blocks = [
        block.text
        for i, block in enumerate(message.content)
        if block.type == "text" and i > last_search_index
    ]
    summary = "".join(text_blocks)
    sources = [
        {"title": r.title, "url": r.url}
        for block in message.content
        if block.type == "web_search_tool_result"
        and isinstance(block.content, list)
        for r in block.content
        if r.type == "web_search_result"
    ]
    return summary, sources


def _no_key_response():
    return {
        "available": False,
        "summary": "No ANTHROPIC_API_KEY configured yet. Add one in your .env file to enable live AI insights.",
    }


def get_geopolitical_context(symbol, company_name=None):
    client = _get_client()
    if client is None:
        return _no_key_response()

    name = company_name or symbol
    prompt = f"""Search for current news (last 1-2 weeks) relevant to {name} (ticker: {symbol})
that a retail investor would want context on: geopolitical events, trade/regulatory
actions, supply chain news, or major company-specific developments.

Rules:
- Do exactly ONE search, then answer from those results. Do not search again even if the
  results feel incomplete — summarize what you got.
- Base the summary on what you actually find via search, not general knowledge.
- Do NOT tell the reader to buy, sell, or hold. Present information only, not a recommendation.
- If search turns up nothing notable and recent, say so plainly instead of padding with generic background.
- Your final message must contain ONLY the summary itself: 2-3 sentences, plain English,
  no jargon, no markdown formatting, no headers, no meta-commentary about your process or
  the search results, no preamble like "Based on the search results" or "Here's what I found."
  Just the 2-3 sentences a reader would see."""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 1}],
        messages=[{"role": "user", "content": prompt}],
    )
    summary, sources = _extract_summary_and_sources(message)
    return {"available": True, "summary": summary, "sources": sources}


def get_portfolio_briefing(holdings):
    """holdings: list of {symbol, weight_pct} — weight_pct is what share of
    the total portfolio value that holding represents, e.g. 42.5."""
    client = _get_client()
    if client is None:
        return _no_key_response()

    holdings_list = "\n".join(
        f"- {h['symbol']}: {h['weight_pct']:.0f}% of portfolio" for h in holdings
    )

    prompt = f"""A retail investor holds this portfolio:
{holdings_list}

Search for current news relevant to this SPECIFIC combination of holdings — not
each stock in isolation. Look especially for:
- Concentration risk (e.g. multiple holdings in the same sector or supply chain)
- A current event or trend that affects several of these holdings at once
- Any single holding that dominates the portfolio and carries outsized risk

Rules:
- Do exactly ONE search covering the whole portfolio (e.g. search for the tickers together,
  or for the shared theme you suspect connects them), then answer from those results. Do not
  search again even if the results feel incomplete — summarize what you got.
- Do NOT tell the reader to buy, sell, or hold, or to rebalance. Present information only.
- If nothing notable connects these holdings beyond the obvious, say so plainly.
- Your final message must contain ONLY the summary itself: 3-5 sentences, plain English,
  no jargon, no markdown formatting, no headers, no meta-commentary about your process,
  no preamble like "Based on the search results." Just the sentences a reader would see."""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1536,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 1}],
        messages=[{"role": "user", "content": prompt}],
    )
    summary, sources = _extract_summary_and_sources(message)
    return {"available": True, "summary": summary, "sources": sources}
