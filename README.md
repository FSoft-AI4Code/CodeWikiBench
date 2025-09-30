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

Parse deepwiki docs ([example result](examples/OpenHands/deepwiki/docs))
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