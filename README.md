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

## Parsing Documentations
### Official Documemtation
Pull docs folder from original repository ([example result](examples/OpenHands/original/docs))
```bash
bash ./download_github_folder.sh --github_repo_url https://github.com/All-Hands-AI/OpenHands.git --folder_path docs --commit_id <COMMIT_ID>
```
Parse official docs ([example result](examples/OpenHands/original))
```bash
python docs_parser/parse_official_docs.py --repo_name OpenHands
```

Crawl deepwiki docs ([example result](examples/OpenHands/deepwiki/docs))
```bash
python docs_parser/crawl_deepwiki_docs.py --url https://deepwiki.com/AnhMinh-Le/OpenHands --output-dir ../data/OpenHands/deepwiki/docs
```

Parse deepwiki docs ([example result](examples/OpenHands/deepwiki))
```bash
python docs_parser/parse_generated_docs.py --input-dir ../data/OpenHands/deepwiki/docs --output-dir ../data/OpenHands/deepwiki
```

Parse codewiki docs ([example example](examples/OpenHands/codewiki))
```bash
python docs_parser/parse_generated_docs.py --input-dir /home/anhnh/CodeWiki/output/docs/All-Hands-AI--OpenHands --output-dir ../data/OpenHands/codewiki
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
python judge/visualize_evaluation.py --repo-name OpenHands --reference deepwiki --format summary

# Detailed view with all requirements  
python judge/visualize_evaluation.py --repo-name OpenHands --reference deepwiki --format detailed

# Show only poorly documented requirements (score < 0.5)
python judge/visualize_evaluation.py --repo-name OpenHands --reference deepwiki --format detailed --max-score 0.5

# Export to CSV for analysis
python judge/visualize_evaluation.py --repo-name OpenHands --reference deepwiki --format csv

# Export to Markdown report
python judge/visualize_evaluation.py --repo-name OpenHands --reference deepwiki --format markdown
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