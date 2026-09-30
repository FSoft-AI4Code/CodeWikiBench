"""caw (coding-agent-wrapper) judge backend: CLI coding agents as judge models.

Model strings look like "caw:<provider>:<model>", e.g. "caw:codex:gpt-5.3-codex"
or "caw:claude_code:opus". The judge tools (grep_docs / read_section) are served
to the CLI agent over caw's built-in MCP tool server, so caw judges see the docs
exactly the way API judges do.
"""

import asyncio
from dataclasses import dataclass
import json
from typing import Any, List, Optional, Tuple, Union

from caw import Agent as CawAgent, ToolGroup, ToolKit, tool

from codewikibench.tools.docs_grep import DocsGrep, format_grep_results, format_read_sections
from codewikibench.tools.docs_navigator import DocsNavigator
from codewikibench.utils import truncate_tokens

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


class DocsNavigatorToolKit(ToolKit, server_name="docs_navigator", display_name="Docs Navigator Tools"):
    """The docs_navigator tool used by the pydantic-ai rubric generator, over MCP."""

    def __init__(self, docs_navigator: DocsNavigator):
        self.docs_navigator = docs_navigator

    @tool(
        name="docs_navigator",
        description=(
            "Navigate the documentation tree and return the content at the given paths. "
            "`paths` is a list of paths; each path is a list of keys/indices from the docs "
            "tree, e.g. [['subpages', 2, 'subpages', 0, 'content', 'Getting Started']]."
        ),
    )
    def docs_navigator_tool(self, paths: List[List[Union[str, int]]]) -> str:
        formatted_results = ""
        for path in paths:
            try:
                result = self.docs_navigator.get_content(path)
                content = result.get("content") if isinstance(result, dict) else result
            except Exception as e:  # surface bad paths to the agent instead of failing the call
                content = f"[error navigating {path}: {e}]"
            formatted_results += "--------------------------------\n"
            formatted_results += f"Path: {path}\n"
            formatted_results += f"Content: \n{json.dumps(content, indent=2)}\n"
            formatted_results += "--------------------------------\n"
        return truncate_tokens(formatted_results)


@dataclass
class CawJudge:
    """Per-run judge config. A fresh CawAgent is built for every completion:
    MCP server handles are started/stopped per session and cannot be shared
    across concurrent sessions. The ToolKit instance itself is safe to share
    (as_server() creates a new handle each time; DocsGrep is read-only)."""

    provider: str
    model: str
    system_prompt: str
    toolkit: Optional[ToolKit] = None  # any caw ToolKit (DocsJudgeToolKit, DocsNavigatorToolKit, ...)

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


# Generic name: the same runner is used for rubric generation / combination.
CawRunner = CawJudge
