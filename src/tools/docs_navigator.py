import json
from typing import Any, Dict, List, Optional, Union
import os
from dataclasses import dataclass

from pydantic_ai import RunContext, Tool

from utils import truncate_tokens


class DocsNavigator:
    """
    A tool for navigating and accessing content from a documentation tree structure.
    Allows agents to retrieve specific content nodes from parsed documentation.
    """
    
    def __init__(self, docs_tree_path: str, structured_docs_path: str):
        """
        Initialize the DocsNavigator with paths to the tree and structured docs files.
        
        Args:
            docs_tree_path: Path to the docs_tree.json file
            structured_docs_path: Path to the structured_docs.json file
        """
        self.docs_tree_path = docs_tree_path
        self.structured_docs_path = structured_docs_path
        self.docs_tree = None
        self.structured_docs = None
        self._load_documents()
    
    def _load_documents(self):
        """Load the documentation files into memory."""
        try:
            with open(self.docs_tree_path, 'r', encoding='utf-8') as f:
                self.docs_tree = json.load(f)
            
            with open(self.structured_docs_path, 'r', encoding='utf-8') as f:
                self.structured_docs = json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Documentation files not found: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in documentation files: {e}")
    
    def list_sections(self, path: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        List all sections at a given path in the documentation tree.
        
        Args:
            path: List of keys to navigate to (e.g., ['Usage', 'How To']). 
                  If None, lists top-level sections.
        
        Returns:
            List of dictionaries with section information (title, type, has_content)
        """
        current_node = self._navigate_to_path(self.docs_tree, path or [])
        sections = []
        
        if isinstance(current_node, dict):
            if 'subpages' in current_node:
                for i, subpage in enumerate(current_node['subpages']):
                    sections.append({
                        'index': i,
                        'title': subpage.get('title', f'Section {i}'),
                        'type': 'subpage',
                        'has_content': bool(subpage.get('content')),
                        'has_subpages': bool(subpage.get('subpages'))
                    })
            
            if 'content' in current_node:
                content = current_node['content']
                if isinstance(content, dict):
                    for key, value in content.items():
                        sections.append({
                            'key': key,
                            'title': key,
                            'type': 'content_section',
                            'has_content': value == '<detail_content>' or isinstance(value, (str, list, dict)),
                            'value_type': type(value).__name__
                        })
        
        return sections
    
    def get_content(self, path: List[str]) -> Dict[str, Any]:
        """
        Retrieve the actual content for a specific path in the documentation.
        
        Args:
            path: List of keys/indices to navigate to the desired content
                  (e.g., ['Usage', 'How To', 0, 'content', 'Getting Started'])
        
        Returns:
            Dictionary containing the content and metadata
        """
        try:
            # Navigate in the structured docs to get actual content
            content_node = self._navigate_to_path(self.structured_docs, path)
            
            # Also get the tree structure for context
            tree_node = self._navigate_to_path(self.docs_tree, path)
            
            return {
                # 'path': path,
                'content': content_node,
                'tree_structure': tree_node,
                'content_type': type(content_node).__name__
            }
        except (KeyError, IndexError, TypeError) as e:
            return {
                # 'path': path,
                'error': f"Content not found at path {' -> '.join(map(str, path))}: {str(e)}",
                'content': None
            }
    
    def search_content(self, query: str, search_titles: bool = True, search_descriptions: bool = True) -> List[Dict[str, Any]]:
        """
        Search for content containing the specified query string.
        
        Args:
            query: The text to search for
            search_titles: Whether to search in section titles
            search_descriptions: Whether to search in section descriptions
        
        Returns:
            List of matching sections with their paths and content previews
        """
        results = []
        query_lower = query.lower()
        
        def _search_recursive(node: Any, current_path: List[str]):
            if isinstance(node, dict):
                # Check title and description
                if search_titles and 'title' in node:
                    title = str(node['title']).lower()
                    if query_lower in title:
                        results.append({
                            'path': current_path + ['title'],
                            'match_type': 'title',
                            'content': node['title'],
                            'context': f"Title: {node['title']}"
                        })
                
                if search_descriptions and 'description' in node:
                    desc = str(node['description']).lower()
                    if query_lower in desc:
                        results.append({
                            'path': current_path + ['description'],
                            'match_type': 'description',
                            'content': node['description'],
                            'context': f"Description: {node['description'][:200]}..."
                        })
                
                # Search in content
                if 'content' in node:
                    _search_recursive(node['content'], current_path + ['content'])
                
                # Search in subpages
                if 'subpages' in node:
                    for i, subpage in enumerate(node['subpages']):
                        _search_recursive(subpage, current_path + ['subpages', i])
                
                # Search in other dict items
                for key, value in node.items():
                    if key not in ['title', 'description', 'content', 'subpages', 'metadata']:
                        _search_recursive(value, current_path + [key])
            
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    _search_recursive(item, current_path + [i])
            
            elif isinstance(node, str) and node != '<detail_content>':
                if query_lower in node.lower():
                    results.append({
                        'path': current_path,
                        'match_type': 'content',
                        'content': node[:500] + '...' if len(node) > 500 else node,
                        'context': f"Content at {' -> '.join(map(str, current_path))}"
                    })
        
        _search_recursive(self.structured_docs, [])
        return results
    
    def _navigate_to_path(self, data: Any, path: List[str], max_depth: int = 15) -> Any:
        """
        Navigate to a specific path in the data structure and limit content depth from the final node.
        
        Args:
            data: The data structure to navigate
            path: List of keys/indices to follow
            max_depth: Maximum depth of content to return from the final node (default: 3)
        
        Returns:
            The node at the specified path, with content limited to max_depth levels
        """
        current = data
        
        # Navigate to the full path
        for key in path:
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, list):
                try:
                    index = int(key)
                    current = current[index]
                except (ValueError, IndexError):
                    raise KeyError(f"Invalid list index: {key}")
            else:
                raise KeyError(f"Cannot navigate further from {type(current)} with key {key}")
        
        # Limit the depth of the content from this final node
        # max_depth = 3 if len(path) <=2 else len(path)*2
        return self._limit_content_depth(current, max_depth)
    
    def _limit_content_depth(self, data: Any, max_depth: int, current_depth: int = 0) -> Any:
        """
        Recursively limit the depth of a data structure.
        
        Args:
            data: The data to limit
            max_depth: Maximum allowed depth
            current_depth: Current recursion depth
        
        Returns:
            Data structure limited to max_depth levels
        """
        if current_depth >= max_depth:
            if isinstance(data, dict):
                return {"...": f"<content truncated at depth {max_depth}>"}
            elif isinstance(data, list):
                return [f"<list with {len(data)} items truncated at depth {max_depth}>"]
            else:
                return data
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                result[key] = self._limit_content_depth(value, max_depth, current_depth + 1)
            return result
        elif isinstance(data, list):
            return [self._limit_content_depth(item, max_depth, current_depth + 1) for item in data]
        else:
            return data


@dataclass
class AgentDeps:
    docs_navigator: DocsNavigator

    def __init__(self, docs_path: str):

        tree_path = os.path.join(docs_path, "docs_tree.json")
        structured_path = os.path.join(docs_path, "structured_docs.json")
        
        if not os.path.exists(tree_path):
            raise FileNotFoundError(f"docs_tree.json not found at {tree_path}")
        if not os.path.exists(structured_path):
            raise FileNotFoundError(f"structured_docs.json not found at {structured_path}")
        
        self.docs_navigator = DocsNavigator(tree_path, structured_path)


async def run_docs_navigator(ctx: RunContext[AgentDeps], paths: List[List[Any]]) -> str:
    """
    Navigate to specific paths in the documentation tree and return the content.
    
    Args:
        paths: List of lists of keys/indices to navigate to the desired content (e.g., [['subpages', 2, 'subpages', 0, 'content', 'Getting Started'], ['subpages', 2, 'subpages', 1, 'content', 'Getting Started']]). Each list is a path to a specific content node in the documentation tree.
    """

    formatted_results = ""
    for path in paths:
        result = ctx.deps.docs_navigator.get_content(path)
        formatted_results += "--------------------------------\n"
        formatted_results += f"Path: {path}\n"
        formatted_results += f"Content: \n{json.dumps(result['content'], indent=2)}\n"
        formatted_results += "--------------------------------\n"

    return truncate_tokens(formatted_results)


docs_navigator_tool = Tool(
    name="docs_navigator",
    description="A tool for navigating and accessing content from a documentation tree structure.",
    function=run_docs_navigator,
    takes_ctx=True
)


async def test_run_docs_navigator(docs_navigator: DocsNavigator, paths: List[List[Any]]) -> str:
    """
    Navigate to specific paths in the documentation tree and return the content.
    
    Args:
        paths: List of lists of keys/indices to navigate to the desired content (e.g., [['subpages', 2, 'subpages', 0, 'content', 'Getting Started'], ['subpages', 2, 'subpages', 1, 'content', 'Getting Started']]). Each list is a path to a specific content node in the documentation tree.
    """

    formatted_results = ""
    for path in paths:
        result = docs_navigator.get_content(path)
        formatted_results += "--------------------------------\n"
        formatted_results += f"Path: {path}\n"
        formatted_results += f"Content: \n{json.dumps(result['content'], indent=2)}\n"
        formatted_results += "--------------------------------\n"

    return truncate_tokens(formatted_results)


if __name__ == "__main__":
    from utils import get_llm
    import asyncio
    deps = AgentDeps(docs_path="../data/ragflow/deepwiki-agent")
    result = asyncio.run(test_run_docs_navigator(
        docs_navigator=deps.docs_navigator,
        paths=[
                [
                [
                    "subpages",
                    3,
                    "content",
                    "Vision Processing Module"
                ]
                ],
                [
                [
                    "subpages",
                    2,
                    "subpages",
                    1,
                    "content",
                    "Advanced Processing Module"
                ]
                ],
                [
                [
                    "subpages",
                    2,
                    "subpages",
                    0,
                    "subpages",
                    0,
                    "content",
                    "PDF Processing Module"
                ]
                ]
            ]))
    print(result)