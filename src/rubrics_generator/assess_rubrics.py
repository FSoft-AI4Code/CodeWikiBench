import json
import os
import asyncio
import argparse
from typing import List, Dict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter

import config
from utils import get_embeddings


class RubricReliabilityAssessor:
    """Comprehensive reliability assessment for generated rubrics"""
    
    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.base_path = config.get_data_path(repo_name, "rubrics")
        self.docs_path = config.get_data_path(repo_name, "original")
        
    async def assess_reliability(self, combined_rubrics_path: str) -> Dict:
        """Main method to assess rubric reliability"""
        
        with open(combined_rubrics_path, 'r') as f:
            combined_data = json.load(f)
            rubrics = combined_data.get("rubrics", combined_data)
        
        assessment_results = {
            "inter_model_consistency": await self._assess_inter_model_consistency(),
        }
        
        # Calculate overall reliability score
        assessment_results["overall_reliability_score"] = self._calculate_overall_score(assessment_results)
        
        return assessment_results
    
    async def _assess_inter_model_consistency(self) -> Dict:
        """Assess consistency between different models' outputs"""
        
        # Load all individual model rubrics
        individual_rubrics = []
        rubrics_files = [f for f in os.listdir(self.base_path) 
                        if f.endswith('.json') and 'combined' not in f and 'assessment' not in f]
        
        for file in rubrics_files:
            with open(os.path.join(self.base_path, file), 'r') as f:
                rubrics = json.load(f)
                individual_rubrics.append((file, rubrics))
        
        if len(individual_rubrics) < 2:
            return {"error": "Need at least 2 individual rubrics files for consistency analysis"}
        
        # Calculate pairwise similarities
        similarities = []
        structural_similarities = []
        
        for i in range(len(individual_rubrics)):
            for j in range(i + 1, len(individual_rubrics)):
                sem_sim = await self._calculate_semantic_similarity(
                    individual_rubrics[i][1], individual_rubrics[j][1]
                )
                struct_sim = self._calculate_structural_similarity(
                    individual_rubrics[i][1], individual_rubrics[j][1]
                )
                
                similarities.append(sem_sim)
                structural_similarities.append(struct_sim)
        
        return {
            "semantic_consistency_scores": similarities,
            "structural_consistency_scores": structural_similarities,
            "avg_semantic_consistency": np.mean(similarities),
            "avg_structural_consistency": np.mean(structural_similarities),
            "consistency_std": np.std(similarities),
            "num_models_compared": len(individual_rubrics)
        }
    
    async def _calculate_semantic_similarity(self, rubrics1: List[Dict], rubrics2: List[Dict]) -> float:
        """Calculate semantic similarity between two sets of rubrics"""
        
        # Extract all requirement texts
        texts1 = self._extract_all_requirements(rubrics1)
        texts2 = self._extract_all_requirements(rubrics2)
        
        # Handle edge cases
        if not texts1 and not texts2:
            return 1.0  # Both empty = identical
        if not texts1 or not texts2:
            return 0.0  # One empty, one not = completely different
        
        # Check for exact match first
        if texts1 == texts2:
            return 1.0
        
        # Get embeddings
        all_texts = texts1 + texts2
        embeddings = await get_embeddings(all_texts)
        
        # Split embeddings
        emb1 = embeddings[:len(texts1)]
        emb2 = embeddings[len(texts1):]
        
        # Best matching pairs (Hungarian-like approach)
        # For each embedding in emb1, find best match in emb2
        max_similarities = []
        for e1 in emb1:
            best_sim = max(cosine_similarity([e1], [e2])[0][0] for e2 in emb2)
            max_similarities.append(best_sim)
        
        # For each embedding in emb2, find best match in emb1  
        for e2 in emb2:
            best_sim = max(cosine_similarity([e1], [e2])[0][0] for e1 in emb1)
            max_similarities.append(best_sim)
        
        # Average the best matches
        best_match_similarity = np.mean(max_similarities)
        
        return best_match_similarity
    
    def _calculate_structural_similarity(self, rubrics1: List[Dict], rubrics2: List[Dict]) -> float:
        """Calculate structural similarity between rubrics"""
        
        stats1 = self._get_rubrics_stats(rubrics1)
        stats2 = self._get_rubrics_stats(rubrics2)
        
        # Compare structural features
        depth_sim = 1 - abs(stats1["max_depth"] - stats2["max_depth"]) / max(stats1["max_depth"], stats2["max_depth"], 1)
        
        # Weight distribution similarity
        weight_sim = self._calculate_distribution_similarity(
            stats1["weight_distribution"], stats2["weight_distribution"]
        )
        
        # Number of items similarity
        items_sim = 1 - abs(stats1["total_items"] - stats2["total_items"]) / max(stats1["total_items"], stats2["total_items"], 1)
        
        return (depth_sim + weight_sim + items_sim) / 3
    
    def _calculate_overall_score(self, assessment_results: Dict) -> float:
        """Calculate weighted overall reliability score"""
        
        scores = []
        weights = []
        
        # Inter-model consistency (weight: 1)
        if "avg_semantic_consistency" in assessment_results.get("inter_model_consistency", {}):
            scores.append(assessment_results["inter_model_consistency"]["avg_semantic_consistency"])
            weights.append(1)
        

        
        if scores and weights:
            # Normalize weights
            total_weight = sum(weights)
            normalized_weights = [w / total_weight for w in weights]
            
            return sum(score * weight for score, weight in zip(scores, normalized_weights))
        
        return 0.0
    
    # Helper methods
    def _extract_all_requirements(self, rubrics: List[Dict]) -> List[str]:
        """Extract all requirement texts from rubrics recursively"""
        requirements = []
        
        def extract_recursive(rubric):
            if "requirements" in rubric:
                requirements.append(rubric["requirements"])
            for child in rubric.get("sub_tasks", []):
                extract_recursive(child)
        
        for rubric in rubrics:
            extract_recursive(rubric)
        
        return requirements
    
    def _get_rubrics_stats(self, rubrics: List[Dict]) -> Dict:
        """Get comprehensive statistics about rubrics"""
        
        def analyze_recursive(rubric, level=0):
            stats = {
                "total_items": 1,
                "max_depth": level,
                "weights": [rubric.get("weight", 1)],
                "leaf_count": 0 if rubric.get("sub_tasks") else 1
            }
            
            for child in rubric.get("sub_tasks", []):
                child_stats = analyze_recursive(child, level + 1)
                stats["total_items"] += child_stats["total_items"]
                stats["max_depth"] = max(stats["max_depth"], child_stats["max_depth"])
                stats["weights"].extend(child_stats["weights"])
                stats["leaf_count"] += child_stats["leaf_count"]
            
            return stats
        
        combined_stats = {"total_items": 0, "max_depth": 0, "weights": [], "leaf_count": 0}
        
        for rubric in rubrics:
            rubric_stats = analyze_recursive(rubric)
            combined_stats["total_items"] += rubric_stats["total_items"]
            combined_stats["max_depth"] = max(combined_stats["max_depth"], rubric_stats["max_depth"])
            combined_stats["weights"].extend(rubric_stats["weights"])
            combined_stats["leaf_count"] += rubric_stats["leaf_count"]
        
        # Calculate additional metrics
        weight_distribution = dict(Counter(combined_stats["weights"]))
        leaf_ratio = combined_stats["leaf_count"] / combined_stats["total_items"] if combined_stats["total_items"] > 0 else 0
        
        return {
            "total_items": combined_stats["total_items"],
            "max_depth": combined_stats["max_depth"],
            "weight_distribution": weight_distribution,
            "leaf_ratio": leaf_ratio
        }
    
    def _calculate_distribution_similarity(self, dist1: Dict, dist2: Dict) -> float:
        """Calculate similarity between two distributions"""
        all_keys = set(dist1.keys()) | set(dist2.keys())
        
        vec1 = [dist1.get(k, 0) for k in all_keys]
        vec2 = [dist2.get(k, 0) for k in all_keys]
        
        # Normalize
        total1, total2 = sum(vec1), sum(vec2)
        if total1 == 0 or total2 == 0:
            return 0.0
        
        vec1 = [v / total1 for v in vec1]
        vec2 = [v / total2 for v in vec2]
        
        # Calculate overlap
        return sum(min(v1, v2) for v1, v2 in zip(vec1, vec2))


def parse_args():
    parser = argparse.ArgumentParser(description="Assess reliability of generated rubrics")
    parser.add_argument("--repo-name", required=True, help="Name of the repository")
    parser.add_argument("--rubrics-file", help="Path to combined rubrics file (default: combined_rubrics.json)")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    assessor = RubricReliabilityAssessor(args.repo_name)
    
    # Determine rubrics file path
    if args.rubrics_file:
        rubrics_path = args.rubrics_file
    else:
        rubrics_path = os.path.join(assessor.base_path, "combined_rubrics.json")
    
    if not os.path.exists(rubrics_path):
        print(f"Rubrics file not found: {rubrics_path}")
        return
    
    print(f"Assessing reliability of rubrics: {rubrics_path}")
    
    # Run assessment
    results = await assessor.assess_reliability(rubrics_path)
    
    # Save results
    assessment_file = os.path.join(assessor.base_path, "reliability_assessment.json")
    with open(assessment_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Assessment results saved to: {assessment_file}")
    
    # Print summary
    print("\n" + "="*80)
    print("RUBRICS RELIABILITY ASSESSMENT SUMMARY")
    print("="*80)
    
    overall_score = results.get("overall_reliability_score", 0)
    print(f"Overall Reliability Score: {overall_score:.4f} / 1.000")
    
    if overall_score >= 0.8:
        print("✅ EXCELLENT reliability - rubrics are highly trustworthy")
    elif overall_score >= 0.6:
        print("✅ GOOD reliability - rubrics are generally trustworthy")
    elif overall_score >= 0.4:
        print("⚠️  MODERATE reliability - rubrics need improvement")
    else:
        print("❌ LOW reliability - rubrics require significant revision")
    
    # Detailed breakdown
    for category, details in results.items():
        if category == "overall_reliability_score":
            continue
        
        print(f"\n{category.replace('_', ' ').title()}:")
        if isinstance(details, dict) and not details.get("error"):
            for key, value in details.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    print(f"  - {key}: {value:.4f}" if isinstance(value, float) else f"  - {key}: {value}")
                elif isinstance(value, list) and len(value) < 10:
                    print(f"  - {key}: {value}")
                elif key not in ["explanations", "consistency_issues"]:
                    print(f"  - {key}: {value}")
        elif details.get("error"):
            print(f"  ❌ {details['error']}")


if __name__ == "__main__":
    asyncio.run(main())
