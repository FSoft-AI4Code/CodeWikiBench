#!/bin/bash

# GitHub Folder Downloader Script
# Usage: ./download_github_folder.sh --github_repo_url <url> --folder_path <path> [--commit_id <commit>]
# Example: ./download_github_folder.sh --github_repo_url https://github.com/infiniflow/ragflow --folder_path docs
# Example with commit: ./download_github_folder.sh --github_repo_url https://github.com/infiniflow/ragflow --folder_path docs --commit_id abc123

set -e  # Exit on any error

# Function to display usage
usage() {
    echo "Usage: $0 --github_repo_url <url> --folder_path <path> [--commit_id <commit>]"
    echo ""
    echo "Examples:"
    echo "  $0 --github_repo_url https://github.com/infiniflow/ragflow --folder_path docs"
    echo "  $0 --folder_path src/components --github_repo_url https://github.com/user/repo"
    echo "  $0 --github_repo_url https://github.com/user/repo --folder_path docs --commit_id abc123456"
    echo ""
    echo "Parameters:"
    echo "  --github_repo_url: Full GitHub repository URL (https://github.com/user/repo)"
    echo "  --folder_path:     Path to the folder within the repo (e.g., docs, src/components)"
    echo "  --commit_id:       Optional specific commit ID to download from (SHA hash)"
    echo ""
    echo "Target directory will be automatically set to: ../data/{repo_name}/original"
    exit 1
}

# Initialize variables
REPO_URL=""
FOLDER_PATH=""
COMMIT_ID=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --github_repo_url)
            REPO_URL="$2"
            shift 2
            ;;
        --folder_path)
            FOLDER_PATH="$2"
            shift 2
            ;;
        --commit_id)
            COMMIT_ID="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: Unknown parameter $1"
            usage
            ;;
    esac
done

# Check if required parameters are provided
if [ -z "$REPO_URL" ]; then
    echo "Error: --github_repo_url parameter is required"
    usage
fi

if [ -z "$FOLDER_PATH" ]; then
    echo "Error: --folder_path parameter is required"
    usage
fi

# Extract repo name from URL for target directory
REPO_NAME=$(basename "$REPO_URL" .git)

# Automatically set target directory based on repo name
TARGET_DIR="../data/$REPO_NAME/original"

echo "🚀 Starting download..."
echo "Repository: $REPO_URL"
echo "Folder: $FOLDER_PATH"
if [ -n "$COMMIT_ID" ]; then
    echo "Commit ID: $COMMIT_ID"
fi
echo "Target: $TARGET_DIR (auto-generated)"
echo ""

# Create target directory
echo "📁 Creating target directory..."
mkdir -p "$TARGET_DIR"

# Navigate to target directory
cd "$TARGET_DIR"

# Initialize git repository
echo "🔧 Initializing git repository..."
git init

# Add remote origin
echo "🔗 Adding remote repository..."
git remote add origin "$REPO_URL"

# Enable sparse-checkout
echo "⚙️  Enabling sparse-checkout..."
git config core.sparseCheckout true

# Configure sparse-checkout to include only the specified folder
echo "📋 Configuring sparse-checkout for folder: $FOLDER_PATH"
echo "$FOLDER_PATH/*" > .git/info/sparse-checkout

if [ -n "$COMMIT_ID" ]; then
    # Use specific commit ID
    echo "📌 Using commit: $COMMIT_ID"
    echo "⬇️  Downloading folder content..."
    git fetch origin
    git checkout "$COMMIT_ID"
else
    # Detect the default branch
    echo "🔍 Detecting default branch..."
    DEFAULT_BRANCH=$(git remote show origin | grep 'HEAD branch' | cut -d' ' -f5)
    if [ -z "$DEFAULT_BRANCH" ]; then
        # Fallback: try common branch names
        echo "⚠️  Could not detect default branch, trying common names..."
        for branch in main master develop; do
            if git ls-remote --heads origin "$branch" | grep -q "$branch"; then
                DEFAULT_BRANCH="$branch"
                break
            fi
        done
        
        if [ -z "$DEFAULT_BRANCH" ]; then
            echo "❌ Error: Could not determine the default branch"
            exit 1
        fi
    fi

    echo "📌 Using branch: $DEFAULT_BRANCH"
    
    # Pull the content
    echo "⬇️  Downloading folder content..."
    git pull origin "$DEFAULT_BRANCH"
fi

# Check if the folder was downloaded successfully
if [ -d "$FOLDER_PATH" ]; then
    echo ""
    echo "✅ Success! Folder downloaded to: $TARGET_DIR/$FOLDER_PATH"
    echo ""
    echo "📊 Contents:"
    ls -la "$FOLDER_PATH"
else
    echo ""
    echo "❌ Error: Folder '$FOLDER_PATH' not found in the repository"
    echo "Please check if the folder path is correct"
    exit 1
fi

echo ""
echo "🎉 Download completed successfully!" 