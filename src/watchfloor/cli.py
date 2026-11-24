from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from watchfloor.rbac import get_user
from watchfloor.runtime import build_app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="watchfloor",
        description="Need-to-know retrieval assistant with PII masking and durable approval gates.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="Ask a question as a fixture user")
    ask.add_argument("--user", required=True, help="Fixture user id: ops-lead, finance, or approver")
    ask.add_argument("--query", required=True)
    ask.add_argument("--json", action="store_true", dest="as_json")

    share = sub.add_parser("share", help="Request approval to share a brief with an external partner")
    share.add_argument("--user", required=True)
    share.add_argument("--summary", required=True)

    pending = sub.add_parser("pending", help="List pending approvals")
    pending.add_argument("--json", action="store_true", dest="as_json")

    approve = sub.add_parser("approve", help="Approve a pending share (approver role)")
    approve.add_argument("--user", default="approver")
    approve.add_argument("--id", required=True)
    approve.add_argument("--reason", default=None)

    deny = sub.add_parser("deny", help="Deny a pending share (approver role)")
    deny.add_argument("--user", default="approver")
    deny.add_argument("--id", required=True)
    deny.add_argument("--reason", default=None)

    audit = sub.add_parser("audit", help="Show the hash-chained audit log")
    audit.add_argument("--tail", type=int, default=20)
    audit.add_argument("--json", action="store_true", dest="as_json")
    audit.add_argument("--verify", action="store_true", help="Verify the hash chain and exit non-zero on failure")

    serve = sub.add_parser("serve", help="Run the local HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except (KeyError, PermissionError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "serve":
        import uvicorn

        uvicorn.run("watchfloor.api:app", host=args.host, port=args.port, factory=False)
        return 0

    app = build_app()
    if args.command == "ask":
        result = app.rag.ask(get_user(args.user), args.query)
        if args.as_json:
            print(result.model_dump_json(indent=2))
        else:
            print(result.answer)
            if result.citations:
                print("\nCitations:", ", ".join(result.citations))
        return 0

    if args.command == "share":
        approval = app.approvals.request_share(get_user(args.user), args.summary)
        print(approval.model_dump_json(indent=2))
        return 0

    if args.command == "pending":
        items = app.approvals.pending()
        if args.as_json:
            print(json.dumps([item.model_dump(mode="json") for item in items], indent=2))
        elif not items:
            print("No pending approvals.")
        else:
            for item in items:
                print(f"{item.id}\t{item.status}\t{item.requester_id}\t{item.summary}")
        return 0

    if args.command == "approve":
        updated = app.approvals.decide(get_user(args.user), args.id, True, args.reason)
        print(updated.model_dump_json(indent=2))
        return 0

    if args.command == "deny":
        updated = app.approvals.decide(get_user(args.user), args.id, False, args.reason)
        print(updated.model_dump_json(indent=2))
        return 0

    if args.command == "audit":
        if args.verify:
            app.audit.verify()
            print("audit chain ok")
            if not args.as_json and args.tail <= 0:
                return 0
        entries = app.audit.entries()[-args.tail :]
        if args.as_json:
            print(json.dumps([entry.model_dump(mode="json") for entry in entries], indent=2, default=str))
        else:
            for entry in entries:
                print(f"{entry.seq}\t{entry.action}\t{entry.actor}\t{entry.entry_hash[:12]}")
        return 0

    raise ValueError(f"unknown command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
