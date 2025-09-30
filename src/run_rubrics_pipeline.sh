#!/bin/bash

# Complete Rubrics Generation Pipeline Script
# This script runs the full rubrics generation pipeline:
# 1. Generate rubrics with multiple LLMs
# 2. Combine results
# 3. Optional visualization

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_REPO_NAME=""
DEFAULT_MODELS="claude-sonnet-4,kimi-k2-instruct,glm-4p5"  # Will use default models from config
DEFAULT_USE_TOOLS="true"
DEFAULT_TEMPERATURE=0.1
DEFAULT_MAX_RETRIES=3

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Complete Rubrics Generation Pipeline

REQUIRED:
  --repo-name NAME           Repository name (required)

OPTIONAL:
  --models LIST             Comma-separated list of models (optional, uses defaults)
  --temperature FLOAT       Temperature for LLM inference (default: 0.1)
  --max-retries INT          Maximum number of retries for API calls (default: 3)
  --skip-generation         Skip rubrics generation step (only combine existing results)
  --skip-combination        Skip combination step
  --no-tools                Disable tools for document navigation
  --visualize               Run visualization after generation

EXAMPLES:
  # Basic usage
  $0 --repo-name myrepo

  # Advanced usage with specific models
  $0 --repo-name myrepo --models kimi-k2-instruct,glm-4p5 --visualize

  # Only combine existing rubrics
  $0 --repo-name myrepo --skip-generation

  # Generate with tools disabled
  $0 --repo-name myrepo --no-tools

EOF
}

# Parse command line arguments
REPO_NAME=""
MODELS="$DEFAULT_MODELS"
SKIP_GENERATION=false
SKIP_COMBINATION=false
USE_TOOLS="$DEFAULT_USE_TOOLS"
VISUALIZE=false
TEMPERATURE="$DEFAULT_TEMPERATURE"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo-name)
            REPO_NAME="$2"
            shift 2
            ;;
        --models)
            MODELS="$2"
            shift 2
            ;;
        --temperature)
            TEMPERATURE="$2"
            shift 2
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        --skip-generation)
            SKIP_GENERATION=true
            shift
            ;;
        --skip-combination)
            SKIP_COMBINATION=true
            shift
            ;;
        --no-tools)
            USE_TOOLS=false
            shift
            ;;
        --visualize)
            VISUALIZE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$REPO_NAME" ]]; then
    print_error "Repository name is required. Use --repo-name"
    show_usage
    exit 1
fi

# Models will be processed individually in the generation loop

# Validate data directory exists
# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data/$REPO_NAME"
if [[ ! -d "$DATA_DIR" ]]; then
    print_error "Data directory not found: $DATA_DIR"
    exit 1
fi

# Check if docs tree exists (assuming it's in the 'original' subfolder)
DOCS_TREE="$DATA_DIR/original/docs_tree.json"
if [[ ! -f "$DOCS_TREE" ]]; then
    print_error "Documentation tree not found: $DOCS_TREE"
    print_error "Please run the documentation parsing step first"
    exit 1
fi

print_status "Starting rubrics generation pipeline for repository: $REPO_NAME"
print_status "Models to use: $MODELS"
print_status "Data directory: $DATA_DIR"

# Change to source directory
cd $SCRIPT_DIR

# Step 1: Run rubrics generation
if [[ "$SKIP_GENERATION" == false ]]; then
    print_step "Step 1: Generating rubrics"
    
    # Process each model individually by splitting on commas
    llm_index=0
    
    # Use a temporary variable to hold remaining models
    remaining_models="$MODELS"
    
    while [[ -n "$remaining_models" ]]; do
        # Extract the first model (up to comma or end of string)
        if [[ "$remaining_models" == *","* ]]; then
            model="${remaining_models%%,*}"
            remaining_models="${remaining_models#*,}"
        else
            model="$remaining_models"
            remaining_models=""
        fi
        
        # Trim whitespace from model name
        model=$(echo "$model" | xargs)
        print_status "Generating rubrics with $model..."
        
        # Build generation command
        gen_cmd="python rubrics_generator/generate_rubrics.py --repo-name \"$REPO_NAME\" --model \"$model\""
        
        # Add optional flags
        if [[ "$USE_TOOLS" == true ]]; then 
            gen_cmd="$gen_cmd --use-tools"
        fi
        
        print_status "Running: $gen_cmd"
        eval $gen_cmd
        generation_exit_code=$?
        
        if [[ $generation_exit_code -eq 0 ]]; then
            print_status "✓ Rubrics generation completed for $model"
        else
            print_error "✗ Rubrics generation failed for $model (exit code: $generation_exit_code)"
            exit 1
        fi
        
        llm_index=$((llm_index + 1))
    done
else
    print_status "Skipping rubrics generation step"
fi

# Step 2: Combine results
if [[ "$SKIP_COMBINATION" == false ]]; then
    print_step "Step 2: Combining rubrics"
    
    # Build combination command
    combine_cmd="python rubrics_generator/combine_rubrics.py --repo-name \"$REPO_NAME\""

    if [[ -n "$TEMPERATURE" ]]; then
        combine_cmd="$combine_cmd --temperature \"$TEMPERATURE\""
    fi

    if [[ -n "$MAX_RETRIES" ]]; then
        combine_cmd="$combine_cmd --max-retries \"$MAX_RETRIES\""
    fi
    
    print_status "Running: $combine_cmd"
    eval $combine_cmd
    
    if [[ $? -eq 0 ]]; then
        print_status "✓ Rubrics combination completed"
    else
        print_error "✗ Rubrics combination failed"
        exit 1
    fi
else
    print_status "Skipping combination step"
fi

# Step 3: Visualization (optional)
if [[ "$VISUALIZE" == true ]]; then
    print_step "Step 3: Generating visualizations"
    
    # Check if visualization script exists and combined rubrics exists
    COMBINED_RUBRICS="$DATA_DIR/rubrics/combined_rubrics.json"
    if [[ -f "rubrics_generator/visualize_rubrics.py" ]] && [[ -f "$COMBINED_RUBRICS" ]]; then
        python rubrics_generator/visualize_rubrics.py --rubrics-path "$COMBINED_RUBRICS"
        if [[ $? -eq 0 ]]; then
            print_status "✓ Visualization completed"
        else
            print_warning "Visualization failed but pipeline continues"
        fi
    else
        if [[ ! -f "rubrics_generator/visualize_rubrics.py" ]]; then
            print_warning "Visualization script not found: rubrics_generator/visualize_rubrics.py"
        fi
        if [[ ! -f "$COMBINED_RUBRICS" ]]; then
            print_warning "Combined rubrics not found: $COMBINED_RUBRICS"
        fi
    fi
fi

# Final summary
print_step "Pipeline completed successfully!"
print_status "Results location: $DATA_DIR/rubrics"

# List output files
echo ""
print_status "Generated files:"
RUBRICS_DIR="$DATA_DIR/rubrics"
if [[ -d "$RUBRICS_DIR" ]]; then
    for file in "$RUBRICS_DIR"/*.json; do
        if [[ -f "$file" ]]; then
            filename=$(basename "$file")
            filesize=$(du -h "$file" | cut -f1)
            echo "  - $filename ($filesize)"
        fi
    done
else
    print_warning "Rubrics directory not found: $RUBRICS_DIR"
fi

# Display final status
echo ""
COMBINED_RUBRICS="$DATA_DIR/rubrics/combined_rubrics.json"
if [[ -f "$COMBINED_RUBRICS" ]]; then
    print_status "Combined rubrics are available in combined_rubrics.json"
    
    # Try to extract basic stats from the combined rubrics
    if command -v python3 &> /dev/null; then
        stats=$(python3 -c "
import json
try:
    with open('$COMBINED_RUBRICS', 'r') as f:
        data = json.load(f)
    if 'combination_metadata' in data and 'statistics' in data['combination_metadata']:
        stats = data['combination_metadata']['statistics']
        print(f\"Total items: {stats.get('total_items', 'N/A')}\")
        print(f\"Top-level items: {stats.get('top_level_items', 'N/A')}\")
        print(f\"Max depth: {stats.get('max_depth', 'N/A')}\")
except Exception as e:
    pass
" 2>/dev/null)
        if [[ -n "$stats" ]]; then
            echo "$stats"
        fi
    fi
else
    result_file=$(find "$RUBRICS_DIR" -name "*.json" | head -1)
    if [[ -f "$result_file" ]]; then
        filename=$(basename "$result_file")
        print_status "Rubrics are available in $filename"
    fi
fi

print_status "Pipeline execution completed at $(date)" 