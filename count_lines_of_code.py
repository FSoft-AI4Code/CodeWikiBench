#!/usr/bin/env python3
"""
GitHub Repository Line Counter

This script clones a GitHub repository at a specific commit and counts lines of code.
"""

import os
import subprocess
import tempfile
import shutil
import argparse
from pathlib import Path
from typing import Dict, Set, Tuple
import re


class GitHubLineCounter:
    """Class to handle GitHub repository line counting operations."""
    
    # Common source code file extensions
    SOURCE_EXTENSIONS = {
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.hpp', '.cc', '.cxx',
        '.cs', '.rb', '.php', '.go', '.rs', '.swift', '.kt', '.scala', '.r',
        '.m', '.mm', '.pl', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat',
        '.html', '.htm', '.css', '.scss', '.sass', '.less', '.xml', '.json',
        '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.sql', '.md',
        '.tex', '.vue', '.jsx', '.tsx', '.dart', '.elm', '.clj', '.cljs',
        '.hs', '.ml', '.fs', '.vb', '.pas', '.dpr', '.asm', '.s'
    }
    
    # Files to exclude (binary files, images, etc.)
    EXCLUDE_EXTENSIONS = {
        '.exe', '.dll', '.so', '.dylib', '.a', '.lib', '.o', '.obj',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg', '.tiff',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.wav',
        '.ttf', '.woff', '.woff2', '.eot'
    }
    
    # Directories to exclude
    EXCLUDE_DIRS = {
        '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
        '.tox', 'build', 'dist', '.idea', '.vscode', 'target',
        'bin', 'obj', '.gradle', '.mvn', 'vendor', 'bower_components'
    }

    def __init__(self):
        self.temp_dir = None

    def parse_github_url(self, url: str) -> Tuple[str, str]:
        """
        Parse GitHub URL to extract owner and repository name.
        
        Args:
            url (str): GitHub repository URL
            
        Returns:
            Tuple[str, str]: (owner, repo_name)
        """
        # Remove .git suffix if present
        url = url.rstrip('.git')
        
        # Handle both HTTPS and SSH formats
        if url.startswith('https://github.com/'):
            path = url[len('https://github.com/'):]
        elif url.startswith('git@github.com:'):
            path = url[len('git@github.com:'):]
        else:
            raise ValueError(f"Invalid GitHub URL format: {url}")
        
        parts = path.split('/')
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL format: {url}")
        
        owner, repo_name = parts[0], parts[1]
        return owner, repo_name

    def clone_repository(self, github_url: str, commit_id: str) -> str:
        """
        Clone the GitHub repository and checkout the specific commit.
        
        Args:
            github_url (str): GitHub repository URL
            commit_id (str): Git commit ID to checkout
            
        Returns:
            str: Path to the cloned repository
        """
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix='github_line_counter_')
        repo_path = os.path.join(self.temp_dir, 'repo')
        
        try:
            # Clone the repository
            print(f"Cloning repository: {github_url}")
            subprocess.run([
                'git', 'clone', github_url, repo_path
            ], check=True, capture_output=True, text=True)
            
            # Checkout the specific commit
            print(f"Checking out commit: {commit_id}")
            subprocess.run([
                'git', 'checkout', commit_id
            ], cwd=repo_path, check=True, capture_output=True, text=True)
            
            return repo_path
            
        except subprocess.CalledProcessError as e:
            self.cleanup()
            raise RuntimeError(f"Git operation failed: {e.stderr}")

    def should_count_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be counted based on its extension and location.
        
        Args:
            file_path (Path): Path to the file
            
        Returns:
            bool: True if the file should be counted
        """
        # Check if any parent directory should be excluded
        for parent in file_path.parents:
            if parent.name in self.EXCLUDE_DIRS:
                return False
        
        # Check file extension
        ext = file_path.suffix.lower()
        
        # Exclude binary/media files
        if ext in self.EXCLUDE_EXTENSIONS:
            return False
        
        # Only count known source code files
        if ext in self.SOURCE_EXTENSIONS:
            return True
        
        # For files without extensions, check if they look like source code
        if not ext:
            try:
                # Try to read a small sample to see if it's text
                with open(file_path, 'rb') as f:
                    sample = f.read(1024)
                    # Simple heuristic: if it's mostly printable ASCII, it's probably text
                    if len(sample) > 0:
                        printable_ratio = sum(32 <= b <= 126 or b in [9, 10, 13] for b in sample) / len(sample)
                        return printable_ratio > 0.7
            except:
                return False
        
        return False

    def count_lines_in_file(self, file_path: Path) -> Dict[str, int]:
        """
        Count different types of lines in a single file.
        
        Args:
            file_path (Path): Path to the file
            
        Returns:
            Dict[str, int]: Dictionary with line counts
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except:
            return {'total': 0, 'code': 0, 'comments': 0, 'blank': 0}
        
        total_lines = len(lines)
        blank_lines = 0
        comment_lines = 0
        
        # Simple comment detection patterns
        comment_patterns = [
            r'^\s*#',          # Python, Shell, etc.
            r'^\s*//',         # C++, Java, JavaScript, etc.
            r'^\s*/\*',        # C-style multiline comments
            r'^\s*\*',         # Continuation of multiline comments
            r'^\s*<!--',       # HTML comments
            r'^\s*%',          # LaTeX, MATLAB
            r'^\s*"',          # VimScript (sometimes)
        ]
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            else:
                is_comment = any(re.match(pattern, line) for pattern in comment_patterns)
                if is_comment:
                    comment_lines += 1
        
        code_lines = total_lines - blank_lines - comment_lines
        
        return {
            'total': total_lines,
            'code': code_lines,
            'comments': comment_lines,
            'blank': blank_lines
        }

    def count_lines_in_directory(self, directory: str) -> Dict[str, any]:
        """
        Count lines of code in all eligible files in a directory.
        
        Args:
            directory (str): Path to the directory
            
        Returns:
            Dict[str, any]: Summary of line counts and file information
        """
        total_stats = {'total': 0, 'code': 0, 'comments': 0, 'blank': 0}
        file_stats = {}
        file_count = 0
        
        directory_path = Path(directory)
        
        print("Counting lines of code...")
        
        for file_path in directory_path.rglob('*'):
            if file_path.is_file() and self.should_count_file(file_path):
                file_count += 1
                relative_path = file_path.relative_to(directory_path)
                
                stats = self.count_lines_in_file(file_path)
                file_stats[str(relative_path)] = stats
                
                # Add to totals
                for key in total_stats:
                    total_stats[key] += stats[key]
                
                if file_count % 100 == 0:
                    print(f"Processed {file_count} files...")
        
        return {
            'total_stats': total_stats,
            'file_stats': file_stats,
            'file_count': file_count
        }

    def cleanup(self):
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def count_lines_of_code(self, github_url: str, commit_id: str) -> Dict[str, any]:
        """
        Main method to count lines of code in a GitHub repository at a specific commit.
        
        Args:
            github_url (str): GitHub repository URL
            commit_id (str): Git commit ID
            
        Returns:
            Dict[str, any]: Complete results including statistics and file breakdown
        """
        try:
            # Parse the GitHub URL
            owner, repo_name = self.parse_github_url(github_url)
            
            # Clone repository and checkout commit
            repo_path = self.clone_repository(github_url, commit_id)
            
            # Count lines of code
            results = self.count_lines_in_directory(repo_path)
            
            # Add repository information
            results['repository_info'] = {
                'url': github_url,
                'owner': owner,
                'name': repo_name,
                'commit_id': commit_id
            }
            
            return results
            
        finally:
            # Always cleanup
            self.cleanup()


def main():
    """Main function to run the line counter as a CLI tool."""
    parser = argparse.ArgumentParser(description='Count lines of code in a GitHub repository at a specific commit')
    parser.add_argument('github_url', help='GitHub repository URL')
    parser.add_argument('commit_id', help='Git commit ID to checkout')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed file statistics')
    
    args = parser.parse_args()
    
    counter = GitHubLineCounter()
    
    try:
        print(f"Analyzing repository: {args.github_url}")
        print(f"At commit: {args.commit_id}")
        print("-" * 50)
        
        results = counter.count_lines_of_code(args.github_url, args.commit_id)
        
        # Display results
        repo_info = results['repository_info']
        stats = results['total_stats']
        
        print(f"\nRepository: {repo_info['owner']}/{repo_info['name']}")
        print(f"Commit: {repo_info['commit_id']}")
        print(f"Files processed: {results['file_count']}")
        print("-" * 30)
        print(f"Total lines: {stats['total']:,}")
        print(f"Code lines: {stats['code']:,}")
        print(f"Comment lines: {stats['comments']:,}")
        print(f"Blank lines: {stats['blank']:,}")
        
        if args.verbose:
            print("\nFile breakdown:")
            print("-" * 50)
            for file_path, file_stats in results['file_stats'].items():
                print(f"{file_path}: {file_stats['total']} total, {file_stats['code']} code")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
