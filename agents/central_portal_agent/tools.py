"""Multi-namespace knowledge base query tool for the Central Portal Agent.

Every department agent (citizen_inquiry_agent, tax_assistance_agent, etc.) pins
`search_knowledge_base` to its own single KB_NAMESPACE. This agent is the front
door on the main gov.lk / gic.gov.lk portal -- it doesn't know in advance which
department a citizen's question belongs to, so it fans a query out across every
configured namespace (or a caller-specified one) and deduplicates overlapping
results before returning them to the LLM.

MCP client construction stays in graph.py (matching every other agent in this
repo) -- this module only wraps the already-connected raw `search_knowledge_base`
tool into the richer `search_all_government_knowledge` tool. Which namespace(s)
actually contributed is embedded as a `namespace=` tag on each returned result
block (same shape the underlying MCP tool already uses for score/source_file/
department) -- main.py parses that back out of this turn's tool messages rather
than threading it through custom graph state, since a citizen's question can
fan out into more than one parallel tool call in a single step (e.g. one
scoped to tax-revenue, one to permits-licensing), and LangGraph only allows a
single write per state key per step unless you introduce an accumulating
reducer -- which would then leak namespaces from earlier turns into later
answers. Parsing the message content sidesteps that entirely.
"""

import asyncio
import re
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

# Matches one result block emitted by mcp_servers/pinecone_kb_mcp/server.py:
#   "[{i}] (score={score:.3f}, source_file={source_file}, department={department})\n{text}"
# blocks are joined with "\n\n" by the server, so that's the block separator here too.
_BLOCK_RE = re.compile(
    r"\[(?P<idx>\d+)\] \(score=(?P<score>[\d.]+), source_file=(?P<source_file>[^,]+), "
    r"department=(?P<department>[^)]+)\)\n(?P<text>.*?)(?=\n\n\[\d+\] \(score=|\Z)",
    re.DOTALL,
)

# Recognizes the tag this module's own combined output adds to each block --
# see _format() below -- so main.py can recover which namespaces contributed.
NAMESPACE_TAG_RE = re.compile(r"namespace=([a-z0-9-]+)")


def _extract_text(raw_result: Any) -> str:
    """Normalizes output from langchain_mcp_adapters tool execution into a clean
    string. Duplicated per-agent by convention in this repo (see e.g.
    agents/citizen_inquiry_agent/graph.py) -- no shared module exists for it."""
    if isinstance(raw_result, str):
        return raw_result

    if isinstance(raw_result, list):
        extracted = []
        for item in raw_result:
            if isinstance(item, str):
                extracted.append(item)
            elif hasattr(item, "text"):  # TextContent block
                extracted.append(item.text)
            elif isinstance(item, dict) and "text" in item:
                extracted.append(item["text"])
            else:
                extracted.append(str(item))
        return "\n".join(extracted)

    if hasattr(raw_result, "text"):
        return raw_result.text

    return str(raw_result)


def _parse_blocks(namespace: str, raw: str) -> list[dict]:
    """Split one namespace's search_knowledge_base output into individual result
    blocks so they can be deduplicated across namespaces. A "no results" response
    parses to [] rather than a false match."""
    if raw.startswith("No results found in namespace"):
        return []
    return [
        {
            "namespace": namespace,
            "score": float(m.group("score")),
            "source_file": m.group("source_file").strip(),
            "department": m.group("department").strip(),
            "text": m.group("text").strip(),
        }
        for m in _BLOCK_RE.finditer(raw)
    ]


def _dedupe(blocks: list[dict]) -> list[dict]:
    """The same source document can legitimately appear in more than one
    namespace's top-k (or, if a citizen's question is broad, be relevant from
    multiple angles). Keep only the highest-scoring occurrence per source_file,
    then rank everything by score."""
    best: dict[str, dict] = {}
    for b in blocks:
        existing = best.get(b["source_file"])
        if existing is None or b["score"] > existing["score"]:
            best[b["source_file"]] = b
    return sorted(best.values(), key=lambda b: b["score"], reverse=True)


def _format(deduped: list[dict], namespaces_searched: list[str], query: str) -> str:
    if not deduped:
        return f"No results found in any of [{', '.join(namespaces_searched)}] for query: {query}"
    return "\n\n".join(
        f"[{i}] (namespace={b['namespace']}, score={b['score']:.3f}, "
        f"source_file={b['source_file']}, department={b['department']})\n{b['text']}"
        for i, b in enumerate(deduped, start=1)
    )


class SearchAllGovernmentKnowledgeArgs(BaseModel):
    query: str = Field(description="The citizen's question, or a clarified version of it.")
    department_filter: str = Field(
        default="all",
        description=(
            "One of the configured department namespaces to search only that department, or "
            "'all' (default) to search every department at once. Use 'all' unless the "
            "citizen's question clearly names or obviously belongs to a single department."
        ),
    )


def build_search_all_government_knowledge_tool(
    raw_kb_tool: BaseTool, all_namespaces: list[str], min_relevance_score: float = 0.4
) -> BaseTool:
    """Wrap the raw pinecone-kb MCP `search_knowledge_base` tool (already
    connected by graph.py) into `search_all_government_knowledge`.

    min_relevance_score only applies when fanning out across every namespace
    (department_filter="all"): Pinecone's top_k query has no relevance cutoff
    of its own, so an unrelated namespace always returns *some* nearest
    neighbor even when nothing there is actually relevant (e.g. querying
    "business license fees" still gets a top match in social-services --
    just a weak one). Without a floor, that noise would pollute both the
    LLM's context and contributing_namespaces. A single explicitly-scoped
    namespace (department_filter=<name>) is trusted as-is and never filtered
    by score -- that department was deliberately chosen, so it should return
    whatever it has.
    """

    async def _search_one(namespace: str, query: str, top_k: int) -> list[dict]:
        raw_result = await raw_kb_tool.ainvoke({"namespace": namespace, "query": query, "top_k": top_k})
        return _parse_blocks(namespace, _extract_text(raw_result))

    async def _search_all(query: str, department_filter: str = "all") -> str:
        is_fan_out = department_filter in (None, "", "all")
        namespaces = all_namespaces if is_fan_out else [department_filter]
        invalid = [n for n in namespaces if n not in all_namespaces]
        if invalid:
            return (
                f"'{department_filter}' is not a recognized department namespace. "
                f"Known departments: {', '.join(all_namespaces)}."
            )

        results_per_namespace = await asyncio.gather(*(_search_one(ns, query, 5) for ns in namespaces))
        blocks = [block for result in results_per_namespace for block in result]
        if is_fan_out:
            blocks = [b for b in blocks if b["score"] >= min_relevance_score]
        deduped = _dedupe(blocks)
        return _format(deduped, namespaces, query)

    return StructuredTool.from_function(
        coroutine=_search_all,
        name="search_all_government_knowledge",
        description=(
            "Search the Sri Lankan government knowledge base for a citizen's question. "
            f"Configured department namespaces: {', '.join(all_namespaces)}."
        ),
        args_schema=SearchAllGovernmentKnowledgeArgs,
    )
