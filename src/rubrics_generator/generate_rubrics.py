import json
import asyncio
import argparse
import os
from pathlib import Path

from pydantic_ai import Agent

from codewikibench.utils import get_llm, run_llm_natively
from codewikibench import config
from codewikibench.tools import AgentDeps, docs_navigator_tool
from codewikibench.rubrics_generator.visualize_rubrics import visualize_rubrics

def parse_args():
    parser = argparse.ArgumentParser(description="Generate hierarchical rubrics from documentation")
    parser.add_argument("--repo-name", required=True, help="Name of the repository")
    parser.add_argument("--use-tools", action="store_true", help="Enable tools for document navigation")
    parser.add_argument("--model", help="Model to use (default: claude-3-5-haiku-20241022 for anthropic, deepseek-r1-0528 for fireworks, gemini-2.0-flash for google). caw:<claude_code|codex>:<model> runs a CLI coding agent via caw")
    parser.add_argument("--language-agnostic", action="store_true", default=False,
                        help="Ask for feature/behaviour rubrics that are independent of the implementation language (default: off)")

    return parser.parse_args()



# --- Agent ---
SYSTEM_PROMPT = """
You are a helpful assistant tasked with analyzing the official documentation of a software repository. You will be given a documentation tree and access to individual documentation files. The documentation outlines the core features and purpose of the repository, though some sections may contain redundant or non-essential information — ignore these.

<REQUIREMENTS>
Your goal is to construct a **hierarchical rubrics** of the repository. This rubrics should:

- Start from abstract, high-level rubrics and progressively drill down into more specific subrubrics.
- Cover all major functionalities and architectural constructs.
- Be structured to help users clearly understand how the repository is organized and how its components systematically work together.

Each rubric must include:
- A **descriptive name**
- A **clear explanation** of its purpose
- A **weight** representing its importance:
  - **3**: Essential
  - **2**: Important but not essential
  - **1**: Supportive or minor
- A list of **reference paths** to the documentation that supports the rubric (only required for **leaf rubrics**).

Use the following JSON format to represent the rubrics:
```json
[
  {
    "name": "Rubric 1",
    "description": "High-level purpose of Rubric 1",
    "reference": [],
    "weight": 3,
    "children": [
      {
        "name": "Rubric 1.1",
        "description": "Specific functionality under Rubric 1",
        "reference": [],
        "weight": 2,
        "children": [
          {
            "name": "Rubric 1.1.1",
            "description": "Leaf-level functionality",
            "weight": 3,
            "reference": ["ref_path_1", "ref_path_2"]
          }
        ]
      },
      {
        "name": "Rubric 1.2",
        "description": "Another function under Rubric 1",
        "weight": 1,
        "reference": ["ref_path_3"]
      }
    ]
  },
  {
    "name": "Rubric 2",
    "description": "High-level purpose of Rubric 2",
    "weight": 2,
    "reference": [],
    "children": [
      {
        "name": "Rubric 2.1",
        "description": "Functionality under Rubric 2",
        "weight": 2,
        "reference": ["ref_path_4"]
      }
    ]
  }
]
```

</REQUIREMENTS>

<GUIDELINES>
- Prioritize accessing documentation files that are **critical for understanding** the system's structure and behavior.
- Build the rubrics **iteratively**, updating and refining it as more information is gathered.
</GUIDELINES>
""".strip()

SYSTEM_PROMPT_WO_TOOLS = """
You are a skilled technical assistant assigned to analyze the official documentation of a software repository.
You will be provided with a documentation tree written primarily in a **HOW-TO-USE** format, which focuses on how to operate the repository's features and tools.
Your task is to **reverse-engineer and reconstruct the internal structure and logic of the system** by transforming this HOW-TO-USE information into a **HOW-DOES-IT-WORK** perspective.

# OBJECTIVE
Develop a **hierarchical rubric** that captures the underlying architecture and working principles of the repository. This rubric should reflect **what the system does and how its parts interact**, abstracting away from usage instructions into architectural insight.

# DELIVERABLE FORMAT
Return the rubrics in the following **nested JSON format**, where:
- Each rubric item includes a `"requirements"` field summarizing the system concept or functionality.
- Each item is assigned a `"weight"` to indicate its importance:
  - **3** = Essential to the system's core functionality
  - **2** = Important but not core
  - **1** = Minor or supporting functionality
- Items can recursively contain `"sub_tasks"` that break down more specific elements.

```json
[
  {
    "requirements": "Top-level concept or component",
    "weight": 3,
    "sub_tasks": [
      {
        "requirements": "More specific concept or subcomponent",
        "weight": 2,
        "sub_tasks": [
          {
            "requirements": "Detailed technical element or behavior",
            "weight": 3,
            "sub_tasks": [
              {
                "requirements": "Leaf-level functionality",
                "weight": 3
              },
              {
                "requirements": "More specific concept or subcomponent",
                "weight": 3,
                "sub_tasks": [
                  {
                    "requirements": "Leaf-level functionality",
                    "weight": 3,
                    "sub_tasks": [...] # dive deeper into the functionality
                  }
                ]
              }
            ]
          }
        ]
      },
      {
        "requirements": "Alternative aspect or feature",
        "weight": 1
      }
    ]
  }
]
```

# REQUIREMENTS
- Begin with **abstract, high-level components**, then drill down to concrete sub-elements.
- Structure the rubric to support **deep understanding** of the system's architecture and internal logic.
- If needed, refine the rubric **iteratively** as more parts of the documentation are reviewed.

# NOTES
- Be analytical: DO NOT mimic the documentation structure. Instead, distill and reframe it.
- Treat the documentation as evidence from which you infer **the design intent and system structure**.
""".strip()

LANGUAGE_AGNOSTIC_BLOCK = """
<LANGUAGE-AGNOSTIC FOCUS>
IMPORTANT: This rubric will be used to evaluate documentation across different languages (e.g., C and Rust).
- Focus on **FEATURES, CAPABILITIES, and FUNCTIONALITY** rather than language-specific syntax or implementation details
- Emphasize **WHAT** the system does, not language-specific HOW
- Ensure rubrics can be fairly evaluated regardless of the implementation language
- Describe components by their role and behaviour; avoid language constructs (header files, structs, traits, macros, pointers, classes, crate/package names) unless they are part of the documented user-facing interface
</LANGUAGE-AGNOSTIC FOCUS>
""".strip()

LANGUAGE_AGNOSTIC_REQUIREMENTS = """
- Focus on **WHAT the system does** and **WHAT features it provides**, not HOW it's implemented in a specific language.
- Evaluate features and capabilities, ensuring the rubric is language-agnostic and applicable across different implementations.
""".strip()


def get_system_prompt(use_tools: bool, language_agnostic: bool = False) -> str:
    """Rubric-generation system prompt; optionally with the language-agnostic focus."""
    if use_tools:
        prompt = SYSTEM_PROMPT
        if language_agnostic:
            prompt = prompt.replace(
                "- Be structured to help users clearly understand how the repository is organized and how its components systematically work together.",
                "- Be structured to help users clearly understand how the repository is organized and how its components systematically work together.\n"
                + LANGUAGE_AGNOSTIC_REQUIREMENTS,
            )
            prompt = prompt.replace(
                "Use the following JSON format to represent the rubrics:",
                LANGUAGE_AGNOSTIC_BLOCK + "\n\nUse the following JSON format to represent the rubrics:",
            )
        return prompt
    prompt = SYSTEM_PROMPT_WO_TOOLS
    if language_agnostic:
        prompt = prompt.replace("# DELIVERABLE FORMAT", LANGUAGE_AGNOSTIC_BLOCK + "\n\n# DELIVERABLE FORMAT")
    return prompt


def normalize_rubrics(items) -> list:
    """Normalise either rubric schema to the judge schema.

    with-tools schema:   {name, description, weight, reference, children}
    without-tools schema: {requirements, weight, sub_tasks}
    -> {requirements, weight (1|2|3), sub_tasks?, reference? (leaves, when present)}
    """
    if isinstance(items, dict):
        items = items.get("rubrics", [])
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        requirements = item.get("requirements")
        if not requirements:
            name = (item.get("name") or "").strip()
            description = (item.get("description") or "").strip()
            if name and description:
                requirements = f"{name}: {description}"
            else:
                requirements = name or description
        try:
            weight = int(item.get("weight", 2))
        except (TypeError, ValueError):
            weight = 2
        weight = min(3, max(1, weight))

        out = {"requirements": requirements, "weight": weight}
        children = item.get("sub_tasks") or item.get("children") or []
        sub_tasks = normalize_rubrics(children) if children else []
        if sub_tasks:
            out["sub_tasks"] = sub_tasks
        else:
            reference = item.get("reference")
            if reference:
                out["reference"] = reference if isinstance(reference, list) else [reference]
        normalized.append(out)
    return normalized


def extract_rubrics_json(final_output: str):
    """Extract the rubric list from an LLM response. Returns a list or raises ValueError."""
    final_output = final_output or ""
    json_start = final_output.find('[')
    json_end = final_output.rfind(']') + 1
    if json_start != -1 and json_end > json_start:
        try:
            parsed = json.loads(final_output[json_start:json_end])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    # the model may have wrapped the list in {"rubrics": [...]}
    obj_start = final_output.find('{')
    obj_end = final_output.rfind('}') + 1
    if obj_start != -1 and obj_end > obj_start:
        try:
            parsed = json.loads(final_output[obj_start:obj_end])
            if isinstance(parsed, dict) and isinstance(parsed.get("rubrics"), list):
                return parsed["rubrics"]
        except json.JSONDecodeError:
            pass
    raise ValueError("No valid JSON rubrics found in output")


async def generate_rubrics_raw(docs_path: str, model: str = None, use_tools: bool = False,
                               language_agnostic: bool = False) -> str:
    """Run one rubric-generation pass over the parsed docs in `docs_path`; returns raw model text."""
    with open(os.path.join(docs_path, "docs_tree.json"), "r") as f:
        docs_tree = json.load(f)

    prompt = f"""
Given the docs tree:
\"\"\"
{json.dumps(docs_tree, indent=2)}
\"\"\"
""".strip()

    system_prompt = get_system_prompt(use_tools, language_agnostic)
    deps = AgentDeps(docs_path)

    if model and model.startswith("caw:"):
        # CLI coding agent (claude code / codex) via caw; lazy import (optional dep)
        from codewikibench.judge.caw_backend import CawRunner, DocsNavigatorToolKit, parse_caw_model
        provider, caw_model = parse_caw_model(model)
        toolkit = DocsNavigatorToolKit(deps.docs_navigator) if use_tools else None
        if use_tools:
            prompt += "\n\nUse the `docs_navigator` tool to read the documentation content. Return ONLY the JSON rubric list as your final answer."
        else:
            prompt += "\n\nReturn ONLY the JSON rubric list as your final answer."
        runner = CawRunner(provider=provider, model=caw_model, system_prompt=system_prompt, toolkit=toolkit)
        text, _, _ = await runner.run(prompt)
        return text

    tools = [docs_navigator_tool] if use_tools else []
    agent = Agent(
        model=get_llm(model),
        deps_type=AgentDeps,
        system_prompt=system_prompt,
        tools=tools,
    )
    final_output = await agent.run(prompt, deps=deps)
    return final_output.output


# --- Run ---
async def run(args):
    # Setup paths automatically from repo name
    base_path = config.get_data_path(args.repo_name)
    docs_path = os.path.join(base_path, "original")
    docs_tree_path = os.path.join(docs_path, "docs_tree.json")
    output_dir = os.path.join(base_path, "rubrics")
    sanitized_model = args.model.replace("/", "_").replace(":", "_") if args.model else "default"

    #check if output file already exists
    if os.path.exists(os.path.join(output_dir, f"{sanitized_model}.json")):
        print(f"Rubrics already generated for {args.model}")
        return
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    final_output = await generate_rubrics_raw(
        docs_path, args.model, use_tools=args.use_tools, language_agnostic=args.language_agnostic
    )
    
    # Parse and save rubrics
    try:
        # Extract JSON from the final output
        json_start = final_output.find('[')
        json_end = final_output.rfind(']') + 1
        
        if json_start != -1 and json_end > json_start:
            rubrics_json = final_output[json_start:json_end]
            rubrics = json.loads(rubrics_json)
            
            # Save rubrics to file
            rubrics_file = os.path.join(output_dir, f"{sanitized_model}.json")
            with open(rubrics_file, "w") as f:
                json.dump(rubrics, f, indent=2)
            
            print(f"Rubrics saved to: {rubrics_file}")
            # visualize rubrics
            visualize_rubrics(rubrics_file)
        else:
            print("No valid JSON rubrics found in output")
            # Save raw output for debugging
            raw_output_file = os.path.join(output_dir, f"{sanitized_model}_raw_output.txt")
            with open(raw_output_file, "w") as f:
                f.write(final_output)
            print(f"Raw output saved to: {raw_output_file}")
            
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        # Save raw output for debugging
        raw_output_file = os.path.join(output_dir, f"{sanitized_model}_raw_output.txt")
        with open(raw_output_file, "w") as f:
            f.write(final_output)
        print(f"Raw output saved to: {raw_output_file}")

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args))


