import json
import asyncio
import argparse
import os
from pathlib import Path
from tqdm import tqdm
import traceback
import logfire

try:
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()
except Exception as e:
    print(f"Failed to configure logfire: {e}")

from pydantic_ai import Agent
from codewikibench.tools import AgentDeps, grep_docs_tool, read_section_tool
from codewikibench.utils import get_llm, run_llm_natively
from codewikibench import config

def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate documentation against hierarchical rubrics")
    parser.add_argument("--repo-name", required=True, help="Name of the repository")
    parser.add_argument("--reference", required=True, help="Name of the folder that contains the reference documentation needed for evaluation")
    parser.add_argument("--use-tools", action="store_true", help="Enable tools for document navigation")
    parser.add_argument("--model", help="Model to use (default: claude-sonnet-4)")
    parser.add_argument("--rubrics-file", help="Path to existing rubrics file for evaluation mode")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of requirements to evaluate concurrently in each batch (default: 5)")
    parser.add_argument("--enable-retry", action="store_true", default=False, help="Enable re-evaluation of error cases (default: False)")
    parser.add_argument("--max-retries", type=int, default=2, help="Maximum number of retries for error cases (default: 2)")
    return parser.parse_args()



# --- Agent ---
EVALUATION_SYSTEM_PROMPT = """
You are a documentation evaluation expert. Your task is to evaluate whether a specific criteria is documented in the given documentation tree.

# OBJECTIVE
For each leaf-level criteria provided, determine if the documentation adequately covers that criteria using a binary evaluation (0 or 1).

# EVALUATION CRITERIA
- **1 (Documented)**: The criteria is explained, described, or mentioned in the documentation
- **0 (Not Documented)**: The criteria is not mentioned or missing from the documentation

# EVALUATION PROCESS
1. Extract the key concepts from the criteria (component names, algorithm names, feature names).
2. Use the `grep_docs` tool to search the FULL documentation text for those concepts. The documentation tree you are given shows only titles — section bodies are hidden, so NEVER decide from the tree alone.
3. Try multiple search variants before concluding something is missing: exact names ("GhostTrainer"), abbreviations ("ELO"), synonyms ("rating", "opponent"), and partial words ("determinis" matches deterministic/determinism). A concept can be documented under a different name.
4. Use the `read_section` tool to read the full text around promising matches and confirm the coverage is real, not a passing keyword hit.
5. Make a binary decision: Does the documentation mention this criteria? Consider both direct explanations and implicit coverage.
6. Only assign 0 after several different grep_docs searches (at least 3 distinct patterns) come back empty or clearly irrelevant.
7. Provide brief reasoning for your decision

# OUTPUT FORMAT
For each criteria evaluated, respond with:
```json
{
  "criteria": "The specific criteria text",
  "score": 0 or 1,
  "reasoning": "Brief explanation of why this score was assigned",
  "evidence": "Specific documentation sections or content that support the score"
}
```
""".strip()


def is_leaf_node(rubric_item):
    """Check if a rubric item is a leaf node (has no sub_tasks)"""
    return "sub_tasks" not in rubric_item or not rubric_item["sub_tasks"]

def collect_leaf_requirements(rubrics):
    """Collect all leaf-level requirements from the rubrics hierarchy"""
    leaf_requirements = []
    
    def traverse(items, path=""):
        for i, item in enumerate(items):
            current_path = f"{path}.{i}" if path else str(i)
            
            if is_leaf_node(item):
                leaf_requirements.append({
                    "requirement": item["requirements"],
                    "weight": item["weight"],
                    "path": current_path
                })
            else:
                traverse(item["sub_tasks"], current_path)
    
    traverse(rubrics)
    return leaf_requirements

async def re_evaluate_error_leaves(
    leaf_requirements, docs_tree,
    agent: Agent = None,
    deps: AgentDeps = None,
    initial_evaluations = None,
    max_retries=2,
    model: str = None,
    system_prompt: str = None,
    caw_judge=None,
    ):
    """Re-evaluate leaf requirements that had errors during initial evaluation"""
    error_leaves = []
    
    # Identify leaves that had errors
    for leaf in leaf_requirements:
        path = leaf['path']
        if path in initial_evaluations:
            evaluation = initial_evaluations[path]
            # Check if this was an error case
            if ( evaluation.get("error") or
                "[AUTOMATIC PARSING FALLBACK]".lower() in evaluation.get("reasoning", "").lower() or
                "[PARSING ERROR]".lower() in evaluation.get("reasoning", "").lower() or
                "[EVALUATION ERROR]".lower() in evaluation.get("reasoning", "").lower()):
                error_leaves.append(leaf)
    
    if not error_leaves:
        tqdm.write("No error leaves found to re-evaluate.")
        return {}
    
    tqdm.write(f"Found {len(error_leaves)} error leaves to re-evaluate:")
    for leaf in error_leaves:
        tqdm.write(f"  - {leaf['requirement'][:100]}...")
    
    re_evaluations = {}
    
    async def re_evaluate_single_requirement(leaf, retry_count=0):
        """Re-evaluate a single requirement with retry logic"""
        try:
            # Use a more explicit prompt for re-evaluation
            prompt = f"""
RETRY EVALUATION - Previous attempt failed. Please be extra careful with the JSON format.
Previous attempt:
\"\"\"
{initial_evaluations[leaf['path']]['evidence']}
\"\"\"
Got error: {initial_evaluations[leaf['path']]['reasoning']}

Evaluate this criteria against the documentation:

Criteria: "{leaf['requirement']}"

Documentation tree:
```json
{json.dumps(docs_tree, indent=2)}
```

IMPORTANT: You must respond with valid JSON in exactly this format:
{{
  "criteria": "The specific criteria text",
  "score": 0 or 1,
  "reasoning": "Brief explanation of why this score was assigned",
  "evidence": "Specific documentation sections or content that support the score"
}}

First, search the full documentation text with the `grep_docs` tool (try several keyword variants — the tree above shows titles only, the bodies are hidden). Read promising sections with `read_section` to confirm.
Then, evaluate if the criteria is mentioned.
""".strip()
            if caw_judge is not None:
                final_output, input_tokens, output_tokens = await caw_judge.run(prompt)
            elif agent is None:
                final_output = await run_llm_natively(model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}])
                input_tokens = 0  # Token counting would need to be implemented separately
                output_tokens = 0
            else:
                result = await agent.run(prompt, deps=deps)
                final_output = result.output
                input_tokens = 0  # Token counting would need to be implemented separately
                output_tokens = 0

            # More robust JSON parsing
            try:
                # Try to extract JSON more carefully
                json_start = final_output.find('{')
                json_end = final_output.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    eval_json = final_output[json_start:json_end]
                    # Clean up the JSON string
                    eval_json = eval_json.strip()
                    evaluation = json.loads(eval_json)
                    
                    # Validate the JSON structure
                    if "score" in evaluation and isinstance(evaluation["score"], int):
                        return leaf['path'], {
                            "score": evaluation.get("score", 0),
                            "reasoning": evaluation.get("reasoning", ""),
                            "evidence": evaluation.get("evidence", ""),
                            "tokens": {"input": input_tokens, "output": output_tokens},
                            "retry_count": retry_count + 1
                        }
                    else:
                        raise ValueError("Invalid JSON structure - missing or invalid score")
                else:
                    raise ValueError("No JSON found in response")
                    
            except Exception as parse_error:
                if retry_count < max_retries:
                    tqdm.write(f"!! Retry {retry_count + 1} failed for {leaf['requirement'][:50]}: {parse_error} !!")
                    await asyncio.sleep(2)  # Wait before retry
                    return await re_evaluate_single_requirement(leaf, retry_count + 1)
                else:
                    # Final fallback after all retries
                    tqdm.write(f"!! All retries failed for {leaf['requirement'][:50]}, using text analysis !!")
                    score = 1 if any(keyword in final_output.lower() for keyword in ["documented", "covered", "explained", "yes"]) else 0
                    return leaf['path'], {
                        "score": score,
                        "reasoning": f"Final fallback after {max_retries} retries - text analysis",
                        "evidence": final_output[:200],
                        "tokens": {"input": input_tokens, "output": output_tokens},
                        "retry_count": retry_count + 1
                    }
                    
        except Exception as e:
            if retry_count < max_retries:
                tqdm.write(f"!! Retry {retry_count + 1} evaluation error for {leaf['requirement'][:50]}: {e} !!")
                await asyncio.sleep(2)  # Wait before retry
                return await re_evaluate_single_requirement(leaf, retry_count + 1)
            else:
                tqdm.write(f"!! Final retry failed for {leaf['requirement'][:50]}: {e} !!")
                return leaf['path'], {
                    "score": 0,
                    "reasoning": f"[EVALUATION ERROR]: final evaluation error after {max_retries} retries: {e}",
                    "evidence": "",
                    "tokens": {"input": 0, "output": 0},
                    "retry_count": retry_count + 1,
                    "error": True,
                }
    
    # Process error leaves with retries
    tqdm.write("Re-evaluating error leaves...")
    retry_tasks = [re_evaluate_single_requirement(leaf) for leaf in error_leaves]
    retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
    
    # Process results
    successful_retries = 0
    for result in retry_results:
        if isinstance(result, Exception):
            tqdm.write(f"!! Re-evaluation exception: {result} !!")
            continue
        
        path, evaluation = result
        re_evaluations[path] = evaluation
        
        # Check if retry was successful (no error in reasoning)
        if not any(keyword in evaluation.get("reasoning", "").lower() for keyword in ["error", "failed", "fallback"]):
            successful_retries += 1
    
    tqdm.write(f"Re-evaluation completed: {successful_retries}/{len(error_leaves)} successful retries")
    return re_evaluations

async def evaluate_leaf_requirements(
    leaf_requirements,
    docs_tree,
    agent: Agent = None,
    deps: AgentDeps = None,
    batch_size=5,
    enable_retry=True,
    max_retries=2,
    model: str = None,
    system_prompt: str = None,
    caw_judge=None,
):
    """Evaluate all leaf requirements against the documentation using batch processing"""
    evaluations = {}
    
    async def evaluate_single_requirement(leaf):
        """Evaluate a single requirement"""
        try:
            prompt = f"""
Evaluate this criteria against the documentation:

Criteria: "{leaf['requirement']}"

Documentation tree:
```json
{json.dumps(docs_tree, indent=2)}
```

First, search the full documentation text with the `grep_docs` tool (try several keyword variants — the tree above shows titles only, the bodies are hidden). Read promising sections with `read_section` to confirm.
Then, evaluate if the criteria is mentioned. Respond with the exact JSON format specified.
""".strip()
            
            if caw_judge is not None:
                final_output, input_tokens, output_tokens = await caw_judge.run(prompt)
            elif agent is None:
                final_output = await run_llm_natively(model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}])
                input_tokens = 0  # Token counting would need to be implemented separately
                output_tokens = 0
            else:
                result = await agent.run(prompt, deps=deps)
                final_output = result.output
                input_tokens = 0  # Token counting would need to be implemented separately
                output_tokens = 0

            # Parse evaluation result
            try:
                # Add debug logging
                # tqdm.write(f"Debug - LLM output for {leaf['requirement'][:30]}: {final_output[:100]}...")
                
                # Extract JSON from output
                json_start = final_output.find('{')
                json_end = final_output.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    eval_json = final_output[json_start:json_end]
                    # tqdm.write(f"Debug - Extracted JSON: {eval_json[:100]}...")
                    evaluation = json.loads(eval_json)
                    
                    # Validate required fields
                    if "score" not in evaluation:
                        tqdm.write(f"!! Warning: No score field in evaluation for {leaf['requirement'][:30]} !!")
                        evaluation["score"] = 0
                    
                    return leaf['path'], {
                        "score": evaluation.get("score", 0),
                        "reasoning": evaluation.get("reasoning", "No reasoning provided"),
                        "evidence": evaluation.get("evidence", "No evidence provided"), 
                        "tokens": {"input": input_tokens, "output": output_tokens}
                    }
                else:
                    raise ValueError("No JSON found in response")
                    
            except Exception as e:
                # Fallback: look for score in text
                tqdm.write(f"!! Fallback to text parsing for {leaf['requirement'][:30]} !!")
                final_output = final_output or ""
                score = 1 if "\"score\": 1" in final_output.lower() or "adequately documented" in final_output.lower() else 0
                return leaf['path'], {
                    "score": score,
                    "reasoning": "[AUTOMATIC PARSING FALLBACK] - No valid JSON found",
                    "evidence": final_output[:500] if final_output else "No output received",
                    "tokens": {"input": input_tokens, "output": output_tokens}
                }
        except Exception as e:
            error_msg = str(e)
            tqdm.write(f"!! Error evaluating {leaf['requirement'][:50]}: {error_msg} !!")
            tqdm.write(traceback.format_exc())
            
            # Check if it's a rate limit error and add delay
            if "429" in error_msg or "rate limit" in error_msg.lower():
                tqdm.write("!! Rate limit detected, adding delay !!")
                await asyncio.sleep(60)  # Wait 60 seconds for rate limit
            
            # An error is NOT evidence of coverage: score 0 and flag it so that
            # --enable-retry re-judges it and reports can tell it apart.
            return leaf['path'], {
                "score": 0,
                "reasoning": f"[EVALUATION ERROR]: {error_msg}",
                "evidence": f"Full error: {error_msg}",
                "tokens": {"input": 0, "output": 0},
                "error": True,
            }
    
    # Process requirements in batches
    total_batches = (len(leaf_requirements) + batch_size - 1) // batch_size
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(leaf_requirements))
        batch = leaf_requirements[start_idx:end_idx]
        
        tqdm.write(f"Processing batch {batch_idx + 1}/{total_batches} ({len(batch)} requirements)...")
        
        # Display what's being evaluated in this batch
        for leaf in batch:
            tqdm.write(f"  - {leaf['requirement'][:100]}...")
        
        # Process batch concurrently
        batch_tasks = [evaluate_single_requirement(leaf) for leaf in batch]
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                tqdm.write(f"!! Batch evaluation error: {result} !!")
                continue
            
            path, evaluation = result
            evaluations[path] = evaluation
        
        # Add a small delay between batches to be respectful to API limits
        if batch_idx < total_batches - 1:
            await asyncio.sleep(1)

    
    # Re-evaluate error cases if enabled
    if enable_retry:
        tqdm.write("Checking for error cases to re-evaluate...")
        re_evaluations = await re_evaluate_error_leaves(
            leaf_requirements,
            docs_tree,
            agent,
            deps,
            evaluations,
            max_retries,
            model,
            system_prompt,
            caw_judge=caw_judge,
        )
        
        # Update evaluations with successful re-evaluations
        for path, re_evaluation in re_evaluations.items():
            evaluations[path] = re_evaluation

    return evaluations

def calculate_scores_bottom_up(rubrics, leaf_evaluations):
    """Calculate scores for all rubric items using bottom-up weighted average"""

    def calculate_score(items, path=""):
        for i, item in enumerate(items):
            current_path = f"{path}.{i}" if path else str(i)
            
            if is_leaf_node(item):
                if current_path not in leaf_evaluations:
                    print(f"[WARNING] No evaluation found for path: {current_path}")

                # Leaf node: use evaluation score
                evaluation = leaf_evaluations.get(current_path, {
                    "score": 0,
                    "reasoning": "No evaluation found",
                    "evidence": "Missing evaluation data",
                    "tokens": {"input": 0, "output": 0}
                })
                
                # Ensure all required fields exist
                if "reasoning" not in evaluation:
                    evaluation["reasoning"] = "No reasoning provided"
                if "evidence" not in evaluation:
                    evaluation["evidence"] = "No evidence provided"
                if "tokens" not in evaluation:
                    evaluation["tokens"] = {"input": 0, "output": 0}
                    
                item["score"] = evaluation["score"]
                item["evaluation"] = evaluation
            else:
                # Parent node: calculate weighted average of children
                calculate_score(item["sub_tasks"], current_path)
                
                total_weighted_score = 0
                total_weight = 0
                
                for sub_task in item["sub_tasks"]:
                    total_weighted_score += sub_task["score"] * sub_task["weight"]
                    total_weight += sub_task["weight"]
                
                item["score"] = total_weighted_score / total_weight if total_weight > 0 else 0
    
    # Create a copy to avoid modifying the original
    scored_rubrics = json.loads(json.dumps(rubrics))
    calculate_score(scored_rubrics)
    
    return scored_rubrics

# --- Run ---
def build_judge(docs_path: str, model: str = None, use_tools: bool = False):
    """Build (agent, deps, caw_judge) for a model string (API model or caw:<provider>:<model>)."""
    deps = AgentDeps(docs_path)
    caw_judge = None
    agent = None

    if model and model.startswith("caw:"):
        # CLI coding agent judge (claude code / codex) via caw; lazy import so
        # non-caw runs don't need caw installed
        from codewikibench.judge.caw_backend import CawJudge, DocsJudgeToolKit, parse_caw_model
        caw_provider, caw_model = parse_caw_model(model)
        toolkit = DocsJudgeToolKit(deps.docs_grep) if use_tools else None
        caw_judge = CawJudge(
            provider=caw_provider,
            model=caw_model,
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            toolkit=toolkit,
        )

    elif use_tools:
        tools = [grep_docs_tool, read_section_tool]
        agent = Agent(
            model=get_llm(model),
            deps_type=AgentDeps,
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            tools=tools
        )

    return agent, deps, caw_judge


def compute_overall_score(scored_rubrics) -> float:
    total_weight = sum(item["weight"] for item in scored_rubrics)
    if total_weight == 0:
        return 0.0
    return sum(item["score"] * item["weight"] for item in scored_rubrics) / total_weight


async def evaluate_rubrics(
    rubrics,
    docs_path: str,
    model: str = None,
    use_tools: bool = False,
    batch_size: int = 5,
    enable_retry: bool = False,
    max_retries: int = 2,
):
    """Judge every leaf of `rubrics` against the parsed docs in `docs_path`.

    Returns (scored_rubrics, leaf_evaluations)."""
    with open(os.path.join(docs_path, "docs_tree.json"), "r") as f:
        docs_tree = json.load(f)

    agent, deps, caw_judge = build_judge(docs_path, model, use_tools)

    # Collect all leaf requirements
    leaf_requirements = collect_leaf_requirements(rubrics)
    print(f"Found {len(leaf_requirements)} leaf requirements to evaluate")

    # Evaluate each leaf requirement
    print("Starting evaluation...")
    leaf_evaluations = await evaluate_leaf_requirements(
        leaf_requirements,
        docs_tree,
        agent,
        deps,
        batch_size,
        enable_retry,
        max_retries,
        model,
        EVALUATION_SYSTEM_PROMPT,
        caw_judge=caw_judge,
    )

    # Calculate scores bottom-up
    print("Calculating scores...")
    scored_rubrics = calculate_scores_bottom_up(rubrics, leaf_evaluations)
    print_evaluation_summary(leaf_requirements, leaf_evaluations, scored_rubrics)
    return scored_rubrics, leaf_evaluations


def print_evaluation_summary(leaf_requirements, leaf_evaluations, scored_rubrics):
    # Calculate and display summary statistics
    total_tokens = sum(eval_data.get("tokens", {}).get("input", 0) + eval_data.get("tokens", {}).get("output", 0) 
                      for eval_data in leaf_evaluations.values())
    total_cost = sum(eval_data.get("tokens", {}).get("input", 0) * 3/1e6 + eval_data.get("tokens", {}).get("output", 0) * 15/1e6 
                    for eval_data in leaf_evaluations.values())
    
    # Count retry statistics
    retry_count = sum(1 for eval_data in leaf_evaluations.values() if eval_data.get("retry_count", 0) > 0)
    error_count = sum(1 for eval_data in leaf_evaluations.values() 
                     if eval_data.get("error") or any(keyword in eval_data.get("reasoning", "").lower() for keyword in ["error", "failed"]))
    
    print("-" * 100)
    print("EVALUATION SUMMARY:")
    print(f"Total leaf requirements evaluated: {len(leaf_requirements)}")
    print(f"Requirements that needed retry: {retry_count}")
    print(f"Requirements with final errors: {error_count}")
    print(f"Total tokens used: {total_tokens}")
    print(f"Total cost: ${total_cost:.4f}")
    
    # Calculate overall score
    overall_score = compute_overall_score(scored_rubrics)
    print(f"Overall documentation score: {overall_score:.4f}")
    print("-" * 100)


async def run(args):
    # Setup paths automatically from repo name
    base_path = config.get_data_path(args.repo_name)
    docs_path = os.path.join(base_path, args.reference)
    output_dir = base_path
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Load existing rubrics
    rubrics_file = args.rubrics_file or os.path.join(output_dir, "rubrics", "combined_rubrics.json")
    
    if not os.path.exists(rubrics_file):
        print(f"Rubrics file not found: {rubrics_file}")
        return
    
    with open(rubrics_file, "r") as f:
        rubrics = json.load(f)
        if "rubrics" in rubrics:
            rubrics = rubrics["rubrics"]
    
    print(f"Loaded rubrics from: {rubrics_file}")

    # check if evaluation file already exists
    evaluation_folder = os.path.join(output_dir, args.reference, "evaluation_results")
    if not os.path.exists(evaluation_folder):
        os.makedirs(evaluation_folder)
    # Sanitize model name to avoid path issues with forward slashes and colons
    sanitized_model = args.model.replace("/", "_").replace(":", "_") if args.model else "default"
    evaluation_file = os.path.join(evaluation_folder, f"{sanitized_model}.json")
    
    if os.path.exists(evaluation_file):
        print(f"Evaluation file already exists: {evaluation_file}")
        return

    scored_rubrics, _ = await evaluate_rubrics(
        rubrics,
        docs_path,
        model=args.model,
        use_tools=args.use_tools,
        batch_size=args.batch_size,
        enable_retry=args.enable_retry,
        max_retries=args.max_retries,
    )

    # Save results
    with open(evaluation_file, "w") as f:
        json.dump(scored_rubrics, f, indent=2)
    
    print(f"Evaluation results saved to: {evaluation_file}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args))


