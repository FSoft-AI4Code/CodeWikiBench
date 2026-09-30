# CodeWikiBench

## 📚 Dataset

The benchmark dataset is available on HuggingFace:
- **Dataset**: [anhnh2002/codewikibench](https://huggingface.co/datasets/anhnh2002/codewikibench)
- **Paper**: [arXiv:2510.24428](https://arxiv.org/abs/2510.24428)

### Dataset Overview

The dataset contains benchmark data for 22 open-source repositories across multiple programming languages:
- **JS/TS**: Chart.js, marktext, puppeteer, storybook, mermaid, svelte
- **Python**: graphrag, rasa, OpenHands
- **C**: qmk_firmware, libsql, sumatrapdf, wazuh
- **C++**: electron, x64dbg, json
- **C#**: FluentValidation, git-credential-manager, ml-agents
- **Java**: logstash, material-components-android, trino

Each repository includes:
- **metadata**: Repository URL and commit ID
- **docs_tree**: Original documentation tree structure
- **structured_docs**: Parsed and structured documentation
- **rubrics**: Evaluation rubrics for assessing documentation quality

### Using the Dataset

```python
from datasets import load_dataset
import json

# Load the dataset
dataset = load_dataset("anhnh2002/codewikibench")

# Access a specific repository
repo_data = dataset['train'][0]
print(f"Repository: {repo_data['repo_name']}")
print(f"Commit: {repo_data['commit_id']}")

# Parse JSON fields
docs_tree = json.loads(repo_data['docs_tree'])
structured_docs = json.loads(repo_data['structured_docs'])
rubrics = json.loads(repo_data['rubrics'])
```

## Installation

Install the package first (Python >= 3.10). The `[caw]` extra enables CLI coding agents
(Claude Code / Codex, model strings `caw:<claude_code|codex>:<model>`) as rubric generators and judges:

```bash
pip install -e .[caw]          # or: uv pip install -e '.[caw]'
pip install -e .[caw,assess]   # + numpy/scikit-learn for rubrics_generator/assess_rubrics.py
```

API models are called through an OpenAI-compatible endpoint configured by `BASE_URL`, `API_KEY`
and `MODEL` (read from the environment or a `.env` file found from the current directory upwards).

The legacy `--repo-name` scripts read/write `data/<repo>/...`. The data dir resolves to
`$CWB_DATA_DIR` if set, else `<repo root>/data` for a source checkout (editable install),
else `./data` relative to the current directory.

## `codewikibench` CLI

All subcommands take explicit paths:

```bash
# 1. parse CodeWiki (or DeepWiki) markdown output -> docs_tree.json + structured_docs.json
codewikibench parse --docs-dir path/to/codewiki/docs --out work/parsed [--project-name X]

# 2. rubrics from reference docs (one set per --model, then combined; language-agnostic prompt by default)
codewikibench rubrics --docs work/reference_parsed --out work/rubrics.json \
    --model caw:claude_code:sonnet [--model gpt-oss-120b] [--use-tools] [--no-language-agnostic] [--force]

# 3. judge docs against rubrics (per-model results next to --out as <stem>.<model>.json)
codewikibench judge --rubrics work/rubrics.json --docs work/parsed --out work/results.json \
    --model caw:claude_code:haiku [--model M2] [--batch-size 4] [--use-tools] [--enable-retry] [--method average] [--force]

# 4. list failed leaves (score <= --max-score, or evaluation errors)
codewikibench report --results work/results.json [--format json|markdown|summary] [--max-score 0.99]
```

Existing outputs are reused (with a message) unless `--force` is given. A leaf whose evaluation raised
an error is scored 0 with `evaluation.error: true` and `[EVALUATION ERROR]` in its reasoning;
`--enable-retry` re-judges such leaves.

The individual scripts below are also runnable as modules, e.g.
`python -m codewikibench.judge.judge --repo-name OpenHands --reference codewiki --model ...`
(run the shell pipelines from `src/`).

## Parsing Documentations
### Official Documemtation
Pull docs folder from original repository ([example result](examples/OpenHands/original/docs))
```bash
bash ./download_github_folder.sh --github_repo_url https://github.com/All-Hands-AI/OpenHands.git --folder_path docs --commit_id <COMMIT_ID>
```
Parse official docs ([example result](examples/OpenHands/original))
```bash
python -m codewikibench.docs_parser.parse_official_docs --repo_name OpenHands
```

Crawl deepwiki docs ([example result](examples/OpenHands/deepwiki/docs))
```bash
python -m codewikibench.docs_parser.crawl_deepwiki_docs --url https://deepwiki.com/AnhMinh-Le/OpenHands --output-dir ../data/OpenHands/deepwiki/docs
```

Parse deepwiki docs ([example result](examples/OpenHands/deepwiki))
```bash
python -m codewikibench.docs_parser.parse_generated_docs --input-dir ../data/OpenHands/deepwiki/docs --output-dir ../data/OpenHands/deepwiki
```

Parse codewiki docs ([example example](examples/OpenHands/codewiki))
```bash
python -m codewikibench.docs_parser.parse_generated_docs --input-dir /home/anhnh/CodeWiki/output/docs/All-Hands-AI--OpenHands --output-dir ../data/OpenHands/codewiki
```

[NOTE] To evaluate any other types of documentation, you need to parse it into structured_docs.json and its backbone docs_tree.json (see [parsed example](examples/OpenHands/codewiki))

## Rubrics Generation
Generate rubrics with multiple models
```bash
bash ./run_rubrics_pipeline.sh --repo-name OpenHands --models claude-sonnet-4,kimi-k2-instruct --visualize
```

## Evaluation
### Complete Evaluation Pipeline
Run evaluation with multiple models
```bash
bash ./run_evaluation_pipeline.sh --repo-name OpenHands --reference deepwiki-agent --models kimi-k2-instruct --visualize --batch-size 8
bash ./run_evaluation_pipeline.sh --repo-name OpenHands --reference deepwiki-agent --models kimi-k2-instruct,gpt-oss-120b,gemini-2.5-flash --visualize --batch-size 4
```


### Visualize Results
```bash
# Using the complete pipeline (recommended)
bash ./run_evaluation_pipeline.sh --repo-name OpenHands --reference deepwiki --visualize

# Manual visualization of specific results
# Summary view
python -m codewikibench.judge.visualize_evaluation --repo-name OpenHands --reference deepwiki --format summary

# Detailed view with all requirements  
python -m codewikibench.judge.visualize_evaluation --repo-name OpenHands --reference deepwiki --format detailed

# Show only poorly documented requirements (score < 0.5)
python -m codewikibench.judge.visualize_evaluation --repo-name OpenHands --reference deepwiki --format detailed --max-score 0.5

# Export to CSV for analysis
python -m codewikibench.judge.visualize_evaluation --repo-name OpenHands --reference deepwiki --format csv

# Export to Markdown report
python -m codewikibench.judge.visualize_evaluation --repo-name OpenHands --reference deepwiki --format markdown
```

## Lines of Code
```bash
# Count lines in the main branch (use the latest commit ID)
python3 count_lines_of_code.py https://github.com/All-Hands-AI/OpenHands.git HEAD

# Count lines at a specific commit
python3 count_lines_of_code.py https://github.com/All-Hands-AI/OpenHands.git a1b2c3d4e5f6

# Show detailed file-by-file breakdown
python3 count_lines_of_code.py https://github.com/All-Hands-AI/OpenHands.git 30604c40fc6e9ac914089376f41e118582954f22
```

## Citation

If you use this dataset or codebase in your research, please cite:

```bibtex
@misc{hoang2025codewikievaluatingaisability,
      title={CodeWiki: Evaluating AI's Ability to Generate Holistic Documentation for Large-Scale Codebases}, 
      author={Anh Nguyen Hoang and Minh Le-Anh and Bach Le and Nghi D. Q. Bui},
      year={2025},
      eprint={2510.24428},
      archivePrefix={arXiv},
      primaryClass={cs.SE},
      url={https://arxiv.org/abs/2510.24428},
}
```