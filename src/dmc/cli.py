"""Command-line entry points with explicit collection and publishing controls."""

import argparse
import json
import logging
import os
import re
from dataclasses import asdict
from pathlib import Path

from dmc.client import Client
from dmc.pipeline import run_pipeline
from dmc.publishing import publish_dataset
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
    scrape.add_argument("--publish", action="store_true")
    publish = commands.add_parser("publish", help="Publish an existing local dataset")
    publish.add_argument("dataset", choices=SOURCES)
    publish.add_argument("--data-dir", type=Path, default=Path("data"))
    for command in (scrape, publish):
        command.add_argument("--hf-namespace", default=os.environ.get("HUGGING_FACE_USERNAME"))
    readme = commands.add_parser("readme", help="Update the dataset statistics in README")
    readme.add_argument("--data-dir", type=Path, default=Path("data"))
    readme.add_argument("--output", type=Path, default=Path("README.md"))
    readme.add_argument("--repository", help="Read summaries from owner/repository data branches")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.environ.get("HUGGING_FACE_TOKEN") or os.environ.get("HF_TOKEN")
    should_publish = args.command == "publish" or getattr(args, "publish", False)
    if should_publish and (not args.hf_namespace or not token):
        parser.error("Publishing requires --hf-namespace and HUGGING_FACE_TOKEN (or HF_TOKEN)")
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
            if result.errors:
                return 1
        if should_publish:
            repos = publish_dataset(args.data_dir / args.dataset, args.hf_namespace, token)
            print(json.dumps({"published": repos}))
        if args.command == "readme":
            if args.repository:
                if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repository):
                    raise ValueError("Repository must be owner/name")
                with Client() as client:
                    summaries = [
                        client.get_json(
                            f"https://raw.githubusercontent.com/{args.repository}/"
                            f"refs/heads/data_{label}/data/{label}/summary.json"
                        )
                        for label in SOURCES
                    ]
            else:
                summaries = load_local_summaries(args.data_dir)
            build_global_readme(args.output, summaries)
    except Exception as exc:
        logging.error("%s", exc)
        return 1
    return 0
