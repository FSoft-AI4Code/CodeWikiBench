import json
import re
from typing import Any, Dict, List

from pydantic_ai import RunContext, Tool

from codewikibench.utils import truncate_tokens


class DocsGrep:
    """
    Full-text search over structured_docs.json.

    The docs are flattened into "sections": every leaf string in the
    structured docs gets an integer id and a breadcrumb built from the
    page titles and headings above it. Agents grep for keywords to find
    sections, then read full sections by id.
    """

    def __init__(self, structured_docs_path: str):
        with open(structured_docs_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        self.sections: List[Dict[str, Any]] = []
        self._index_page(docs, [])

    def _index_page(self, page: Dict[str, Any], crumbs: List[str]):
        title = page.get("title", "")
        page_crumbs = crumbs + [title] if title else crumbs

        if page.get("content") is not None:
            self._index_content(page["content"], page_crumbs)

        for subpage in page.get("subpages") or []:
            self._index_page(subpage, page_crumbs)

    def _index_content(self, node: Any, crumbs: List[str]):
        if isinstance(node, dict):
            for heading, value in node.items():
                self._index_content(value, crumbs + [str(heading)])
        elif isinstance(node, list):
            for item in node:
                self._index_content(item, crumbs)
        elif isinstance(node, str) and node.strip() and node != "<detail_content>":
            self.sections.append({
                "id": len(self.sections),
                "breadcrumb": " > ".join(crumbs),
                "text": node,
            })

    def grep(self, pattern: str, max_results: int = 10, context_chars: int = 300) -> Dict[str, Any]:
        """
        Case-insensitive regex search across all sections.

        Returns total match count and up to max_results sections, each with
        a snippet of context_chars around the first match in that section.
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"pattern": pattern, "error": f"Invalid regex: {e}"}

        total_matches = 0
        hits = []

        for section in self.sections:
            matches = list(regex.finditer(section["text"]))
            if not matches:
                continue
            total_matches += len(matches)
            hits.append((section, matches))

        # Sections with the most matches first: real coverage beats passing mentions
        hits.sort(key=lambda h: len(h[1]), reverse=True)

        matched_sections = []
        for section, matches in hits[:max_results]:
            m = matches[0]
            start = max(0, m.start() - context_chars)
            end = min(len(section["text"]), m.end() + context_chars)
            snippet = section["text"][start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(section["text"]):
                snippet = snippet + "..."
            matched_sections.append({
                "section_id": section["id"],
                "breadcrumb": section["breadcrumb"],
                "matches_in_section": len(matches),
                "snippet": snippet,
            })

        return {
            "pattern": pattern,
            "total_matches": total_matches,
            "sections_shown": len(matched_sections),
            "sections": matched_sections,
        }

    def read(self, section_id: int) -> Dict[str, Any]:
        """Return the full text of a section by id."""
        if not isinstance(section_id, int) or not (0 <= section_id < len(self.sections)):
            return {"error": f"Invalid section_id {section_id}. Valid range: 0-{len(self.sections) - 1}"}
        return self.sections[section_id]


def format_grep_results(docs_grep: DocsGrep, patterns: List[str]) -> str:
    results = ""
    for pattern in patterns:
        hit = docs_grep.grep(pattern)
        results += "--------------------------------\n"
        if "error" in hit:
            results += f'Pattern "{pattern}": {hit["error"]}\n'
            continue
        results += f'Pattern "{pattern}": {hit["total_matches"]} matches'
        if hit["total_matches"] == 0:
            results += " (not found anywhere in the documentation)\n"
            continue
        results += f', showing {hit["sections_shown"]} sections:\n'
        for sec in hit["sections"]:
            results += f'\n[section {sec["section_id"]}] {sec["breadcrumb"]} ({sec["matches_in_section"]} matches)\n'
            results += f'{sec["snippet"]}\n'
    results += "--------------------------------\n"
    return truncate_tokens(results)


def format_read_sections(docs_grep: DocsGrep, section_ids: List[int]) -> str:
    results = ""
    for section_id in section_ids:
        section = docs_grep.read(section_id)
        results += "--------------------------------\n"
        if "error" in section:
            results += f'{section["error"]}\n'
            continue
        results += f'[section {section["id"]}] {section["breadcrumb"]}\n{section["text"]}\n'
    results += "--------------------------------\n"
    return truncate_tokens(results)


async def run_grep_docs(ctx: RunContext, patterns: List[str]) -> str:
    """
    Search the full documentation text for regex patterns (case-insensitive).

    Args:
        patterns: List of regex patterns to search for. Pass several variants of the
                  same concept in one call (e.g. ["ELO", "rating", "opponent select"]).
                  Plain words work as patterns; use "\\b" for word boundaries if needed.
    """
    return format_grep_results(ctx.deps.docs_grep, patterns)


async def run_read_section(ctx: RunContext, section_ids: List[int]) -> str:
    """
    Read the full text of documentation sections found via grep_docs.

    Args:
        section_ids: List of section ids (from grep_docs results) to read in full.
    """
    return format_read_sections(ctx.deps.docs_grep, section_ids)


grep_docs_tool = Tool(
    name="grep_docs",
    description=(
        "Case-insensitive regex search over the FULL documentation text. "
        "Returns match counts, section locations, and snippets. "
        "Pass multiple keyword variants in one call."
    ),
    function=run_grep_docs,
    takes_ctx=True,
)

read_section_tool = Tool(
    name="read_section",
    description="Read the full text of documentation sections by section id (ids come from grep_docs results).",
    function=run_read_section,
    takes_ctx=True,
)
