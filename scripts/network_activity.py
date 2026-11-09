#!/usr/bin/env python3
"""Bounded native-firewall evidence collection; no third-party dependencies."""

import base64
import collections
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile


REPO = "Steve-Glass/pr-note-consumer"
WORKFLOW = ".github/workflows/issuecomment.yml"
BRANCH = "network-activity-data"
STATE_PATH = "state.json"
TITLE = "Repository network activity"
MARKER = "<!-- network-activity-dashboard:v1 -->"
MAX_BYTES = 1_000_000
MAX_RECORDS = 100
MAX_GENERATIONS = 256
MAX_GROUPS = 120
SHA = re.compile(r"[0-9a-f]{40}")
DOMAIN = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
REASONS = {"Allowed", "NotInAllowList", "ExplicitlyBlocked", "Other"}
STATUSES = {"observed", "partial", "missing", "expired", "invalid"}
CONFIG = Path(__file__).resolve().parents[1] / ".github/network-activity.json"


class EvidenceError(ValueError):
    """Untrusted evidence is invalid or exceeds a documented limit."""


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def positive(value):
    return type(value) is int and value > 0


def timestamp(value):
    require(isinstance(value, str) and len(value) <= 40, "Invalid timestamp")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)",
                         value) is not None, "Invalid timestamp encoding")
    # Native firewall timestamps use nanoseconds; Python 3.9 accepts microseconds.
    normalized = re.sub(r"(\.\d{6})\d+", r"\1", value)
    parsed = dt.datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "Timestamp needs timezone")
    return parsed


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def load_json(data, limit=MAX_BYTES):
    require(len(data) <= limit, "JSON byte limit exceeded")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique)
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("Malformed JSON") from exc


def config():
    value = load_json(CONFIG.read_bytes())
    require(set(value) == {"issue_number", "public_domains"}, "Unexpected configuration")
    require(type(value["issue_number"]) is int and value["issue_number"] >= 0, "Invalid issue")
    require(isinstance(value["public_domains"], list) and len(value["public_domains"]) <= 50,
            "Invalid domain disclosure policy")
    require(all(isinstance(d, str) and DOMAIN.fullmatch(d) for d in value["public_domains"]),
            "Invalid public domain")
    return value


class ArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        host = parsed.hostname or ""
        require(parsed.scheme == "https" and parsed.port in (None, 443) and
                not parsed.username and not parsed.password and
                (host.endswith(".blob.core.windows.net") or
                 host.endswith(".githubusercontent.com")),
                "Unexpected artifact redirect")
        # Never forward the Actions token to signed artifact storage URLs.
        return urllib.request.Request(newurl, headers={"User-Agent": "network-activity"})


class API:
    def __init__(self):
        require(os.environ.get("GITHUB_REPOSITORY") == REPO, "Unexpected repository")
        self.token = os.environ["GH_TOKEN"]

    def request(self, path, method="GET", data=None, binary=False):
        require(path.startswith("/") and not path.startswith("//") and ".." not in path and
                "#" not in path, "Invalid API path")
        url = f"https://api.github.com/repos/{REPO}{path}"
        headers = {"Authorization": f"Bearer {self.token}", "User-Agent": "network-activity",
                   "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        body = None if data is None else encode(data)
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        opener = urllib.request.build_opener(ArtifactRedirect())
        with opener.open(request, timeout=30) as response:
            raw = response.read((2_000_000 if binary else 4_000_000) + 1)
        require(len(raw) <= (2_000_000 if binary else 4_000_000), "API response limit exceeded")
        return raw if binary else load_json(raw, 4_000_000)


def disclosed_domain(value, public_domains):
    require(isinstance(value, str), "Domain is not text")
    domain = value.lower().rstrip(".")
    require(DOMAIN.fullmatch(domain) is not None, "Unsupported domain encoding")
    if domain in public_domains:
        return domain
    return "redacted-" + hashlib.sha256(domain.encode()).hexdigest()[:16] + ".invalid"


def parse_artifact(raw, run_id, job_id, public_domains):
    require(len(raw) <= 2_000_000, "Compressed artifact exceeds limit")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            require(len(members) == 1, "Expected one JSON member")
            member = members[0]
            require(re.fullmatch(r"firewall-decisions-[A-Za-z0-9_-]+\.json", member.filename)
                    is not None and member.file_size <= 8_000_000 and
                    (member.external_attr >> 16) & 0o170000 != 0o120000,
                    "Unsafe archive member")
            data = load_json(archive.read(member), 8_000_000)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise EvidenceError("Invalid archive") from exc
    require(isinstance(data, dict) and set(data) == {"meta", "decision"}, "Unknown native schema")
    require(isinstance(data["meta"], dict) and
            data["meta"].get("url") ==
            f"https://github.com/{REPO}/actions/runs/{run_id}/job/{job_id}",
            "Artifact job/run mismatch")
    events = data["decision"]
    require(isinstance(events, list) and len(events) <= 20000, "Decision row limit exceeded")
    groups = collections.Counter()
    ignored = 0
    for event in events:
        require(isinstance(event, dict), "Invalid decision row")
        if event.get("msg") == "HTTP RESPONSE":
            ignored += 1
            continue
        layer = event.get("blockedAt")
        blocked = event.get("blocked")
        require(layer in {"dns", "http"} and type(blocked) is bool and
                event.get("msg") == f"{layer.upper()} {'BLOCKED' if blocked else 'ALLOWED'}",
                "Unsupported decision row")
        timestamp(event.get("time"))
        domain = disclosed_domain(event.get("domains"), public_domains)
        reason = event.get("because")
        require(isinstance(reason, str) and len(reason) <= 200, "Invalid decision reason")
        reason = reason if reason in REASONS else "Other"
        groups[(job_id, domain, layer, blocked, reason)] += 1
    require(len(groups) <= MAX_GROUPS, "Decision group limit exceeded")
    return [dict(job_id=j, domain=d, layer=l, blocked=b, reason=r, count=c)
            for (j, d, l, b, r), c in sorted(groups.items())], ignored


def validate_record(record):
    require(isinstance(record, dict) and set(record) == {
        "run_id", "attempt", "workflow", "branch", "revision", "started_at", "completed_at",
        "collected_at", "status", "jobs", "covered_jobs", "artifact_ids", "groups",
        "ignored_responses", "diagnostics"}, "Invalid record schema")
    require(positive(record["run_id"]) and positive(record["attempt"]), "Invalid run identity")
    require(record["workflow"] == WORKFLOW and SHA.fullmatch(record["revision"]) is not None,
            "Invalid source workflow/revision")
    require(isinstance(record["branch"], str) and
            re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", record["branch"]) is not None, "Invalid branch")
    for field in ("started_at", "completed_at", "collected_at"):
        timestamp(record[field])
    require(record["status"] in STATUSES, "Invalid status")
    for field in ("jobs", "covered_jobs", "artifact_ids"):
        require(isinstance(record[field], list) and len(record[field]) <= 100 and
                all(positive(i) for i in record[field]) and
                len(set(record[field])) == len(record[field]), "Invalid evidence identifiers")
    require(set(record["covered_jobs"]) <= set(record["jobs"]), "Foreign covered job")
    require(type(record["ignored_responses"]) is int and 0 <= record["ignored_responses"] <= 2_000_000,
            "Invalid response count")
    require(isinstance(record["diagnostics"], list) and len(record["diagnostics"]) <= 10 and
            all(d in {"jobs-truncated", "artifacts-truncated", "artifact-invalid",
                      "artifact-expired", "artifact-limit", "telemetry-missing"}
                for d in record["diagnostics"]), "Invalid diagnostic")
    require(isinstance(record["groups"], list) and len(record["groups"]) <= MAX_GROUPS,
            "Invalid decision groups")
    public_domains = config()["public_domains"]
    keys = set()
    for group in record["groups"]:
        require(isinstance(group, dict) and set(group) ==
                {"job_id", "domain", "layer", "blocked", "reason", "count"}, "Invalid group")
        require(group["job_id"] in record["covered_jobs"] and
                isinstance(group["domain"], str) and DOMAIN.fullmatch(group["domain"]) is not None and
                (group["domain"] in public_domains or
                 re.fullmatch(r"redacted-[0-9a-f]{16}\.invalid", group["domain"]) is not None) and
                group["layer"] in {"dns", "http"} and type(group["blocked"]) is bool and
                group["reason"] in REASONS and positive(group["count"]) and group["count"] <= 20000,
                "Invalid group values")
        key = tuple(group[k] for k in ("job_id", "domain", "layer", "blocked", "reason"))
        require(key not in keys, "Duplicate group")
        keys.add(key)
    if record["status"] == "observed":
        require(record["jobs"] and set(record["jobs"]) == set(record["covered_jobs"]) and
                not record["diagnostics"], "Observed status requires complete job coverage")
    if record["status"] in {"missing", "expired", "invalid"}:
        require(not record["groups"] and not record["covered_jobs"], "Status contradicts evidence")
    return record


def empty_state():
    return {"version": 1, "generation": 0, "updated_at": now(), "records": [],
            "discovery": {"runs_returned": 0, "total_runs": 0, "attempts_omitted": 0}}


def validate_state(state):
    require(isinstance(state, dict) and set(state) ==
            {"version", "generation", "updated_at", "records", "discovery"}, "Invalid state schema")
    require(state["version"] == 1 and type(state["generation"]) is int and
            0 <= state["generation"] <= MAX_GENERATIONS, "Invalid state version/generation")
    timestamp(state["updated_at"])
    discovery = state["discovery"]
    require(isinstance(discovery, dict) and set(discovery) ==
            {"runs_returned", "total_runs", "attempts_omitted"} and
            all(type(n) is int and 0 <= n <= 10**9 for n in discovery.values()),
            "Invalid discovery bounds")
    records = state["records"]
    require(isinstance(records, list) and len(records) <= MAX_RECORDS, "History record limit")
    seen = set()
    for record in records:
        validate_record(record)
        key = (record["run_id"], record["attempt"])
        require(key not in seen, "Duplicate run attempt")
        seen.add(key)
    require(len(encode(state)) <= MAX_BYTES, "State byte limit")
    return state


def read_state(api):
    try:
        response = api.request(f"/contents/{STATE_PATH}?ref={BRANCH}")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        # A missing state on an existing branch is corruption, not a fresh baseline.
        try:
            api.request(f"/git/ref/heads/{BRANCH}")
        except urllib.error.HTTPError as ref_exc:
            if ref_exc.code == 404:
                return empty_state(), None
            raise
        raise EvidenceError("Data branch exists without state.json") from exc
    require(response["encoding"] == "base64" and response["size"] <= MAX_BYTES,
            "Invalid stored state envelope")
    return validate_state(load_json(base64.b64decode(response["content"], validate=False))), response["sha"]


def merge_state(state, records, discovery):
    validate_state(state)
    require(state["generation"] < MAX_GENERATIONS, "Storage generation limit; operator archival required")
    combined = {(r["run_id"], r["attempt"]): r for r in state["records"]}
    for record in records:
        validate_record(record)
        key = (record["run_id"], record["attempt"])
        # Reconciliation must not downgrade previously collected complete evidence after expiry.
        if key not in combined or combined[key]["status"] != "observed":
            combined[key] = record
    state = {"version": 1, "generation": state["generation"] + 1, "updated_at": now(),
             "records": sorted(combined.values(), key=lambda r: (timestamp(r["completed_at"]), r["run_id"],
                                                               r["attempt"]))[-MAX_RECORDS:],
             "discovery": discovery}
    return validate_state(state)


def save_state(api, records, discovery):
    for attempt in range(3):
        state, blob_sha = read_state(api)
        state = merge_state(state, records, discovery)
        content = base64.b64encode(encode(state)).decode()
        try:
            if blob_sha is None:
                tree = api.request("/git/trees", "POST", {"tree": [
                    {"path": STATE_PATH, "mode": "100644", "type": "blob",
                     "content": encode(state).decode()}]})
                commit = api.request("/git/commits", "POST", {
                    "message": "Initialize bounded network activity", "tree": tree["sha"], "parents": []})
                api.request("/git/refs", "POST",
                            {"ref": f"refs/heads/{BRANCH}", "sha": commit["sha"]})
            else:
                api.request(f"/contents/{STATE_PATH}", "PUT", {
                    "message": "Update bounded network activity", "branch": BRANCH,
                    "sha": blob_sha, "content": content})
            return state
        except urllib.error.HTTPError as exc:
            if exc.code not in {409, 422} or attempt == 2:
                raise
    raise EvidenceError("Concurrent state update failed")


def collect_attempt(api, run, public_domains):
    run_id, attempt = run["id"], run["run_attempt"]
    require(positive(run_id) and positive(attempt) and run["status"] == "completed" and
            run["repository"]["full_name"] == REPO and run["path"] == WORKFLOW and
            run["head_branch"] == "main",
            "Unexpected source run")
    jobs = api.request(f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    job_ids = [j["id"] for j in jobs["jobs"]]
    artifacts = api.request(f"/actions/runs/{run_id}/artifacts?per_page=100")
    record = dict(run_id=run_id, attempt=attempt, workflow=WORKFLOW, branch=run["head_branch"],
                  revision=run["head_sha"], started_at=run["run_started_at"],
                  completed_at=run["updated_at"], collected_at=now(), status="missing",
                  jobs=job_ids, covered_jobs=[], artifact_ids=[], groups=[],
                  ignored_responses=0, diagnostics=[])
    if jobs["total_count"] > len(job_ids):
        record["diagnostics"].append("jobs-truncated")
    if artifacts["total_count"] > len(artifacts["artifacts"]):
        record["diagnostics"].append("artifacts-truncated")
    candidates = []
    for artifact in artifacts["artifacts"]:
        require(positive(artifact["id"]), "Invalid artifact identifier")
        match = re.fullmatch(r"firewall-decisions-[A-Za-z0-9_-]+-(\d+)", artifact["name"])
        if match and int(match[1]) in job_ids:
            candidates.append((artifact, int(match[1])))
    if len(candidates) > 10:
        record["diagnostics"].append("artifact-limit")
    for artifact, job_id in candidates[:10]:
        record["artifact_ids"].append(artifact["id"])
        if artifact["expired"]:
            record["diagnostics"].append("artifact-expired")
            continue
        try:
            require(artifact["size_in_bytes"] <= 2_000_000, "Artifact size limit")
            require(job_id not in record["covered_jobs"], "Duplicate artifact for job")
            raw = api.request(f"/actions/artifacts/{artifact['id']}/zip", binary=True)
            groups, ignored = parse_artifact(raw, run_id, job_id, public_domains)
            require(len(record["groups"]) + len(groups) <= MAX_GROUPS, "Run group limit")
            record["groups"].extend(groups)
            record["ignored_responses"] += ignored
            record["covered_jobs"].append(job_id)
        except (EvidenceError, urllib.error.HTTPError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {404, 410}:
                raise
            record["diagnostics"].append("artifact-invalid")
    if set(job_ids) - set(record["covered_jobs"]) or not job_ids:
        record["diagnostics"].append("telemetry-missing")
    record["diagnostics"] = sorted(set(record["diagnostics"]))
    if record["covered_jobs"]:
        record["status"] = "partial" if record["diagnostics"] else "observed"
    elif "artifact-invalid" in record["diagnostics"]:
        record["status"] = "invalid"
    elif "artifact-expired" in record["diagnostics"]:
        record["status"] = "expired"
    return validate_record(record)


def collect(api):
    public = config()["public_domains"]
    listing = api.request("/actions/workflows/issuecomment.yml/runs?status=completed&branch=main&per_page=20")
    runs = {r["id"]: r for r in listing["workflow_runs"]}
    event = load_json(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_run":
        source = event["workflow_run"]
        require(source["repository"]["full_name"] == REPO and positive(source["id"]),
                "Foreign workflow_run")
        runs[source["id"]] = source
    state, _ = read_state(api)
    complete = {(r["run_id"], r["attempt"]) for r in state["records"] if r["status"] == "observed"}
    records = []
    omitted = 0
    for run_id, run in sorted(runs.items()):
        latest = run["run_attempt"]
        require(positive(latest), "Invalid attempt count")
        omitted += max(0, latest - 3)
        for attempt in range(max(1, latest - 2), latest + 1):
            if (run_id, attempt) not in complete:
                metadata = api.request(f"/actions/runs/{run_id}/attempts/{attempt}")
                records.append(collect_attempt(api, metadata, public))
    result = save_state(api, records, {
        "runs_returned": len(listing["workflow_runs"]), "total_runs": listing["total_count"],
        "attempts_omitted": omitted})
    print(f"Persisted {len(result['records'])} retained run attempts; generation {result['generation']}.")


def facts(state):
    validate_state(state)
    records = sorted(state["records"], key=lambda r: (timestamp(r["completed_at"]),
                                                     r["run_id"], r["attempt"]))
    earliest = min((timestamp(r["started_at"]) for r in records), default=None)
    lines = [MARKER, "# Repository network activity", "",
             "## Deterministic evidence", "",
             f"Snapshot freshness: {state['updated_at']}. Retained attempts: {len(records)}/{MAX_RECORDS}.",
             f"Reporting window: {earliest.isoformat() if earliest else 'unknown'} "
             f"through {records[-1]['completed_at'] if records else 'unknown'}.",
             "Counts are native DNS/HTTP decision rows, NOT unique connections. HTTP responses "
             "are excluded. DNS retries remain separate rows; DNS and HTTP are not added as connections.",
             "Missing, expired, partial or invalid telemetry is unknown coverage, not zero traffic.",
             "Unapproved hostnames are stable pseudonyms ending in .invalid.", ""]
    statuses = collections.Counter(r["status"] for r in records)
    lines.append("Coverage: " + ", ".join(f"{s}={statuses[s]}" for s in sorted(STATUSES)) + ".")
    discovery = state["discovery"]
    lines.append(f"Latest discovery: {discovery['runs_returned']} of {discovery['total_runs']} "
                 f"completed runs returned; {discovery['attempts_omitted']} older retry attempts "
                 "outside the per-run reconciliation bound. Not a complete repository inventory.")
    counts = collections.Counter()
    first = {}
    for record in records:
        for group in record["groups"]:
            domain = group["domain"]
            first.setdefault(domain, (record["run_id"], record["attempt"]))
            counts[(domain, group["layer"], group["blocked"], group["reason"])] += group["count"]
    lines += ["", "### Destinations and decisions", "",
              "| Destination | Layer | Recorded decision | Recorded reason | Rows |",
              "| --- | --- | --- | --- | --- |"]
    for (domain, layer, blocked, reason), count in sorted(counts.items())[:150]:
        lines.append(f"| `{domain}` | {layer} | {'BLOCKED' if blocked else 'ALLOWED'} | {reason} | {count} |")
    if len(counts) > 150:
        lines.append(f"\nTable truncated: showing 150 of {len(counts)} groups.")
    lines += ["", "### Recent attempts and changes", "",
              "First observations refer only to retained history, never a lifetime baseline.", ""]
    for record in records[-10:]:
        identity = (record["run_id"], record["attempt"])
        new = sorted(d for d, key in first.items() if key == identity)
        link = f"https://github.com/{REPO}/actions/runs/{identity[0]}/attempts/{identity[1]}"
        lines.append(f"- [PR note run {identity[0]} attempt {identity[1]}]({link}): "
                     f"{record['status']}; jobs {len(record['covered_jobs'])}/{len(record['jobs'])}; "
                     f"branch `{record['branch']}`, revision `{record['revision']}`; "
                     f"first retained observations: {', '.join(new[:10]) or 'none'}.")
        layer_counts = collections.Counter()
        for group in record["groups"]:
            layer_counts[(group["layer"], group["blocked"])] += group["count"]
        lines.append("  Observed decision rows: " + "; ".join(
            f"{layer} {sum(layer_counts[(layer, b)] for b in (True, False))} "
            f"({layer_counts[(layer, True)]} blocked)" for layer in ("dns", "http")) +
            ". These are observed rows only, not estimates of missing telemetry.")
        lines.append("  Diagnostics: " + (", ".join(record["diagnostics"]) or "none") + ". "
                     "Artifacts: " + (", ".join(
                         f"[{a}](https://github.com/{REPO}/actions/runs/{identity[0]}/artifacts/{a})"
                         for a in record["artifact_ids"]) or "none") + ".")
    lines += ["", "Raw evidence remains in source-run artifacts and may expire. "
              "Job attribution is retained in state.json; no raw logs, URLs, commands, IPs, "
              "headers, or payloads are persisted.",
              f"[Validated history](https://github.com/{REPO}/blob/{BRANCH}/state.json)"]
    return "\n".join(lines)


def prepare(api):
    state, sha = read_state(api)
    require(sha is not None and state["records"], "No collected evidence")
    directory = Path("/tmp/gh-aw/network-activity")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "facts.txt").write_text(facts(state))
    (directory / "state.json").write_bytes(encode(state))


def publish(api):
    issue_number = config()["issue_number"]
    require(positive(issue_number), "Configure one approved dashboard issue before publication")
    output = load_json(Path(os.environ["GH_AW_AGENT_OUTPUT"]).read_bytes())
    items = [i for i in output["items"] if i.get("type") == "publish_dashboard"]
    require(len(items) == 1, "Expected exactly one dashboard output")
    text = items[0].get("observations")
    require(isinstance(text, str) and 1 <= len(text) <= 2000 and
            re.fullmatch(r"[A-Za-z0-9 .,;:()!?'\n-]+", text) is not None,
            "Interpretation must be bounded plain text without links, markup or mentions")
    state, sha = read_state(api)
    require(sha is not None, "Missing authoritative state")
    issue = api.request(f"/issues/{issue_number}")
    require("pull_request" not in issue and issue["state"] == "open" and
            issue["title"] == TITLE and MARKER in (issue["body"] or ""),
            "Configured issue is not the approved dashboard")
    run_id = int(os.environ["GITHUB_RUN_ID"])
    require(positive(run_id), "Invalid publisher run")
    body = (facts(state) + "\n\n## Model interpretation (not authoritative facts)\n\n" + text +
            f"\n\nGenerated by [Network activity dashboard](https://github.com/{REPO}/actions/runs/{run_id})."
            "\n<!-- gh-aw-agentic-workflow: Network activity dashboard, engine: copilot -->")
    require(len(body.encode()) <= 60000, "Dashboard body limit")
    if issue["body"] != body:
        api.request(f"/issues/{issue_number}", "PATCH", {"body": body})
    print(f"Updated configured dashboard issue {issue_number}.")


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in {"collect", "prepare", "publish"}, "Invalid command")
    {"collect": collect, "prepare": prepare, "publish": publish}[sys.argv[1]](API())


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        # Signed artifact URLs and API response bodies must not leak into public logs.
        print(f"::error::Network activity API failed (HTTP {error.code}); no successful result claimed.",
              file=sys.stderr)
        sys.exit(1)
    except (EvidenceError, KeyError, TypeError, ValueError, OSError, urllib.error.URLError):
        print("::error::Network activity validation/transport failed; inspect coverage and setup. "
              "No successful result claimed.", file=sys.stderr)
        sys.exit(1)
