"""Gold-set build commands: `python -m eval.gold_build <step>`.

The steps run in this order: freeze_search, build_pool, label_prepare, label_run, label_import,
select_sets, blind_sample, compare, escalation_import, extraction_prepare, extraction_verify,
validate. Steps that write to the data folder end with a reminder to run `make eval-sync`.
"""

import argparse
import asyncio
from collections.abc import Callable
from pathlib import Path

from eval.gold_build.blind_sample import DEFAULT_SEED as BLIND_DEFAULT_SEED
from eval.gold_build.blind_sample import blind_sample
from eval.gold_build.build_pool import (
    build_pool,
    extend_pool,
    read_link_list_from_git,
)
from eval.gold_build.compare import compare
from eval.gold_build.escalation_import import import_escalation
from eval.gold_build.extraction_prepare import prepare_extraction
from eval.gold_build.extraction_verify import import_verification, write_verification_sheet
from eval.gold_build.freeze_search import freeze_search
from eval.gold_build.label_import import import_labels
from eval.gold_build.label_prepare import prepare_labeling
from eval.gold_build.label_run import run_labeling
from eval.gold_build.select_sets import DEFAULT_SEED, select_sets, topics_below_min_includes
from eval.harness.data_dir import data_dir
from eval.harness.gold import DEFAULT_GOLD_DIR, validate
from eval.harness.topics import TOPICS_DIR

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_REMINDER = "Now back up the data folder: make eval-sync"


def _freeze_search(args: argparse.Namespace) -> int:
    path = asyncio.run(freeze_search(args.topic))
    print(f"wrote {path}")
    return 0


def _build_pool(args: argparse.Namespace) -> int:
    if args.extend:
        added = extend_pool(args.extend)
        print(f"{args.extend}: added {len(added)} papers as search_extended; label them next")
        return 0
    report = build_pool(link_md=read_link_list_from_git(REPO_ROOT))
    for topic_id, size in report.pool_sizes.items():
        print(f"{topic_id}: pool of {size} papers")
    for topic_id in report.skipped:
        print(f"{topic_id}: pool.json exists, left as it is")
    for url in report.unresolved_links:
        print(f"unresolved link, add it to link_list_manual.json: {url}")
    return 0


def _label_prepare(args: argparse.Namespace) -> int:
    print(f"wrote {prepare_labeling(data_root=data_dir())} labeling inputs")
    print(SYNC_REMINDER)
    return 0


def _label_run(args: argparse.Namespace) -> int:
    print(f"{run_labeling(args.model, data_root=data_dir())} papers labeled")
    print(SYNC_REMINDER)
    return 0


def _label_import(args: argparse.Namespace) -> int:
    print(f"imported {import_labels(data_root=data_dir())} new papers")
    return 0


def _select_sets(args: argparse.Namespace) -> int:
    if args.needs_extension:
        topics = topics_below_min_includes(DEFAULT_GOLD_DIR, TOPICS_DIR)
        print("topics below the minimum of gold includes: " + (", ".join(topics) or "none"))
        return 0
    selected = select_sets(seed=args.seed)
    for topic_id, keys in selected.items():
        print(f"{topic_id}: {len(keys)} papers in the screening set")
    return 0


def _blind_sample(args: argparse.Namespace) -> int:
    print(f"wrote {blind_sample(data_root=data_dir(), seed=args.seed)}")
    print(SYNC_REMINDER)
    return 0


def _compare(args: argparse.Namespace) -> int:
    triggers = compare(data_root=data_dir())
    for topic_id, check_id in triggers:
        print(f"escalation: {topic_id} {check_id}")
    print("sheet: escalation_sheet.csv" if triggers else "no escalation needed")
    print(SYNC_REMINDER)
    return 0


def _escalation_import(args: argparse.Namespace) -> int:
    for entry in import_escalation(data_root=data_dir()):
        not_reached = len(entry["papers_in_scope"]) - len(entry["papers_reviewed"])
        print(
            f"{entry['topic_id']} {entry['check']}: {len(entry['papers_reviewed'])} reviewed, "
            f"{len(entry['answers_changed'])} changed, {not_reached} not reached"
        )
    return 0


def _extraction_prepare(args: argparse.Namespace) -> int:
    failures = prepare_extraction(args.model, args.paper, data_root=data_dir())
    print(SYNC_REMINDER)
    if failures:
        print("quotes that are not on their page; run the step again:")
        print("\n".join(f"  {failure}" for failure in failures))
        return 1
    return 0


def _extraction_verify(args: argparse.Namespace) -> int:
    if args.import_sheet:
        print(f"wrote extraction gold for {import_verification(data_root=data_dir())} papers")
        return 0
    print(f"wrote {write_verification_sheet(data_root=data_dir())}")
    print(SYNC_REMINDER)
    return 0


def _validate(args: argparse.Namespace) -> int:
    report = validate(DEFAULT_GOLD_DIR, data_dir(), topics_dir=TOPICS_DIR)
    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")
    print("gold set is valid" if not report.errors else f"{len(report.errors)} problems")
    return 1 if report.errors else 0


def build_parser() -> argparse.ArgumentParser:
    """The command line: one subcommand per build step."""
    parser = argparse.ArgumentParser(prog="python -m eval.gold_build", description=__doc__)
    steps = parser.add_subparsers(dest="step", required=True)

    def add(name: str, handler: Callable[[argparse.Namespace], int], help_text: str):
        step = steps.add_parser(name, help=help_text)
        step.set_defaults(handler=handler)
        return step

    add("freeze_search", _freeze_search, "freeze the baseline search of one topic").add_argument(
        "--topic", required=True
    )
    add("build_pool", _build_pool, "build the candidate pools, or extend one").add_argument(
        "--extend", metavar="TOPIC", help="append the next results of the frozen query"
    )
    add("label_prepare", _label_prepare, "write the labeling inputs")
    add("label_run", _label_run, "label every paper with headless Claude").add_argument(
        "--model", required=True, help="the pinned model id, e.g. claude-opus-5-5"
    )
    add("label_import", _label_import, "import the model answers as gold")
    select = add("select_sets", _select_sets, "choose the 20-paper screening set per topic")
    select.add_argument("--seed", type=int, default=DEFAULT_SEED)
    select.add_argument("--needs-extension", action="store_true", help="only list short topics")
    add("blind_sample", _blind_sample, "write the human blind-labeling sheet").add_argument(
        "--seed", type=int, default=BLIND_DEFAULT_SEED
    )
    add("compare", _compare, "count agreement and write the escalation sheet")
    add("escalation_import", _escalation_import, "apply the escalation answers")
    prepare = add("extraction_prepare", _extraction_prepare, "freeze PDFs and pre-fill fields")
    prepare.add_argument("--model", required=True, help="the pinned model id")
    prepare.add_argument("--paper", action="append", required=True, help="a paper key; repeatable")
    verify = add("extraction_verify", _extraction_verify, "write or import the verification sheet")
    verify.add_argument("--import", dest="import_sheet", action="store_true")
    add("validate", _validate, "validate the whole gold set")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Command line entry point."""
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
