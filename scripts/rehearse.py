#!/usr/bin/env python3
"""Operator-run rehearsal helpers. Remote writes require an explicit --apply."""

import argparse
import base64
import datetime
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import uuid

REPO = "Steve-Glass/pr-note-consumer"
PRODUCER = "Steve-Glass/pr-note"
SAMPLE_BRANCH = "demo/sample-pr"
SAMPLE_PATH = "demo/sample.txt"
SAMPLE_CONTENT = "Harmless PR note recording fixture. No executable code.\n"
ROOT = Path(__file__).resolve().parents[1]


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def api(path, method="GET", data=None):
    args = ["gh", "api", "--method", method, path]
    if data is not None:
        args += ["--input", "-"]
    result = subprocess.run(
        args, cwd=ROOT, text=True, input=json.dumps(data) if data is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{method} {path}: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def optional_api(path):
    try:
        return api(path)
    except RuntimeError as error:
        if "(HTTP 404)" not in str(error):
            raise
        print(f"Not available: {error}", file=sys.stderr)
        return None


def encoded(value):
    return urllib.parse.quote(str(value), safe="")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def identity():
    origin = command("git", "remote", "get-url", "origin")
    if origin not in (f"https://github.com/{REPO}.git", f"https://github.com/{REPO}",
                      f"git@github.com:{REPO}.git"):
        raise RuntimeError(f"Unexpected origin: {origin}; refusing to target {REPO}.")
    repo = api(f"repos/{REPO}")
    actor = api("user")
    if actor["login"] != "Steve-Glass" or actor["type"] != "User":
        raise RuntimeError("Use the approved Steve-Glass human account for rehearsal.")
    return repo, actor["login"]


def contents(path, ref):
    return optional_api(f"repos/{REPO}/contents/{path}?ref={encoded(ref)}")


def active_workflow(name, branch):
    commit = api(f"repos/{REPO}/commits/{encoded(branch)}")["sha"]
    if contents(f".github/workflows/{name}", commit) is None:
        raise RuntimeError(f"{name} is not published at {branch} ({commit}).")
    workflow = api(f"repos/{REPO}/actions/workflows/{name}")
    if workflow["state"] != "active":
        raise RuntimeError(f"{name} is not active: {workflow['state']}.")
    return commit


def write_preview(method, path, data, apply):
    if not apply:
        return {"method": method, "path": path, "body": data}
    return api(path, method, data)


def preflight(_args):
    repo, actor = identity()
    refs = {}
    for ref in ("v3", "v3.0.0", "v3.0.1"):
        tag = optional_api(f"repos/{PRODUCER}/git/ref/tags/{ref}")
        value = api(f"repos/{PRODUCER}/commits/{ref}") if tag else None
        refs[ref] = value["sha"] if value else None
    return {
        "repo": repo["full_name"], "actor": actor, "default_branch": repo["default_branch"],
        "permissions": repo["permissions"],
        "actions": api(f"repos/{REPO}/actions/permissions"),
        "workflow_permissions": api(f"repos/{REPO}/actions/permissions/workflow"),
        "rulesets": api(f"repos/{REPO}/rulesets?includes_parents=true"),
        "producer_refs": refs,
        "lockfile_present": (ROOT / ".github/workflows/actions.lock").is_file(),
        "extension": command("gh", "extension", "list"),
        "runtime": "NOT VERIFIED: requires approved native runner executions and evidence",
    }


def sample_pr(args):
    repo, _ = identity()
    base = repo["default_branch"]
    pulls = api(
        f"repos/{REPO}/pulls?state=all&head=Steve-Glass:{encoded(SAMPLE_BRANCH)}"
        f"&base={encoded(base)}&per_page=100"
    )
    open_pulls = [pr for pr in pulls if pr["state"] == "open"]
    if len(open_pulls) > 1:
        raise RuntimeError("Multiple sample PRs found; resolve ambiguity manually.")
    if open_pulls:
        return {"reused": True, "pr": open_pulls[0]["html_url"]}
    if pulls:
        raise RuntimeError("The sample PR was closed. Reopen it with approval; do not duplicate it.")

    base_sha = api(f"repos/{REPO}/commits/{encoded(base)}")["sha"]
    branch = optional_api(f"repos/{REPO}/git/ref/heads/{SAMPLE_BRANCH}")
    existing = contents(SAMPLE_PATH, SAMPLE_BRANCH) if branch else None
    if existing and base64.b64decode(existing["content"]).decode() != SAMPLE_CONTENT:
        raise RuntimeError("The existing sample fixture differs; refusing to overwrite it.")
    if branch:
        comparison = api(f"repos/{REPO}/compare/{encoded(base)}...{encoded(SAMPLE_BRANCH)}")
        if any(file["filename"] != SAMPLE_PATH for file in comparison.get("files", [])):
            raise RuntimeError("The sample branch has unrelated changes; refusing to reuse it.")
    steps = []
    if not branch:
        steps.append(write_preview("POST", f"repos/{REPO}/git/refs", {
            "ref": f"refs/heads/{SAMPLE_BRANCH}", "sha": base_sha,
        }, args.apply))
    if not existing:
        steps.append(write_preview("PUT", f"repos/{REPO}/contents/{SAMPLE_PATH}", {
            "message": "Add harmless recording fixture\n\n"
                       "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>",
            "branch": SAMPLE_BRANCH,
            "content": base64.b64encode(SAMPLE_CONTENT.encode()).decode(),
        }, args.apply))
    pr_command = [
        "gh", "pr", "create", "--repo", REPO, "--base", base, "--head", SAMPLE_BRANCH,
        "--title", "Demo: harmless PR note fixture",
        "--body", "Recording fixture only. A human comment triggers the PR note Action. "
                  "No PR code is checked out or executed.",
    ]
    steps.append(command(*pr_command) if args.apply else {"command": pr_command})
    return {"applied": args.apply, "base_sha": base_sha, "steps": steps}


def trigger(args):
    repo, actor = identity()
    branch = repo["default_branch"]
    sha = active_workflow("issuecomment.yml", branch)
    pr = api(f"repos/{REPO}/pulls/{args.pr}")
    if (pr["state"] != "open" or pr["base"]["ref"] != branch
            or pr["head"]["ref"] != SAMPLE_BRANCH
            or pr["head"]["repo"]["full_name"] != REPO):
        raise RuntimeError("Trigger target must be the open, same-repository sample PR.")
    receipt = {
        "applied": args.apply, "repo": REPO, "actor": actor, "event": "issue_comment",
        "workflow": "issuecomment.yml", "branch": branch, "sha": sha, "since": now(),
        "pr": args.pr,
    }
    result = write_preview("POST", f"repos/{REPO}/issues/{args.pr}/comments", {
        "body": f"Demo checkpoint {uuid.uuid4()}: please post the demo note.",
    }, args.apply)
    if args.apply:
        receipt.update(comment_url=result["html_url"], comment_id=result["id"],
                       title=f"PR note | comment {result['id']}")
    else:
        receipt["preview"] = result
    return receipt


def dispatch(args):
    repo, actor = identity()
    ref = api(f"repos/{REPO}/git/ref/heads/{args.ref}")
    if ref["ref"] != f"refs/heads/{args.ref}":
        raise RuntimeError("Dispatch requires the exact named branch, not a tag or SHA.")
    # A manually dispatched workflow must also exist on the default branch.
    active_workflow("firewall-demo.yml", repo["default_branch"])
    sha = active_workflow("firewall-demo.yml", args.ref)
    if contents(".github/egress-firewall.yaml", sha) is None:
        raise RuntimeError("No committed firewall policy on the selected workflow ref.")
    receipt = {
        "applied": args.apply, "repo": REPO, "actor": actor, "event": "workflow_dispatch",
        "workflow": "firewall-demo.yml", "branch": args.ref, "sha": sha, "since": now(),
    }
    receipt["request"] = write_preview(
        "POST", f"repos/{REPO}/actions/workflows/firewall-demo.yml/dispatches",
        {"ref": args.ref}, args.apply,
    )
    return receipt


def matched_runs(receipt, runs):
    return [
        run for run in runs
        if run["event"] == receipt["event"]
        and ("title" not in receipt or run["display_title"] == receipt["title"])
        and run["head_sha"] == receipt["sha"]
        and run["head_branch"] == receipt["branch"]
        and run["actor"]["login"] == receipt["actor"]
        and datetime.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        >= datetime.datetime.fromisoformat(receipt["since"])
    ]


def evidence(args):
    receipt = json.loads(Path(args.receipt).read_text())
    if receipt.get("applied") is not True or receipt.get("repo") != REPO:
        raise RuntimeError("An applied receipt from this repository is required.")
    if "title" not in receipt and args.run_id is None:
        raise RuntimeError(
            "This input-free dispatch has no unique run title. Select its run in Actions "
            "and pass --run-id; the receipt's event, ref, SHA, actor and time must still match."
        )
    identity()
    endpoint = (
        f"repos/{REPO}/actions/workflows/{receipt['workflow']}/runs"
        f"?event={receipt['event']}&created={encoded('>=' + receipt['since'])}&per_page=100"
    )
    pages = json.loads(command("gh", "api", "--paginate", "--slurp", endpoint))
    candidates = [run for page in pages for run in page["workflow_runs"]]
    if args.run_id is not None:
        candidates = [run for run in candidates if run["id"] == args.run_id]
    matches = matched_runs(receipt, candidates)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one matching run for this receipt and selected ID; found {len(matches)}. "
            "If delivery is pending, retry this read-only command. Check ref movement, "
            "Actions event policy, receipt, and runs; never choose the latest unrelated run."
        )
    run = matches[0]
    if run["run_attempt"] != 1:
        raise RuntimeError("This run was rerun. Post a NEW trigger and retain its new receipt.")
    if run["status"] != "completed":
        raise RuntimeError(f"Run is {run['status']}, not completed: {run['html_url']}")
    logs = command("gh", "run", "view", str(run["id"]), "--repo", REPO, "--attempt", "1", "--log")
    artifact_pages = json.loads(command(
        "gh", "api", "--paginate", "--slurp",
        f"repos/{REPO}/actions/runs/{run['id']}/artifacts?per_page=100",
    ))
    artifacts = [artifact for page in artifact_pages for artifact in page["artifacts"]]
    out = Path(args.out) / str(run["id"])
    out.mkdir(parents=True, exist_ok=False)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    (out / "artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    (out / "run.log").write_text(logs + "\n")
    snapshots = {}
    for path in (f".github/workflows/{receipt['workflow']}",
                 ".github/workflows/actions.lock", ".github/egress-firewall.yaml"):
        content = contents(path, run["head_sha"])
        snapshots[path] = content["sha"] if content else None
        if content:
            (out / Path(path).name).write_bytes(base64.b64decode(content["content"]))
    (out / "snapshot-blobs.json").write_text(json.dumps(snapshots, indent=2) + "\n")
    observations = [
        line for line in logs.splitlines()
        if "pr-note@" in line or "demo-revision" in line or "PR_NOTE_DEMO_REVISION" in line
        or "demo revision" in line.lower()
    ]
    return {
        "run": run["html_url"], "id": run["id"], "attempt": run["run_attempt"],
        "conclusion": run["conclusion"], "sha": run["head_sha"], "evidence_dir": str(out),
        "identity_log_candidates": observations,
        "artifacts": [{"id": a["id"], "name": a["name"], "expired": a["expired"],
                       "archive_download_url": a["archive_download_url"]} for a in artifacts],
        "verdict": "NOT INFERRED. Review actual Action resolution/output or matching firewall "
                   "deny event. A failed run, an absent artifact, or expected text is not proof.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight").set_defaults(handler=preflight)
    sample = commands.add_parser("sample-pr")
    sample.add_argument("--apply", action="store_true", help="Approved remote writes")
    sample.set_defaults(handler=sample_pr)
    comment = commands.add_parser("trigger")
    comment.add_argument("--pr", type=int, required=True)
    comment.add_argument("--apply", action="store_true", help="Approved remote write")
    comment.set_defaults(handler=trigger)
    probe = commands.add_parser("dispatch")
    probe.add_argument("--ref", required=True, help="Explicit branch name, not a tag or SHA")
    probe.add_argument("--apply", action="store_true", help="Approved remote write")
    probe.set_defaults(handler=dispatch)
    collect = commands.add_parser("evidence")
    collect.add_argument("--receipt", required=True)
    collect.add_argument("--run-id", type=int, help="Required for input-free firewall dispatches")
    collect.add_argument("--out", default=".demo-evidence")
    collect.set_defaults(handler=evidence)
    args = parser.parse_args()
    try:
        print(json.dumps(args.handler(args), indent=2))
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
