import os
import json
import yaml
import markdown_to_json
from typing import Any, List, Dict, Optional
from pydantic import BaseModel
import re

class DocPage(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    subpages: List['DocPage'] = []

def convert_to_dict(obj, path=None):
    """Convert Pydantic models to dictionaries for JSON serialization"""
    if path is None:
        path = []
    
    if isinstance(obj, DocPage):
        result = obj.model_dump()
        # Add path information
        if path:
            result["path"] = json.dumps(path.copy())
        # Update subpages with path information
        if result.get("subpages"):
            result["subpages"] = [convert_to_dict(subpage, path + ["subpages", i]) 
                                for i, subpage in enumerate(obj.subpages)]
        return result
    elif isinstance(obj, list):
        return [convert_to_dict(item, path + [i]) for i, item in enumerate(obj)]
    elif isinstance(obj, dict):
        return {key: convert_to_dict(value, path + [key]) for key, value in obj.items()}
    else:
        return obj

def generate_detailed_keys_tree(obj, path=None):
    """
    Generate a detailed tree structure showing only keys until reaching string values.
    Traverses the complete structure and returns only the key hierarchy.
    Includes path information for DocPage objects.
    """
    if path is None:
        path = []
    
    if isinstance(obj, DocPage):
        result = {}
        if obj.title:
            result["title"] = obj.title
        if obj.description:
            result["description"] = obj.description
        # Add path information
        if path:
            result["path"] = json.dumps(path.copy())
        if obj.content:
            result["content"] = generate_detailed_keys_tree(obj.content, path)
        # if obj.metadata:
        #     result["metadata"] = generate_detailed_keys_tree(obj.metadata, path)
        if obj.subpages:
            result["subpages"] = generate_detailed_keys_tree(obj.subpages, path + ["subpages"])
        return result
    elif isinstance(obj, list):
        if not obj:
            return []
        # Show structure of first item and indicate it's a list
        result = []
        if isinstance(obj[0], str):
            return "<detail_content>"#json.dumps(obj, indent=2)
        for i, item in enumerate(obj):
            result.append(generate_detailed_keys_tree(item, path + [i]))
        return result
    elif isinstance(obj, dict):
        if not obj:
            return {}
        result = {}
        for key, value in obj.items():
            if key == "On this page":
                continue
            if isinstance(value, str):
                # Stop at string values, just indicate it's a string
                result[key] = "<detail_content>"
            elif isinstance(value, (int, float, bool)):
                # Stop at primitive values
                result[key] = f"<{type(value).__name__}>"
            elif value is None:
                result[key] = None
            else:
                # Continue traversing for complex objects
                result[key] = generate_detailed_keys_tree(value, path)
        return result
    elif isinstance(obj, str):
        return "<detail_content>"
    elif isinstance(obj, (int, float, bool)):
        return f"<{type(obj).__name__}>"
    elif obj is None:
        return None
    else:
        return f"<{type(obj).__name__}>"

def find_svg_file(svg_path: str, docs_root: str) -> Optional[str]:
    """
    Find the actual SVG file path given a reference path.
    Handles both absolute and relative paths within the docs directory.
    """
    # Remove leading slash if present
    if svg_path.startswith('/'):
        svg_path = svg_path[1:]
    
    # Possible locations to search for the SVG file
    possible_paths = [
        os.path.join(docs_root, svg_path),
        os.path.join(docs_root, 'static', svg_path.replace('static/', '')),
        os.path.join(docs_root, svg_path.replace('static/', '')),
        os.path.join(os.path.dirname(docs_root), svg_path),
        os.path.join(os.path.dirname(docs_root), 'static', svg_path.replace('static/', '')),
    ]
    
    for path in possible_paths:
        if os.path.isfile(path) and path.endswith('.svg'):
            return path
    
    return None

def read_svg_content(svg_path: str) -> Optional[str]:
    """Read and return SVG file content."""
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Ensure it's a valid SVG by checking if it starts with SVG tag
            if '<svg' in content.lower():
                return content
    except (IOError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read SVG file {svg_path}: {e}")
    return None

def replace_svg_references(content: str, docs_root: str) -> str:
    """
    Replace SVG image references in markdown content with actual SVG content.
    Handles patterns like: ![alt_text](/static/img/file.svg) or ![alt_text](file.svg)
    """
    # Pattern to match markdown image syntax with SVG files
    svg_pattern = r'!\[([^\]]*)\]\(([^)]*\.svg)\)'
    
    def replace_svg(match):
        alt_text = match.group(1)
        svg_ref = match.group(2)
        
        # Skip external URLs (http/https)
        if svg_ref.startswith(('http://', 'https://')):
            print(f"Skipping external SVG: {svg_ref}")
            return match.group(0)
        
        # Find the actual SVG file
        svg_path = find_svg_file(svg_ref, docs_root)
        
        if svg_path:
            svg_content = read_svg_content(svg_path)
            if svg_content:
                # Return the SVG content directly, optionally with a comment indicating the original reference
                return f"<!-- Original: ![{alt_text}]({svg_ref}) -->\n{svg_content}"
        
        # If SVG not found or couldn't be read, return original
        print(f"Warning: Could not find or read local SVG: {svg_ref}")
        return match.group(0)
    
    return re.sub(svg_pattern, replace_svg, content)

def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content"""
    frontmatter = {}
    markdown_content = content
    
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                markdown_content = parts[2].strip()
            except yaml.YAMLError:
                # If YAML parsing fails, treat as regular content
                pass
    
    return frontmatter, markdown_content

def parse_markdown_file(file_path: str, docs_root: str) -> DocPage:
    """Parse a single markdown or MDX file"""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Parse frontmatter
    frontmatter, markdown_content = parse_frontmatter(content)
    
    # Replace SVG references with actual SVG content
    markdown_content = replace_svg_references(markdown_content, docs_root)
    
    # Convert markdown to JSON structure
    try:
        content_json = json.loads(markdown_to_json.jsonify(markdown_content))
    except:
        # If markdown_to_json fails, store as plain content
        content_json = {"content": markdown_content}
    
    # Clean up "On this page" sections
    if isinstance(content_json, dict) and "On this page" in content_json:
        del content_json["On this page"]
    
    # Extract title from frontmatter or content
    title = frontmatter.get('title')
    if not title and isinstance(content_json, dict):
        # Try to find title in the content structure
        for key in content_json.keys():
            if isinstance(content_json[key], dict):
                title = key
                content_json = content_json[key]
                break
    
    # Use filename as fallback title
    if not title:
        title = os.path.splitext(os.path.basename(file_path))[0].replace('-', ' ').replace('_', ' ').title()
    
    return DocPage(
        title=title,
        description=frontmatter.get('description'),
        content=content_json,
        metadata=frontmatter,
        subpages=[]
    )

def parse_docs_directory(path: str, project_name: str = None, output_dir: str = None) -> tuple[DocPage, Dict]:
    """
    Parse documentation from markdown files in a directory structure and generate structured output.
    
    Args:
        path (str): Path to the directory containing markdown files
        project_name (str, optional): Name of the project. If None, uses directory name.
        output_dir (str, optional): Directory to save output files. If None, saves to the input path.
    
    Returns:
        tuple: (structured_docs, detailed_keys_tree)
    """
    if output_dir is None:
        output_dir = path
    
    if project_name is None:
        project_name = os.path.basename(path.rstrip('/'))
    
    docs_root = path  # Store the root docs path for SVG resolution
    
    def process_directory(dir_path: str, current_page: DocPage) -> None:
        """Recursively process directory and its subdirectories"""
        items = []
        
        # Get all items in directory and sort them
        try:
            dir_items = os.listdir(dir_path)
        except (PermissionError, FileNotFoundError):
            return
        
        # Separate files and directories
        files = []
        directories = []
        
        for item in dir_items:
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path) and (item.endswith('.md') or item.endswith('.mdx')):
                files.append((item, item_path))
            elif os.path.isdir(item_path) and not item.startswith('.'):
                directories.append((item, item_path))
        
        # Sort files and directories
        files.sort(key=lambda x: x[0])
        directories.sort(key=lambda x: x[0])
        
        # Process files first
        for filename, file_path in files:
            try:
                doc_page = parse_markdown_file(file_path, docs_root)
                current_page.subpages.append(doc_page)
            except Exception as e:
                print(f"Warning: Could not parse {file_path}: {e}")
        
        # Process subdirectories
        for dirname, dir_path in directories:
            # Create a new page for the directory
            dir_page = DocPage(
                title=dirname.replace('-', ' ').replace('_', ' ').title(),
                description=f"Documentation section: {dirname}",
                content={},
                metadata={"type": "directory", "path": dir_path},
                subpages=[]
            )
            
            # Recursively process the subdirectory
            process_directory(dir_path, dir_page)
            
            # Only add the directory page if it has content
            if dir_page.subpages:
                current_page.subpages.append(dir_page)
    
    # Create root documentation structure
    root_page = DocPage(
        title=project_name,
        description=f"Documentation for {project_name}",
        content={},
        metadata={"type": "root", "path": path},
        subpages=[]
    )
    
    # Process the root directory
    process_directory(path, root_page)
    
    # Generate detailed keys tree
    detailed_keys_tree = generate_detailed_keys_tree(root_page)
    
    # Save outputs
    os.makedirs(output_dir, exist_ok=True)
    
    # Save detailed keys tree
    with open(os.path.join(output_dir, "docs_tree.json"), "w", encoding='utf-8') as f:
        json.dump(detailed_keys_tree, f, indent=2, ensure_ascii=False)
    
    # Save structured docs
    with open(os.path.join(output_dir, "structured_docs.json"), "w", encoding='utf-8') as f:
        json.dump(convert_to_dict(root_page), f, indent=2, ensure_ascii=False)
    
    return root_page, detailed_keys_tree

if __name__ == "__main__":
    import config
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Parse documentation for a repository')
    parser.add_argument('--repo_name', required=True, help='Name of the repository to parse documentation for')
    args = parser.parse_args()
    
    # Get repository name from command line argument
    project_name = args.repo_name
    
    # Automatically detect docs_path and target_path using config
    docs_path = config.get_data_path(project_name, "original", "docs")
    target_path = config.get_data_path(project_name, "original")
    
    print(f"Parsing documentation for: {project_name}")
    print(f"Documentation path: {docs_path}")
    print(f"Output path: {target_path}")
    
    # Check if docs path exists
    if not os.path.exists(docs_path):
        print(f"Error: Documentation path does not exist: {docs_path}")
        exit(1)
    
    # Parse the documentation
    structured_docs, keys_tree = parse_docs_directory(docs_path, project_name, output_dir=target_path)
    
    print(f"Successfully parsed documentation for {project_name}")
    print(f"Generated files: docs_tree.json and structured_docs.json in {target_path}")
    print(f"Found {len(structured_docs.subpages)} top-level sections")
    
    # Print a preview of the structure
    print("\nDocument structure preview:")
    for i, subpage in enumerate(structured_docs.subpages[:5]):  # Show first 5
        print(f"  {i+1}. {subpage.title} ({len(subpage.subpages)} subsections)")
    
    if len(structured_docs.subpages) > 5:
        print(f"  ... and {len(structured_docs.subpages) - 5} more sections")