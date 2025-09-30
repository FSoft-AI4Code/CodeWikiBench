import networkx as nx
from typing import Set
from pydantic import BaseModel, Field
from typing import List, Any
import json

class Rubric(BaseModel):
    requirements: str = Field(description="The requirements of the rubric")
    weight: int = Field(description="The weight that represents its importance: 3: Essential rubric, 2: Important but not essential, 1: Non-essential or supportive")
    reference: List[List[Any]|Any] = Field(default_factory=list, description="The list of references to the documentation paths that inform this rubric. Only leaf rubrics should have non-empty references.")
    sub_tasks: List["Rubric"] = Field(default_factory=list, description="The list of children rubrics. Leaf rubrics should not have children.")

def find_root(tree: nx.DiGraph) -> str:
    """Find the root node (node with no incoming edges)"""
    in_degrees = dict(tree.in_degree())
    for node, degree in in_degrees.items():
        if degree == 0:
            return node
    return None

def tree_ascii_art(tree: nx.DiGraph, root: str = None) -> str:
    """Create ASCII art representation of tree"""
    if root is None:
        root = find_root(tree)
    
    def build_tree_lines(node, prefix="", is_last=True):
        lines = []
        note_metadata = tree.nodes[node]
        weight = note_metadata.get("weight", "")
        reference = note_metadata.get("reference", "[]")
        if isinstance(reference, str):
            reference = json.loads(reference)
        
        # Current node
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + str(node) + f' (weight={weight})')
        # lines.append(prefix + connector + str(node))
        
        # Get children
        children = list(tree.successors(node))
        
        # Process children
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            extension = "    " if is_last else "│   "
            child_lines = build_tree_lines(child, prefix + extension, is_last_child)
            lines.extend(child_lines)
        
        return lines
    
    return "\n".join(build_tree_lines(root))

def rubric_to_graph(rubric: Rubric) -> nx.DiGraph:
    """
    Convert a Rubric instance to a directed NetworkX graph.
    
    Args:
        rubric: The root Rubric instance
        
    Returns:
        nx.DiGraph: A directed graph where nodes represent rubrics and edges represent parent-child relationships
    """
    graph = nx.DiGraph()
    visited = set()
    
    def _add_rubric_recursive(rubric: Rubric, parent_name: str = None):
        """Recursively add rubrics to the graph."""
        # Avoid infinite loops in case of circular references
        if rubric.requirements in visited:
            return
        visited.add(rubric.requirements)
        
        # Add node with all rubric attributes
        graph.add_node(
            rubric.requirements,
            weight=rubric.weight,
            reference=rubric.reference,
            is_leaf=len(rubric.sub_tasks) == 0,
            has_references=len(rubric.reference) > 0
        )
        
        # Add edge from parent to this rubric
        if parent_name:
            graph.add_edge(parent_name, rubric.requirements)
        
        # Recursively add children
        for child in rubric.sub_tasks:
            _add_rubric_recursive(child, rubric.requirements)
    
    _add_rubric_recursive(rubric)
    return graph

def get_graph_statistics(graph: nx.DiGraph) -> dict:
    """
    Get useful statistics about the rubric graph.
    
    Args:
        graph: The NetworkX directed graph
        
    Returns:
        dict: Dictionary containing graph statistics
    """
    stats = {
        'total_nodes': graph.number_of_nodes(),
        'total_edges': graph.number_of_edges(),
        'leaf_nodes': [node for node, data in graph.nodes(data=True) if data.get('is_leaf', False)],
        'root_nodes': [node for node in graph.nodes() if graph.in_degree(node) == 0],
        'nodes_with_references': [node for node, data in graph.nodes(data=True) if data.get('has_references', False)],
        'weight_distribution': {},
        'max_depth': 0
    }
    
    # Calculate weight distribution
    for node, data in graph.nodes(data=True):
        weight = data.get('weight', 0)
        stats['weight_distribution'][weight] = stats['weight_distribution'].get(weight, 0) + 1
    
    # Calculate maximum depth
    for root in stats['root_nodes']:
        try:
            depths = nx.single_source_shortest_path_length(graph, root)
            max_depth_from_root = max(depths.values()) if depths else 0
            stats['max_depth'] = max(stats['max_depth'], max_depth_from_root)
        except:
            pass
    
    return stats

def visualize_rubrics(path: str) -> None:
    with open(path, "r") as f:
        rubrics = json.load(f)
    
    root = Rubric(
        requirements="root rubric",
        weight=3,
        sub_tasks=[Rubric(**rubric) for rubric in rubrics]
    )
    
    # Convert to graph
    graph = rubric_to_graph(root)

    print(tree_ascii_art(graph))
    

import argparse

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rubrics-path", type=str, default="ragflow/rubrics.json")
    args = parser.parse_args()
    
    with open(args.rubrics_path, "r") as f:
        rubrics = json.load(f)
        if "rubrics" in rubrics:
            rubrics = rubrics["rubrics"]
    
    root = Rubric(
        requirements="root rubric",
        weight=3,
        sub_tasks=[Rubric(**rubric) for rubric in rubrics]
    )
    
    # Convert to graph
    graph = rubric_to_graph(root)

    print(tree_ascii_art(graph))
    