"""`codewikibench` command line interface.

Every subcommand takes explicit paths; nothing assumes the data/<repo>/<variant>
layout used by the legacy per-script entry points.

    codewikibench parse   --docs-dir DIR --out PARSED_DIR [--project-name X]
    codewikibench rubrics --docs PARSED_DIR --out RUBRICS.json --model M [--model M2 ...]
    codewikibench judge   --rubrics RUBRICS.json --docs PARSED_DIR --out RESULTS.json --model M [...]
    codewikibench report  --results RESULTS.json [--format json|markdown|summary]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def sanitize_model(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def per_model_path(out: Path, model: str) -> Path:
    """<out_dir>/<out_stem>.<sanitized model>.json"""
    return out.with_name(f"{out.stem}.{sanitize_model(model)}{out.suffix or '.json'}")


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def rubric_list(data: Any) -> List[Dict]:
    if isinstance(data, dict):
        return data.get("rubrics", [])
    return data or []


def require_parsed_docs(docs: Path) -> None:
    missing = [n for n in ("docs_tree.json", "structured_docs.json") if not (docs / n).is_file()]
    if missing:
        sys.exit(f"Error: {docs} is not a parsed docs dir (missing {', '.join(missing)}). "
                 f"Run `codewikibench parse` first.")


def die(msg: str) -> None:
    sys.exit(f"Error: {msg}")


# --------------------------------------------------------------------------
# parse
# --------------------------------------------------------------------------

def cmd_parse(args) -> int:
    from codewikibench.docs_parser.parse_generated_docs import parse_deepwiki

    docs_dir = os.path.normpath(os.path.abspath(args.docs_dir))
    if not os.path.isdir(docs_dir):
        die(f"docs dir does not exist: {docs_dir}")
    md_files = [f for f in os.listdir(docs_dir) if f.endswith(".md")]
    if not md_files:
        die(f"no .md files found in {docs_dir}")

    project_name = args.project_name
    if not project_name:
        base = os.path.basename(docs_dir)
        project_name = os.path.basename(os.path.dirname(docs_dir)) if base == "docs" else base

    out = Path(args.out).absolute()
    has_tree = os.path.isfile(os.path.join(docs_dir, "module_tree.json"))
    print(f"Parsing {len(md_files)} md files from {docs_dir} as project '{project_name}'"
          f"{' (using module_tree.json)' if has_tree else ''}")
    result = parse_deepwiki(docs_dir, project_name, str(out))
    if result is None:
        die("parsing failed")
    root_page, _ = result
    print(f"Wrote {out / 'docs_tree.json'}")
    print(f"Wrote {out / 'structured_docs.json'}")
    print(f"Top-level sections: {len(root_page.subpages)}")
    return 0


# --------------------------------------------------------------------------
# rubrics
# --------------------------------------------------------------------------

async def _rubrics(args) -> int:
    from codewikibench.rubrics_generator.generate_rubrics import (
        extract_rubrics_json, generate_rubrics_raw, normalize_rubrics,
    )
    from codewikibench.rubrics_generator.combine_rubrics import (
        calculate_rubrics_statistics, semantic_combine_rubrics,
    )

    docs = Path(args.docs).absolute()
    require_parsed_docs(docs)
    out = Path(args.out).absolute()

    if out.exists() and not args.force:
        print(f"Reusing existing combined rubrics: {out} (pass --force to regenerate)")
        return 0

    all_rubrics: List[List[Dict]] = []
    used_models: List[str] = []
    for model in args.model:
        model_file = per_model_path(out, model)
        if model_file.exists() and not args.force:
            print(f"[{model}] Reusing existing rubrics: {model_file}")
            rubrics = normalize_rubrics(load_json(model_file))
        else:
            print(f"[{model}] Generating rubrics from {docs} "
                  f"(use_tools={args.use_tools}, language_agnostic={args.language_agnostic})...")
            raw = await generate_rubrics_raw(
                str(docs), model, use_tools=args.use_tools, language_agnostic=args.language_agnostic,
            )
            try:
                rubrics = normalize_rubrics(extract_rubrics_json(raw))
            except ValueError as e:
                raw_file = model_file.with_suffix(".raw.txt")
                raw_file.parent.mkdir(parents=True, exist_ok=True)
                raw_file.write_text(raw or "", encoding="utf-8")
                print(f"[{model}] {e}; raw output saved to {raw_file}")
                continue
            if not rubrics:
                print(f"[{model}] Model returned an empty rubric list; skipping")
                continue
            write_json(model_file, rubrics)
            print(f"[{model}] Rubrics saved to: {model_file}")
        all_rubrics.append(rubrics)
        used_models.append(model)

    if not all_rubrics:
        die("no rubric set could be generated")

    combine_model = args.combine_model or args.model[0]
    if len(all_rubrics) == 1:
        combined = all_rubrics[0]
        method = "single_model"
    else:
        print(f"Combining {len(all_rubrics)} rubric sets with {combine_model}...")
        combined = await semantic_combine_rubrics(
            all_rubrics, model=combine_model, temperature=args.temperature,
            max_retries=args.max_retries, language_agnostic=args.language_agnostic,
        )
        combined = normalize_rubrics(combined)
        method = "semantic_llm"

    stats = calculate_rubrics_statistics(combined)
    result = {
        "rubrics": combined,
        "combination_metadata": {
            "combination_method": method,
            "llm_model": combine_model if method == "semantic_llm" else None,
            "source_models": used_models,
            "temperature": args.temperature,
            "num_rubrics_combined": len(all_rubrics),
            "max_retries": args.max_retries,
            "use_tools": args.use_tools,
            "language_agnostic": args.language_agnostic,
            "docs": str(docs),
            "statistics": stats,
        },
    }
    write_json(out, result)
    print(f"Combined rubrics saved to: {out}")
    print(f"Items: {stats['total_items']}  top-level: {stats['top_level_items']}  "
          f"max depth: {stats['max_depth']}  weights: {stats['weight_distribution']}")
    return 0


def cmd_rubrics(args) -> int:
    return asyncio.run(_rubrics(args))


# --------------------------------------------------------------------------
# judge
# --------------------------------------------------------------------------

async def _judge(args) -> int:
    from codewikibench.judge.judge import evaluate_rubrics
    from codewikibench.judge.combine_evaluations import combine_evaluation_results
    from codewikibench.rubrics_generator.generate_rubrics import normalize_rubrics

    rubrics_path = Path(args.rubrics).absolute()
    if not rubrics_path.is_file():
        die(f"rubrics file not found: {rubrics_path}")
    docs = Path(args.docs).absolute()
    require_parsed_docs(docs)
    out = Path(args.out).absolute()

    if out.exists() and not args.force:
        print(f"Reusing existing results: {out} (pass --force to re-judge)")
        _print_overall(load_json(out))
        return 0

    rubrics = normalize_rubrics(rubric_list(load_json(rubrics_path)))
    if not rubrics:
        die(f"no rubrics found in {rubrics_path}")
    print(f"Loaded rubrics from: {rubrics_path}")

    evaluations = []
    for model in args.model:
        model_file = per_model_path(out, model)
        if model_file.exists() and not args.force:
            print(f"[{model}] Reusing existing evaluation: {model_file}")
            evaluations.append(rubric_list(load_json(model_file)))
            continue
        print(f"[{model}] Judging {docs} ...")
        scored, _ = await evaluate_rubrics(
            rubrics, str(docs), model=model, use_tools=args.use_tools,
            batch_size=args.batch_size, enable_retry=args.enable_retry, max_retries=args.max_retries,
        )
        write_json(model_file, scored)
        print(f"[{model}] Evaluation saved to: {model_file}")
        evaluations.append(scored)

    weights = None
    if args.weights:
        weights = [float(w) for w in args.weights.split(",")]
    result = combine_evaluation_results(evaluations, args.method, weights)
    meta = result["combination_metadata"]
    meta["models"] = list(args.model)
    meta["rubrics"] = str(rubrics_path)
    meta["docs"] = str(docs)
    meta["per_model_files"] = [str(per_model_path(out, m)) for m in args.model]
    write_json(out, result)
    print(f"Combined results saved to: {out}")
    _print_overall(result)
    return 0


def _print_overall(result: Any) -> None:
    meta = result.get("combination_metadata", {}) if isinstance(result, dict) else {}
    if "overall_score" in meta:
        print(f"Overall score: {meta['overall_score']:.4f}"
              f" (leaves: {meta.get('num_leaves', '?')}, errors: {meta.get('num_error_leaves', '?')})")


def cmd_judge(args) -> int:
    return asyncio.run(_judge(args))


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def collect_leaves(items: List[Dict], prefix: str = "") -> List[Dict]:
    leaves = []
    for i, item in enumerate(items):
        path = f"{prefix}.{i}" if prefix else str(i)
        if item.get("sub_tasks"):
            leaves.extend(collect_leaves(item["sub_tasks"], path))
        else:
            ev = item.get("evaluation", {}) or {}
            reasoning = str(ev.get("reasoning", ""))
            # older result files lack the flag; they only carry the reasoning tag
            is_error = bool(ev.get("error")) or "[evaluation error]" in reasoning.lower()
            leaves.append({
                "path": path,
                "requirements": item.get("requirements", ""),
                "weight": item.get("weight"),
                "score": item.get("score", ev.get("score", 0)),
                "reasoning": ev.get("reasoning", ""),
                "evidence": ev.get("evidence", ""),
                "error": is_error,
            })
    return leaves


def build_report(results: Any, max_score: float) -> Dict[str, Any]:
    rubrics = rubric_list(results)
    meta = results.get("combination_metadata", {}) if isinstance(results, dict) else {}
    leaves = collect_leaves(rubrics)
    # errored leaves are never a pass, whatever score an older judge recorded for them
    failed = [leaf for leaf in leaves if (leaf["score"] or 0) <= max_score or leaf["error"]]
    if "overall_score" in meta:
        overall = meta["overall_score"]
    else:
        tw = sum(r.get("weight", 1) for r in rubrics)
        overall = sum(r.get("score", 0) * r.get("weight", 1) for r in rubrics) / tw if tw else 0.0
    return {
        "overall_score": overall,
        "num_leaves": len(leaves),
        "num_failed": len(failed),
        "num_error_leaves": sum(1 for leaf in leaves if leaf["error"]),
        "max_score": max_score,
        "top_level": [
            {"path": str(i), "requirements": r.get("requirements", ""), "weight": r.get("weight"),
             "score": r.get("score", 0)}
            for i, r in enumerate(rubrics)
        ],
        "failed": failed,
    }


def _one_line(text: Any, limit: int = 300) -> str:
    text = " ".join(str(text or "").split())
    text = text.replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def render_markdown(report: Dict[str, Any], source: str) -> str:
    lines = [
        "# CodeWikiBench report",
        "",
        f"- Results: `{source}`",
        f"- Overall score: **{report['overall_score']:.4f}**",
        f"- Leaves: {report['num_leaves']}  |  failed (score <= {report['max_score']}): "
        f"{report['num_failed']}  |  evaluation errors: {report['num_error_leaves']}",
        "",
        "## Top-level",
        "",
        "| Path | Weight | Score | Requirement |",
        "|---|---|---|---|",
    ]
    for t in report["top_level"]:
        lines.append(f"| {t['path']} | {t['weight']} | {t['score']:.3f} | {_one_line(t['requirements'], 160)} |")
    lines += ["", "## Failed leaves", ""]
    if not report["failed"]:
        lines.append("None.")
    else:
        lines += ["| Path | Weight | Score | Requirement | Reasoning |", "|---|---|---|---|---|"]
        for f in report["failed"]:
            tag = " (error)" if f["error"] else ""
            lines.append(f"| {f['path']} | {f['weight']} | {f['score']:.3f}{tag} | "
                         f"{_one_line(f['requirements'], 200)} | {_one_line(f['reasoning'])} |")
    return "\n".join(lines) + "\n"


def render_summary(report: Dict[str, Any]) -> str:
    lines = [
        f"Overall score: {report['overall_score']:.4f}",
        f"Leaves: {report['num_leaves']}   failed (<= {report['max_score']}): {report['num_failed']}   "
        f"errors: {report['num_error_leaves']}",
        "Top-level:",
    ]
    for t in report["top_level"]:
        lines.append(f"  [{t['path']}] {t['score']:.3f} (w{t['weight']}) {_one_line(t['requirements'], 90)}")
    return "\n".join(lines)


def cmd_report(args) -> int:
    path = Path(args.results)
    if not path.is_file():
        die(f"results file not found: {path}")
    report = build_report(load_json(path), args.max_score)
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        print(render_markdown(report, str(path)), end="")
    else:
        print(render_summary(report))
    return 0


# --------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------

MODEL_HELP = ("Model to use; repeat for several models. API models go through the OpenAI-compatible "
              "endpoint in BASE_URL/API_KEY; 'caw:<claude_code|codex>:<model>' runs a CLI coding agent "
              "(needs the [caw] extra).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codewikibench",
        description="Evaluate repository documentation against hierarchical rubrics.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("parse", help="Parse a CodeWiki/DeepWiki markdown docs dir into docs_tree.json + structured_docs.json")
    p.add_argument("--docs-dir", required=True, help="Generated docs dir (.md files, optional module_tree.json)")
    p.add_argument("--out", required=True, help="Output dir for docs_tree.json and structured_docs.json")
    p.add_argument("--project-name", help="Root page name (default: docs dir name, or its parent if named 'docs')")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("rubrics", help="Generate rubrics from parsed docs (one set per model) and combine them")
    p.add_argument("--docs", required=True, help="Parsed docs dir (docs_tree.json + structured_docs.json)")
    p.add_argument("--out", required=True, help="Combined rubrics JSON; per-model sets are written next to it")
    p.add_argument("--model", required=True, action="append", help=MODEL_HELP)
    p.add_argument("--combine-model", help="Model used to merge multiple rubric sets (default: first --model)")
    p.add_argument("--use-tools", action="store_true", help="Let the model navigate docs content with the docs_navigator tool")
    la = p.add_mutually_exclusive_group()
    la.add_argument("--language-agnostic", dest="language_agnostic", action="store_true", default=True,
                    help="Rubrics describe features/behaviour, not language constructs (default: on)")
    la.add_argument("--no-language-agnostic", dest="language_agnostic", action="store_false",
                    help="Use the original (language-specific allowed) rubric prompt")
    p.add_argument("--temperature", type=float, default=0.1, help="Recorded in metadata for the combine step (default: 0.1)")
    p.add_argument("--max-retries", type=int, default=3, help="Retries for the combine call (default: 3)")
    p.add_argument("--force", action="store_true", help="Regenerate even if outputs exist")
    p.set_defaults(func=cmd_rubrics)

    p = sub.add_parser("judge", help="Judge parsed docs against rubrics with one or more models and combine the scores")
    p.add_argument("--rubrics", required=True, help="Rubrics JSON ({'rubrics': [...]} or a bare list)")
    p.add_argument("--docs", required=True, help="Parsed docs dir to evaluate")
    p.add_argument("--out", required=True, help="Combined results JSON; per-model results go to <out_stem>.<model>.json")
    p.add_argument("--model", required=True, action="append", help=MODEL_HELP)
    p.add_argument("--batch-size", type=int, default=4, help="Leaves judged concurrently (default: 4)")
    p.add_argument("--use-tools", action="store_true", help="Give the judge grep_docs/read_section tools")
    p.add_argument("--enable-retry", action="store_true", help="Re-judge leaves that errored or fell back to text parsing")
    p.add_argument("--max-retries", type=int, default=2, help="Retries per errored leaf (default: 2)")
    p.add_argument("--method", choices=["average", "majority_vote", "weighted_average", "max", "min"],
                   default="average", help="How to combine per-model leaf scores (default: average)")
    p.add_argument("--weights", help="Comma-separated per-model weights for --method weighted_average")
    p.add_argument("--force", action="store_true", help="Re-judge even if outputs exist")
    p.set_defaults(func=cmd_judge)

    p = sub.add_parser("report", help="List failed leaves from a results JSON")
    p.add_argument("--results", required=True, help="Results JSON written by `codewikibench judge`")
    p.add_argument("--format", choices=["json", "markdown", "summary"], default="summary", help="Output format (default: summary)")
    p.add_argument("--max-score", type=float, default=0.99, help="Leaves with score <= this are reported as failed (default: 0.99)")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
