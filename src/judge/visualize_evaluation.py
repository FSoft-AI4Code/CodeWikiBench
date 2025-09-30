#!/usr/bin/env python3
"""
Visualization script for rubric evaluation results.

This script provides various ways to view and analyze the evaluation results:
- Overall score summary
- Detailed breakdown by category
- Low-scoring requirements that need attention
- Export to different formats
"""

import json
import argparse
import os
from pathlib import Path
from typing import Dict, List, Any
import config

def parse_args():
    parser = argparse.ArgumentParser(description="Visualize rubric evaluation results")
    parser.add_argument("--results-file", help="Absolute path to evaluation results JSON file")
    parser.add_argument("--repo-name", help="Name of the repository")
    parser.add_argument("--reference", help="Name of the folder that contains the reference documentation needed for evaluation")
    parser.add_argument("--format", choices=["summary", "detailed", "csv", "markdown"], 
                       default="summary", help="Output format")
    parser.add_argument("--min-score", type=float, default=0.0, 
                       help="Only show items with score >= this value")
    parser.add_argument("--max-score", type=float, default=1.0,
                       help="Only show items with score <= this value") 
    return parser.parse_args()

def calculate_overall_metrics(scored_rubrics: List[Dict]) -> Dict[str, float]:
    """Calculate overall metrics from scored rubrics"""
    def collect_all_items(items: List[Dict]) -> List[Dict]:
        all_items = []
        for item in items:
            all_items.append(item)
            if "sub_tasks" in item and item["sub_tasks"]:
                all_items.extend(collect_all_items(item["sub_tasks"]))
        return all_items
    
    all_items = collect_all_items(scored_rubrics)
    leaf_items = [item for item in all_items if "sub_tasks" not in item or not item["sub_tasks"]]
    
    # Overall weighted score
    total_weighted_score = sum(item["score"] * item["weight"] for item in scored_rubrics)
    total_weight = sum(item["weight"] for item in scored_rubrics)
    overall_score = total_weighted_score / total_weight if total_weight > 0 else 0
    
    # Leaf metrics
    leaf_scores = [item["score"] for item in leaf_items]
    avg_leaf_score = sum(leaf_scores) / len(leaf_scores) if leaf_scores else 0
    documented_leaves = sum(1 for score in leaf_scores if score > 0)
    coverage_percentage = (documented_leaves / len(leaf_scores)) * 100 if leaf_scores else 0
    
    return {
        "overall_score": overall_score,
        "average_leaf_score": avg_leaf_score,
        "total_requirements": len(all_items),
        "leaf_requirements": len(leaf_items),
        "documented_leaves": documented_leaves,
        "coverage_percentage": coverage_percentage
    }

def print_summary(scored_rubrics: List[Dict]):
    """Print a summary of the evaluation results"""
    metrics = calculate_overall_metrics(scored_rubrics)
    
    print("=" * 60)
    print("DOCUMENTATION EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Overall Score: {metrics['overall_score']:.4f}")
    print(f"Average Leaf Score: {metrics['average_leaf_score']:.4f}")
    print(f"Coverage: {metrics['documented_leaves']}/{metrics['leaf_requirements']} leaf requirements ({metrics['coverage_percentage']:.1f}%)")
    print(f"Total Requirements: {metrics['total_requirements']}")
    print()
    
    # Top-level category scores
    print("TOP-LEVEL CATEGORY SCORES:")
    print("-" * 40)
    for i, item in enumerate(scored_rubrics):
        print(f"{i+1}. {item['requirements'][:80]}...")
        print(f"   Score: {item['score']:.4f} | Weight: {item['weight']}")
        print()

def print_detailed(scored_rubrics: List[Dict], min_score: float = 0.0, max_score: float = 1.0):
    """Print detailed breakdown of all requirements"""
    
    def print_item(item: Dict, indent: int = 0, path: str = ""):
        score = item.get("score", 0)
        if not (min_score <= score <= max_score):
            return
            
        prefix = "  " * indent
        status = "✓" if score > 0.5 else "✗"
        
        print(f"{prefix}{status} [{score:.4f}] {item['requirements']}")
        
        # Print evaluation details for leaf nodes
        if "evaluation" in item:
            eval_data = item["evaluation"]
            print(f"{prefix}    Reasoning: {eval_data.get('reasoning', 'N/A')}")
            if eval_data.get('evidence'):
                evidence = eval_data['evidence'][:100] + "..." if len(eval_data['evidence']) > 100 else eval_data['evidence']
                print(f"{prefix}    Evidence: {evidence}")
        
        # Recurse to sub-tasks
        if "sub_tasks" in item and item["sub_tasks"]:
            for j, sub_item in enumerate(item["sub_tasks"]):
                print_item(sub_item, indent + 1, f"{path}.{j}" if path else str(j))
    
    print("=" * 60)
    print("DETAILED EVALUATION RESULTS")
    print("=" * 60)
    print(f"Showing items with score between {min_score} and {max_score}")
    print()
    
    for i, item in enumerate(scored_rubrics):
        print_item(item, 0, str(i))
        print()

def export_to_csv(scored_rubrics: List[Dict], output_file: str):
    """Export results to CSV format"""
    import csv
    
    def collect_flat_items(items: List[Dict], path: str = "") -> List[Dict]:
        flat_items = []
        for i, item in enumerate(items):
            current_path = f"{path}.{i}" if path else str(i)
            
            flat_item = {
                "path": current_path,
                "requirement": item["requirements"],
                "score": item.get("score", 0),
                "weight": item["weight"],
                "is_leaf": "sub_tasks" not in item or not item["sub_tasks"]
            }
            
            if "evaluation" in item:
                eval_data = item["evaluation"]
                flat_item.update({
                    "reasoning": eval_data.get("reasoning", ""),
                    "evidence": eval_data.get("evidence", "")
                })
            
            flat_items.append(flat_item)
            
            if "sub_tasks" in item and item["sub_tasks"]:
                flat_items.extend(collect_flat_items(item["sub_tasks"], current_path))
        
        return flat_items
    
    flat_items = collect_flat_items(scored_rubrics)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if flat_items:
            fieldnames = flat_items[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_items)
    
    print(f"Results exported to {output_file}")

def export_to_markdown(scored_rubrics: List[Dict], output_file: str):
    """Export results to Markdown format"""
    
    def item_to_markdown(item: Dict, level: int = 1) -> str:
        score = item.get("score", 0)
        status_emoji = "✅" if score > 0.7 else "⚠️" if score > 0.3 else "❌"
        
        md = f"{'#' * level} {status_emoji} {item['requirements']} (Score: {score:.4f})\n\n"
        
        if "evaluation" in item:
            eval_data = item["evaluation"]
            md += f"**Reasoning:** {eval_data.get('reasoning', 'N/A')}\n\n"
            if eval_data.get('evidence'):
                md += f"**Evidence:** {eval_data['evidence']}\n\n"
        
        if "sub_tasks" in item and item["sub_tasks"]:
            for sub_item in item["sub_tasks"]:
                md += item_to_markdown(sub_item, level + 1)
        
        return md
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Documentation Evaluation Results\n\n")
        
        metrics = calculate_overall_metrics(scored_rubrics)
        f.write(f"**Overall Score:** {metrics['overall_score']:.4f}\n")
        f.write(f"**Coverage:** {metrics['coverage_percentage']:.1f}%\n")
        f.write(f"**Total Requirements:** {metrics['total_requirements']}\n\n")
        
        for item in scored_rubrics:
            f.write(item_to_markdown(item))
    
    print(f"Results exported to {output_file}")

def main():
    args = parse_args()

    results_file = args.results_file or config.get_data_path(args.repo_name, args.reference, "evaluation_results", "combined_evaluation_results.json")
    
    # If combined file doesn't exist, look for individual model results
    if not os.path.exists(results_file):
        eval_results_dir = config.get_data_path(args.repo_name, args.reference, "evaluation_results")
        individual_files = [f for f in os.listdir(eval_results_dir) if f.endswith('.json') and not f.startswith('combined')]
        
        if len(individual_files) == 1:
            results_file = os.path.join(eval_results_dir, individual_files[0])
            print(f"Combined results not found, using individual results: {individual_files[0]}")
        elif len(individual_files) > 1:
            print(f"Multiple individual result files found: {individual_files}")
            print("Please specify --results-file or run combination step first")
            return
        else:
            print(f"No evaluation result files found in {eval_results_dir}")
            return
    
    # Load evaluation results
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict) and "rubrics" in data:
        # Combined results with metadata
        scored_rubrics = data["rubrics"]
        combination_metadata = data.get("combination_metadata", {})
        print(f"Using combined results from {combination_metadata.get('num_evaluations_combined', 'unknown')} evaluations")
        print(f"Combination method: {combination_metadata.get('combination_method', 'unknown')}")
        print()
    elif isinstance(data, list):
        # Direct list of rubrics
        scored_rubrics = data
    else:
        print(f"Error: Unexpected JSON structure in {results_file}")
        return
    
    if args.format == "summary":
        print_summary(scored_rubrics)
    elif args.format == "detailed":
        print_detailed(scored_rubrics, args.min_score, args.max_score)
    elif args.format == "csv":
        output_file = results_file.replace('.json', '.csv')
        export_to_csv(scored_rubrics, output_file)
    elif args.format == "markdown":
        output_file = results_file.replace('.json', '.md')
        export_to_markdown(scored_rubrics, output_file)

if __name__ == "__main__":
    main() 