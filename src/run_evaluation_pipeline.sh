#!/bin/bash

# Complete Evaluation Pipeline Script
# This script runs the full documentation evaluation pipeline:
# 1. Run evaluations with multiple LLMs
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
DEFAULT_REFERENCE=""
DEFAULT_MODELS="gpt4.1-mini,kimi-k2-instruct,glm-4p5"  # Default models to use
DEFAULT_BATCH_SIZE=5
DEFAULT_COMBINATION_METHOD="average"
DEFAULT_USE_TOOLS="true"
DEFAULT_ENABLE_RETRY="false"
DEFAULT_MAX_RETRIES=2

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

Complete Documentation Evaluation Pipeline

REQUIRED:
  --repo-name NAME           Repository name (required)
  --reference NAME           Name of the folder that contains the reference documentation needed for evaluation (default: deepwiki)

OPTIONAL:
  --models LIST             Comma-separated list of models (optional, uses defaults)
  --batch-size N            Batch size for evaluation (default: 5)
  --combination-method M    Method to combine results (default: average)
                           Options: average, majority_vote, weighted_average, max, min
  --weights W1,W2,W3        Weights for weighted_average (e.g., 0.4,0.3,0.3)
  --skip-evaluation         Skip evaluation step (only combine existing results)
  --skip-combination        Skip combination step
  --no-tools                Disable tools for document navigation
  --no-retry                Disable retry for error cases
  --max-retries N           Maximum number of retries (default: 2)
  --visualize               Run visualization after evaluation
  --help                    Show this help message

EXAMPLES:
  # Basic usage
  $0 --repo-name myrepo

  # Advanced usage
  $0 --repo-name myrepo --models claude-sonnet-4,kimi-k2-instruct --combination-method weighted_average --weights 0.6,0.4 --visualize

  # Only combine existing results
  $0 --repo-name myrepo --skip-evaluation

EOF
}

# Parse command line arguments
REPO_NAME=""
REFERENCE=""
MODELS="$DEFAULT_MODELS"
BATCH_SIZE="$DEFAULT_BATCH_SIZE"
COMBINATION_METHOD="$DEFAULT_COMBINATION_METHOD"
WEIGHTS=""
SKIP_EVALUATION=false
SKIP_COMBINATION=false
USE_TOOLS="$DEFAULT_USE_TOOLS"
ENABLE_RETRY="$DEFAULT_ENABLE_RETRY"
MAX_RETRIES="$DEFAULT_MAX_RETRIES"
VISUALIZE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo-name)
            REPO_NAME="$2"
            shift 2
            ;;
        --reference)
            REFERENCE="$2"
            shift 2
            ;;

        --models)
            MODELS="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --combination-method)
            COMBINATION_METHOD="$2"
            shift 2
            ;;
        --weights)
            WEIGHTS="$2"
            shift 2
            ;;
        --skip-evaluation)
            SKIP_EVALUATION=true
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
        --no-retry)
            ENABLE_RETRY=false
            shift
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
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

# Models will be processed individually in the evaluation loop

# Validate data directory exists
# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data/$REPO_NAME"
if [[ ! -d "$DATA_DIR" ]]; then
    print_error "Data directory not found: $DATA_DIR"
    exit 1
fi

# Check if docs tree exists
DOCS_TREE="$DATA_DIR/deepwiki/docs_tree.json"
if [[ ! -f "$DOCS_TREE" ]]; then
    print_error "Documentation tree not found: $DOCS_TREE"
    print_error "Please run the documentation parsing step first"
    exit 1
fi

print_status "Starting evaluation pipeline for repository: $REPO_NAME"
print_status "Models to use: $MODELS"
print_status "Data directory: $DATA_DIR"

# Change to source directory
# cd $SCRIPT_DIR


# Step 1: Run evaluations
if [[ "$SKIP_EVALUATION" == false ]]; then
    print_step "Step 1: Running evaluations"
    
    # Process each model individually by splitting on commas
    model_index=0
    
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
        print_status "Running evaluation with $model..."
        
        # Build evaluation command
        eval_cmd="python judge/judge.py --repo-name \"$REPO_NAME\" --model \"$model\" --batch-size $BATCH_SIZE --max-retries $MAX_RETRIES --reference \"$REFERENCE\""
        
        # Add optional flags
        if [[ "$USE_TOOLS" == true ]]; then
            eval_cmd="$eval_cmd --use-tools"
        fi
        
        if [[ "$ENABLE_RETRY" == true ]]; then
            eval_cmd="$eval_cmd --enable-retry"
        fi
        
        print_status "Running: $eval_cmd"
        eval $eval_cmd
        
        if [[ $? -eq 0 ]]; then
            print_status "✓ Evaluation completed for $model"
        else
            print_error "✗ Evaluation failed for $model"
            exit 1
        fi
        
        model_index=$((model_index + 1))
    done
else
    print_status "Skipping evaluation step"
fi

# Step 2: Combine results
# Count the number of models to determine if combination is needed
model_count=0
temp_models="$MODELS"
while [[ -n "$temp_models" ]]; do
    if [[ "$temp_models" == *","* ]]; then
        temp_models="${temp_models#*,}"
    else
        temp_models=""
    fi

    model_count=$((model_count + 1))
done

if [[ "$SKIP_COMBINATION" == false ]] && [[ $model_count -gt 1 ]]; then
    print_step "Step 2: Combining evaluation results"
    
    # Build combination command
    combine_cmd="python judge/combine_evaluations.py --repo-name \"$REPO_NAME\" --method \"$COMBINATION_METHOD\" --reference \"$REFERENCE\""
    
    # Add weights if specified
    if [[ -n "$WEIGHTS" ]]; then
        combine_cmd="$combine_cmd --weights \"$WEIGHTS\""
    fi
    
    print_status "Running: $combine_cmd"
    eval $combine_cmd
    
    if [[ $? -eq 0 ]]; then
        print_status "✓ Results combination completed"
    else
        print_error "✗ Results combination failed"
        exit 1
    fi
elif [[ $model_count -eq 1 ]]; then
    print_status "Skipping combination (only one model used)"
else
    print_status "Skipping combination step"
fi

# Step 3: Visualization (optional)
if [[ "$VISUALIZE" == true ]]; then
    print_step "Step 3: Generating visualizations"
    
    # Check if visualization script exists
    if [[ -f "judge/visualize_evaluation.py" ]]; then
        python judge/visualize_evaluation.py --repo-name "$REPO_NAME" --reference "$REFERENCE"
        if [[ $? -eq 0 ]]; then
            print_status "✓ Visualization completed"
        else
            print_warning "Visualization failed but pipeline continues"
        fi
    else
        print_warning "Visualization script not found: judge/visualize_evaluation.py"
    fi
fi

# Final summary
print_step "Pipeline completed successfully!"
print_status "Results location: $DATA_DIR"

# List output files
echo ""
print_status "Generated files:"
for file in "$DATA_DIR"/*.json; do
    if [[ -f "$file" ]]; then
        filename=$(basename "$file")
        filesize=$(du -h "$file" | cut -f1)
        echo "  - $filename ($filesize)"
    fi
done

# Display final scores if available
echo ""
if [[ -f "$DATA_DIR/evaluation_results_combined.json" ]]; then
    print_status "Combined evaluation results are available in evaluation_results_combined.json"
else
    result_file=$(find "$DATA_DIR" -name "evaluation_results_*.json" | head -1)
    if [[ -f "$result_file" ]]; then
        filename=$(basename "$result_file")
        print_status "Evaluation results are available in $filename"
    fi
fi

print_status "Pipeline execution completed at $(date)" 