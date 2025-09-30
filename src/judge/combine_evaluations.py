import json
import argparse
import os
import glob
from pathlib import Path
from typing import List, Dict, Any
import statistics
from collections import Counter
import math
import config

def parse_args():
    parser = argparse.ArgumentParser(description="Combine evaluation results from multiple LLMs")
    parser.add_argument("--repo-name", required=True, help="Name of the repository")
    parser.add_argument("--reference", required=True, help="Name of the folder that contains the reference documentation needed for evaluation")
    parser.add_argument("--output-file", help="Output file name (default: evaluation_results_combined.json)")
    parser.add_argument("--method", choices=["average", "majority_vote", "weighted_average", "max", "min"], 
                       default="average", help="Combination method (default: average)")
    parser.add_argument("--weights", help="Comma-separated weights for weighted average (e.g., '0.4,0.3,0.3')")
    parser.add_argument("--confidence-threshold", type=float, default=0.0, 
                       help="Minimum confidence threshold for including evaluations (default: 0.0)")
    return parser.parse_args()

def is_leaf_node(rubric_item):
    """Check if a rubric item is a leaf node (has no sub_tasks)"""
    return "sub_tasks" not in rubric_item or not rubric_item["sub_tasks"]

def collect_leaf_paths(rubrics, path=""):
    """Collect all leaf paths from rubrics hierarchy"""
    leaf_paths = []
    
    def traverse(items, current_path=""):
        for i, item in enumerate(items):
            item_path = f"{current_path}.{i}" if current_path else str(i)
            
            if is_leaf_node(item):
                leaf_paths.append(item_path)
            else:
                traverse(item["sub_tasks"], item_path)
    
    traverse(rubrics, path)
    return leaf_paths

def extract_leaf_evaluations(rubrics, path=""):
    """Extract all leaf evaluations with their paths"""
    leaf_evaluations = {}
    
    def traverse(items, current_path=""):
        for i, item in enumerate(items):
            item_path = f"{current_path}.{i}" if current_path else str(i)
            
            if is_leaf_node(item):
                if "evaluation" in item:
                    leaf_evaluations[item_path] = item["evaluation"]
            else:
                traverse(item["sub_tasks"], item_path)
    
    traverse(rubrics, path)
    return leaf_evaluations

def combine_scores_average(scores: List[float]) -> float:
    """Combine scores using simple average"""
    return statistics.mean(scores) if scores else 0.0

def combine_scores_majority_vote(scores: List[int]) -> int:
    """Combine binary scores using majority vote"""
    if not scores:
        return 0
    counter = Counter(scores)
    return counter.most_common(1)[0][0]

def combine_scores_weighted_average(scores: List[float], weights: List[float]) -> float:
    """Combine scores using weighted average"""
    if not scores or not weights or len(scores) != len(weights):
        return 0.0
    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

def combine_scores_max(scores: List[float]) -> float:
    """Combine scores using maximum"""
    return max(scores) if scores else 0.0

def combine_scores_min(scores: List[float]) -> float:
    """Combine scores using minimum"""
    return min(scores) if scores else 0.0

def calculate_std(scores: List[float]) -> float:
    """Calculate sample standard deviation of scores"""
    if len(scores) < 2:
        return 0.0
    return statistics.stdev(scores)

def combine_std_weighted(stds: List[float], weights: List[float]) -> float:
    """
    Combine standard deviations using weighted combination formula.
    Formula: σ_combined = sqrt(Σ(w_i^2 * σ_i^2)) / Σ(w_i)
    """
    if not stds or not weights or len(stds) != len(weights):
        return 0.0
    
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    
    weighted_variance = sum(w**2 * s**2 for w, s in zip(weights, stds))
    return math.sqrt(weighted_variance) / total_weight

def combine_leaf_evaluations(all_leaf_evaluations: List[Dict], method: str, weights: List[float] = None) -> Dict:
    """Combine leaf evaluations from multiple LLMs"""
    if not all_leaf_evaluations:
        return {}
    
    # Get all unique leaf paths
    all_paths = set()
    for leaf_evals in all_leaf_evaluations:
        all_paths.update(leaf_evals.keys())
    
    combined_evaluations = {}
    
    for path in all_paths:
        # Collect scores for this path from all LLMs
        scores = []
        reasonings = []
        evidences = []
        all_tokens = {"input": 0, "output": 0}
        
        for leaf_evals in all_leaf_evaluations:
            if path in leaf_evals:
                eval_data = leaf_evals[path]
                scores.append(eval_data.get("score", 0))
                reasonings.append(eval_data.get("reasoning", ""))
                evidences.append(str(eval_data.get("evidence", "")))
                
                tokens = eval_data.get("tokens", {})
                all_tokens["input"] += tokens.get("input", 0)
                all_tokens["output"] += tokens.get("output", 0)
        
        if not scores:
            continue
        
        # Combine scores based on method
        if method == "average":
            combined_score = combine_scores_average(scores)
        elif method == "majority_vote":
            combined_score = combine_scores_majority_vote([int(s) for s in scores])
        elif method == "weighted_average" and weights:
            # Only use weights if we have enough
            if len(weights) >= len(scores):
                combined_score = combine_scores_weighted_average(scores, weights[:len(scores)])
            else:
                combined_score = combine_scores_average(scores)
        elif method == "max":
            combined_score = combine_scores_max(scores)
        elif method == "min":
            combined_score = combine_scores_min(scores)
        else:
            combined_score = combine_scores_average(scores)
        
        # Calculate standard deviation of scores
        std_deviation = calculate_std(scores)
        
        # Combine reasoning and evidence
        combined_reasoning = f"Combined from {len(scores)} LLMs ({method}): " + " | ".join(reasonings)
        combined_evidence = " | ".join(evidences)
        
        combined_evaluations[path] = {
            "score": combined_score,
            "std": std_deviation,
            "reasoning": combined_reasoning,
            "evidence": combined_evidence,
            "tokens": all_tokens,
            "individual_scores": scores,
            "combination_method": method,
            "num_llms": len(scores)
        }
    
    return combined_evaluations

def calculate_scores_bottom_up(rubrics, leaf_evaluations):
    """Calculate scores and standard deviations for all rubric items using bottom-up weighted average"""
    
    def calculate_score_and_std(items, path=""):
        for i, item in enumerate(items):
            current_path = f"{path}.{i}" if path else str(i)
            
            if is_leaf_node(item):
                # Leaf node: use combined evaluation score and std
                evaluation = leaf_evaluations.get(current_path, {"score": 0, "std": 0})
                item["score"] = evaluation["score"]
                item["std"] = evaluation.get("std", 0)
                item["evaluation"] = evaluation
            else:
                # Parent node: calculate weighted average of children
                calculate_score_and_std(item["sub_tasks"], current_path)
                
                total_weighted_score = 0
                total_weight = 0
                child_stds = []
                child_weights = []
                
                for sub_task in item["sub_tasks"]:
                    weight = sub_task["weight"]
                    total_weighted_score += sub_task["score"] * weight
                    total_weight += weight
                    child_stds.append(sub_task.get("std", 0))
                    child_weights.append(weight)
                
                item["score"] = total_weighted_score / total_weight if total_weight > 0 else 0
                item["std"] = combine_std_weighted(child_stds, child_weights)
    
    # Create a copy to avoid modifying the original
    scored_rubrics = json.loads(json.dumps(rubrics))
    calculate_score_and_std(scored_rubrics)
    
    return scored_rubrics

def load_evaluation_files(repo_name: str, reference: str) -> List[Dict]:
    """Load all evaluation files matching the pattern"""
    base_path = config.get_data_path(repo_name, reference, "evaluation_results")
    
    file_pattern = os.path.join(base_path, "*.json")
    
    all_files = glob.glob(file_pattern)
    evaluation_files = [f for f in all_files if "combined" not in os.path.basename(f)]
    
    if not evaluation_files:
        raise ValueError(f"No evaluation files found matching pattern: {file_pattern}")
    
    print(f"Found {len(evaluation_files)} evaluation files:")
    for file_path in evaluation_files:
        print(f"  - {os.path.basename(file_path)}")
    
    evaluations = []
    for file_path in evaluation_files:
        try:
            with open(file_path, "r") as f:
                evaluation = json.load(f)
                evaluations.append(evaluation)
                print(f"✓ Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"✗ Error loading {file_path}: {e}")
    
    return evaluations

def main():
    args = parse_args()
    
    # Load all evaluation files
    print("Loading evaluation files...")
    evaluations = load_evaluation_files(args.repo_name, args.reference)
    
    if len(evaluations) < 2:
        print("Error: Need at least 2 evaluation files to combine")
        return
    
    print(f"Combining {len(evaluations)} evaluations using method: {args.method}")
    
    # Parse weights if provided
    weights = None
    if args.weights:
        try:
            weights = [float(w.strip()) for w in args.weights.split(",")]
            print(f"Using weights: {weights}")
            if len(weights) != len(evaluations):
                print(f"Warning: Number of weights ({len(weights)}) doesn't match number of evaluations ({len(evaluations)})")
        except Exception as e:
            print(f"Error parsing weights: {e}")
            weights = None
    
    # Extract leaf evaluations from all evaluations
    all_leaf_evaluations = []
    for evaluation in evaluations:
        leaf_evals = extract_leaf_evaluations(evaluation)
        all_leaf_evaluations.append(leaf_evals)
        print(f"Extracted {len(leaf_evals)} leaf evaluations")
    
    # Combine leaf evaluations
    print("Combining leaf evaluations...")
    combined_leaf_evaluations = combine_leaf_evaluations(all_leaf_evaluations, args.method, weights)
    
    # Use the first evaluation as template and update with combined scores
    combined_rubrics = json.loads(json.dumps(evaluations[0]))  # Deep copy
    
    # Calculate combined scores bottom-up
    print("Calculating combined scores...")
    combined_rubrics = calculate_scores_bottom_up(combined_rubrics, combined_leaf_evaluations)
    
    # Calculate overall statistics for metadata
    overall_score_for_metadata = 0
    overall_std_for_metadata = 0
    total_weight_for_metadata = 0
    top_level_stds_for_metadata = []
    top_level_weights_for_metadata = []
    
    if isinstance(combined_rubrics, list):
        rubrics_list_for_metadata = combined_rubrics
    else:
        rubrics_list_for_metadata = combined_rubrics.get("rubrics", combined_rubrics)
    
    if isinstance(rubrics_list_for_metadata, list):
        for item in rubrics_list_for_metadata:
            weight = item.get("weight", 1)
            overall_score_for_metadata += item.get("score", 0) * weight
            total_weight_for_metadata += weight
            top_level_stds_for_metadata.append(item.get("std", 0))
            top_level_weights_for_metadata.append(weight)
    
    overall_score_for_metadata = overall_score_for_metadata / total_weight_for_metadata if total_weight_for_metadata > 0 else 0
    overall_std_for_metadata = combine_std_weighted(top_level_stds_for_metadata, top_level_weights_for_metadata)
    
    # Add metadata about the combination
    combination_metadata = {
        "combination_method": args.method,
        "num_evaluations_combined": len(evaluations),
        "weights": weights,
        "confidence_threshold": args.confidence_threshold,
        "overall_score": overall_score_for_metadata,
        "overall_std": overall_std_for_metadata,
        "overall_score_range": [overall_score_for_metadata - overall_std_for_metadata, 
                               overall_score_for_metadata + overall_std_for_metadata]
    }
    
    # Save combined results
    base_path = config.get_data_path(args.repo_name, args.reference, "evaluation_results")
    output_file = args.output_file or "combined_evaluation_results.json"
    output_path = os.path.join(base_path, output_file)
    
    # Add metadata to the combined results
    if isinstance(combined_rubrics, list):
        result = {
            "rubrics": combined_rubrics,
            "combination_metadata": combination_metadata
        }
    else:
        result = combined_rubrics
        result["combination_metadata"] = combination_metadata
    
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"Combined evaluation results saved to: {output_path}")
    
    # Calculate and display summary statistics
    overall_score = 0
    overall_std = 0
    total_weight = 0
    top_level_stds = []
    top_level_weights = []
    
    if isinstance(combined_rubrics, list):
        rubrics_list = combined_rubrics
    else:
        rubrics_list = combined_rubrics.get("rubrics", combined_rubrics)
    
    if isinstance(rubrics_list, list):
        for item in rubrics_list:
            weight = item.get("weight", 1)
            overall_score += item.get("score", 0) * weight
            total_weight += weight
            top_level_stds.append(item.get("std", 0))
            top_level_weights.append(weight)
    
    overall_score = overall_score / total_weight if total_weight > 0 else 0
    overall_std = combine_std_weighted(top_level_stds, top_level_weights)
    
    print("-" * 100)
    print("COMBINATION SUMMARY:")
    print(f"Method used: {args.method}")
    print(f"Number of evaluations combined: {len(evaluations)}")
    print(f"Total leaf evaluations: {len(combined_leaf_evaluations)}")
    print(f"Overall combined score: {overall_score:.4f} ± {overall_std:.4f}")
    print(f"Overall score range: [{overall_score - overall_std:.4f}, {overall_score + overall_std:.4f}]")
    print("-" * 100)

if __name__ == "__main__":
    main() 