"""caw (coding-agent-wrapper) judge backend: CLI coding agents as judge models.

Model strings look like "caw:<provider>:<model>", e.g. "caw:codex:gpt-5.3-codex"
or "caw:claude_code:opus". The judge tools (grep_docs / read_section) are served
to the CLI agent over caw's built-in MCP tool server, so caw judges see the docs
exactly the way API judges do.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple

from caw import Agent as CawAgent, ToolGroup, ToolKit, tool

from codewikibench.tools.docs_grep import DocsGrep, format_grep_results, format_read_sections

CAW_PREFIX = "caw:"
CAW_PROVIDERS = ("claude_code", "codex")


def is_caw_model(model: Optional[str]) -> bool:
    return bool(model) and model.startswith(CAW_PREFIX)


def parse_caw_model(model: str) -> Tuple[str, str]:
    """'caw:codex:gpt-5.3-codex' -> ('codex', 'gpt-5.3-codex')."""
    parts = model.split(":", 2)
    if len(parts) != 3 or not parts[1] or not parts[2]:
        raise ValueError(
            f"Invalid caw model '{model}'. Expected 'caw:<provider>:<model>', "
            f"e.g. 'caw:codex:gpt-5.3-codex'"
        )
    provider = parts[1]
    if provider not in CAW_PROVIDERS:
        raise ValueError(
            f"Unknown caw provider '{provider}'. Supported: {', '.join(CAW_PROVIDERS)}"
        )
    return provider, parts[2]


class DocsJudgeToolKit(ToolKit, server_name="docs_judge", display_name="Docs Judge Tools"):
    """Same grep_docs/read_section tools the pydantic-ai judge uses, over MCP."""

    def __init__(self, docs_grep: DocsGrep):
        self.docs_grep = docs_grep

    @tool(
        name="grep_docs",
        description=(
            "Case-insensitive regex search over the FULL documentation text. "
            "Returns match counts, section locations, and snippets. "
            "Pass multiple keyword variants in one call."
        ),
    )
    def grep_docs(self, patterns: List[str]) -> str:
        return format_grep_results(self.docs_grep, patterns)

    @tool(
        name="read_section",
        description=(
            "Read the full text of documentation sections by section id "
            "(ids come from grep_docs results)."
        ),
    )
    def read_section(self, section_ids: List[int]) -> str:
        return format_read_sections(self.docs_grep, section_ids)


@dataclass
class CawJudge:
    """Per-run judge config. A fresh CawAgent is built for every completion:
    MCP server handles are started/stopped per session and cannot be shared
    across concurrent sessions. The ToolKit instance itself is safe to share
    (as_server() creates a new handle each time; DocsGrep is read-only)."""

    provider: str
    model: str
    system_prompt: str
    toolkit: Optional[DocsJudgeToolKit] = None

    def _completion_sync(self, prompt: str):
        kwargs = dict(
            provider=self.provider,
            model=self.model,
            system_prompt=self.system_prompt,
            tools=ToolGroup.READER,
        )
        if self.toolkit is not None:
            kwargs["tool_servers"] = [self.toolkit]
        agent = CawAgent(**kwargs)
        return agent.completion(prompt)

    async def run(self, prompt: str) -> Tuple[str, int, int]:
        """Returns (final_text, input_tokens, output_tokens)."""
        traj = await asyncio.to_thread(self._completion_sync, prompt)
        if traj.usage_limited:
            raise RuntimeError(
                f"caw usage_limited (rate limit) for {self.provider}:{self.model}"
            )
        usage = traj.usage
        return traj.result or "", usage.input_tokens, usage.output_tokens
