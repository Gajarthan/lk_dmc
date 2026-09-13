"""Command-line entry points with explicit collection and publishing controls."""

import argparse
import json
import logging
import os
import re
from dataclasses import asdict
from pathlib import Path

from dmc.analysis import analyze_dataset
from dmc.client import Client
from dmc.opencode import OpenCodeClient, OpenCodeConfig
from dmc.pipeline import run_pipeline
from dmc.publishing import export_dataset
from dmc.sources import SOURCES
from dmc.summaries import build_global_readme, load_local_summaries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect and publish DMC report datasets")
    commands = parser.add_subparsers(dest="command", required=True)
    scrape = commands.add_parser("scrape", help="Collect metadata and process PDFs")
    scrape.add_argument("dataset", choices=SOURCES)
    scrape.add_argument("max_dt", nargs="?", type=float, help="Legacy per-stage time budget")
    scrape.add_argument("--data-dir", type=Path, default=Path("data"))
    scrape.add_argument("--max-pages", type=int, default=10000)
    scrape.add_argument("--max-seconds", type=float, default=300)
    scrape.add_argument("--max-documents", type=int)
    scrape.add_argument("--metadata-only", action="store_true")
    scrape.add_argument(
        "--analyze", action="store_true", help="Analyze extracted text with OpenCode"
    )
    analyze = commands.add_parser("analyze", help="Analyze existing report text with OpenCode")
    analyze.add_argument("dataset", choices=SOURCES)
    analyze.add_argument("--data-dir", type=Path, default=Path("data"))
    analyze.add_argument(
        "--force", action="store_true", help="Reanalyze matching completed reports"
    )
    for command, prefix in ((scrape, "analysis-"), (analyze, "")):
        command.add_argument("--export", action="store_true", help="Prepare JSONL for publication")
        command.add_argument(
            f"--{prefix}max-documents", dest="analysis_max_documents", type=int, default=10
        )
        command.add_argument(
            f"--{prefix}max-seconds", dest="analysis_max_seconds", type=float, default=300
        )
        command.add_argument(
            f"--{prefix}max-characters", dest="analysis_max_characters", type=int, default=40000
        )
    export = commands.add_parser("export", help="Prepare local JSONL files for GitHub publication")
    export.add_argument("dataset", choices=SOURCES)
    export.add_argument("--data-dir", type=Path, default=Path("data"))
    commands.add_parser("opencode-health", help="Check the configured OpenCode service")
    readme = commands.add_parser("readme", help="Update the dataset statistics in README")
    readme.add_argument("--data-dir", type=Path, default=Path("data"))
    readme.add_argument("--output", type=Path, default=Path("README.md"))
    readme.add_argument("--repository", help="Read summaries from owner/repository data branches")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    should_analyze = args.command == "analyze" or getattr(args, "analyze", False)
    should_export = args.command == "export" or getattr(args, "export", False)
    config = None
    if should_analyze or args.command == "opencode-health":
        try:
            config = OpenCodeConfig.from_env()
        except ValueError as exc:
            parser.error(str(exc))
    failed = False
    try:
        if args.command == "scrape":
            result = run_pipeline(
                SOURCES[args.dataset],
                args.data_dir,
                max_pages=args.max_pages,
                max_seconds=args.max_dt if args.max_dt is not None else args.max_seconds,
                max_documents=args.max_documents,
                metadata_only=args.metadata_only,
            )
            print(json.dumps(asdict(result), indent=2))
            failed = bool(result.errors)
        if should_analyze and not failed:
            with OpenCodeClient(config) as client:
                analysis = analyze_dataset(
                    args.data_dir / args.dataset,
                    client=client,
                    max_documents=args.analysis_max_documents,
                    max_seconds=args.analysis_max_seconds,
                    max_characters=args.analysis_max_characters,
                    force=getattr(args, "force", False),
                )
            print(json.dumps({"analysis": asdict(analysis)}, indent=2))
            failed = bool(analysis.errors)
        if should_export:
            paths = export_dataset(args.data_dir / args.dataset)
            print(json.dumps({"exported": [str(path) for path in paths]}))
        if args.command == "opencode-health":
            with OpenCodeClient(config) as client:
                print(json.dumps(client.health()))
        if args.command == "readme":
            if args.repository:
                if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
                    raise ValueError("Repository must be owner/name")
                with Client() as client:
                    client.session.headers["Accept"] = "application/vnd.github.raw+json"
                    github_token = os.environ.get("GITHUB_TOKEN")
                    if github_token:
                        client.session.headers["Authorization"] = f"Bearer {github_token}"
                    summaries = [
                        client.get_json(
                            f"https://api.github.com/repos/{args.repository}/contents/"
                            f"data/{label}/summary.json?ref=data_{label}"
                        )
                        for label in SOURCES
                    ]
            else:
                summaries = load_local_summaries(args.data_dir)
            build_global_readme(args.output, summaries)
    except Exception as exc:
        logging.error("%s", exc)
        return 1
    return 1 if failed else 0
