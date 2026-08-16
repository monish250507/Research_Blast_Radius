"""rbr CLI.

Commands:
  rbr init       --repo <path>                 register a project
  rbr ingest     --project <id> --repo <path> --from <sha> --to <sha> [--claims <yaml>]
  rbr analyze    --project <id> --change <id> [--claims <yaml>]
  rbr report     --project <id> --assessment <id> [--format json|markdown]
  rbr status     --project <id> [--change <id>]
"""

from __future__ import annotations

import argparse
import json
import sys

from ..claims import ClaimLoader
from ..config import settings
from ..evidence import GitParentError, IngestionPipeline, persist
from ..logging import get_logger
from ..orchestrator import AnalyzeError, AnalyzeService
from ..reports import render_markdown
from ..schemas import ids
from ..store import open_repository
from ..store.repository import Repository

log = get_logger("rbr.cli")


def _repo() -> Repository:
    return open_repository(settings.db_url)


def cmd_init(args: argparse.Namespace) -> int:
    repo = _repo()
    pid = ids.project_id()
    repo.create_project(pid, owner=args.owner or "", repository=args.repo, scope="python+git+jupyter")
    print(pid)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    repo = _repo()
    pipeline = IngestionPipeline(args.repo)
    try:
        result = pipeline.ingest_commit_range(args.project, args.from_sha, args.to_sha)
    except GitParentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.claims:
        claims = ClaimLoader(args.project).load_yaml(args.claims)
        from ..claims import ClaimIndex

        ClaimIndex(repo, args.project).ingest_claims(claims)
        print(f"ingested {len(claims)} claims from {args.claims}", file=sys.stderr)
    persist(repo, result)
    print(result.change.change_id)
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    repo = _repo()
    service = AnalyzeService(repo, settings)
    claims = None
    if args.claims:
        claims = ClaimLoader(args.project).load_yaml(args.claims)
    try:
        result = service.run(args.project, args.change, claims=claims)
    except AnalyzeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    assessment = result["assessment"]
    print(f"assessment_id: {assessment.assessment_id}")
    print(f"status: {assessment.status.value}")
    print(f"conclusions: {len(assessment.conclusions)}")
    print(f"unknowns: {len(assessment.unknowns)}")
    print(f"validation actions: {len(assessment.validation_actions)}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    repo = _repo()
    assessment = repo.get_assessment(args.assessment)
    if assessment is None:
        print(f"error: assessment not found: {args.assessment}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(assessment.model_dump(mode="json"), indent=2, default=str))
    else:
        print(render_markdown(repo, assessment))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = _repo()
    project = repo.get_project(args.project)
    if project is None:
        print(f"error: project not found: {args.project}", file=sys.stderr)
        return 1
    nodes = repo.list_nodes(args.project)
    edges = repo.list_edges(args.project)
    evidence = repo.list_evidence(args.project)
    print(f"project: {args.project}")
    print(f"nodes: {len(nodes)}  edges: {len(edges)}  evidence: {len(evidence)}")
    if args.change:
        coverage = repo.get_coverage(args.project, args.change)
        if coverage:
            for layer, cov in coverage.layers.items():
                print(f"  {layer.value}: parsed {cov.parsed}/{cov.scanned} "
                      f"failed {cov.failed} unknown {cov.unknown}")
        else:
            print("  (no coverage for change)")
    gaps = [n.ref for n in nodes if n.node_type.value == "UNKNOWN_STATE"]
    if gaps:
        print(f"unknown-state nodes: {len(gaps)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rbr",
                                     description="Research Blast Radius")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="register a repository as a project")
    p_init.add_argument("--repo", required=True)
    p_init.add_argument("--owner", default="")
    p_init.set_defaults(func=cmd_init)

    p_ingest = sub.add_parser("ingest", help="fingerprint + parse a change deterministically")
    p_ingest.add_argument("--project", required=True)
    p_ingest.add_argument("--repo", required=True)
    p_ingest.add_argument("--from", dest="from_sha", required=True)
    p_ingest.add_argument("--to", dest="to_sha", required=True)
    p_ingest.add_argument("--claims", default=None)
    p_ingest.set_defaults(func=cmd_ingest)

    p_analyze = sub.add_parser("analyze", help="run agents + arbiter for a change")
    p_analyze.add_argument("--project", required=True)
    p_analyze.add_argument("--change", required=True)
    p_analyze.add_argument("--claims", default=None)
    p_analyze.set_defaults(func=cmd_analyze)

    p_report = sub.add_parser("report", help="render an impact report")
    p_report.add_argument("--project", required=True)
    p_report.add_argument("--assessment", required=True)
    p_report.add_argument("--format", dest="format", choices=["json", "markdown"], default="markdown")
    p_report.set_defaults(func=cmd_report)

    p_status = sub.add_parser("status", help="show project/change status")
    p_status.add_argument("--project", required=True)
    p_status.add_argument("--change", default=None)
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    raise SystemExit(main())
