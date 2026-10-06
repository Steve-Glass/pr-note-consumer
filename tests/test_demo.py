import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rehearse", ROOT / "scripts/rehearse.py")
rehearse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rehearse)


def load(path):
    # BaseLoader preserves Actions' "on" key instead of YAML 1.1's boolean coercion.
    return yaml.load((ROOT / path).read_text(), Loader=yaml.BaseLoader)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.comment = load(".github/workflows/issuecomment.yml")
        self.probe = load(".github/workflows/firewall-demo.yml")

    def test_comment_contract_and_baseline(self):
        baseline = load("demo/before/issuecomment.yml")
        self.assertEqual(self.comment, baseline)
        self.assertEqual(self.comment["on"], {"issue_comment": {"types": ["created"]}})
        self.assertEqual(self.comment["permissions"], {})
        job = self.comment["jobs"]["comment"]
        self.assertEqual(job["permissions"], {"pull-requests": "write"})
        self.assertIn("github.event.issue.pull_request", job["if"])
        self.assertIn("github.event.comment.user.type != 'Bot'", job["if"])
        self.assertIn("!endsWith(github.event.comment.user.login, '[bot]')", job["if"])
        actions = [step for step in job["steps"] if "uses" in step]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["uses"], "Steve-Glass/pr-note@v3")
        self.assertEqual(actions[0]["with"], {
            "token": "${{ github.token }}", "body": "Thanks for the pull request!",
        })
        self.assertNotIn("checkout", json.dumps(self.comment))
        self.assertIn("github.event.comment.id", self.comment["run-name"])

    def test_probe_is_independent_and_policy_is_log(self):
        self.assertEqual(set(self.probe["on"]), {"workflow_dispatch"})
        self.assertEqual(self.probe["permissions"], {})
        self.assertNotIn("uses", json.dumps(self.probe))
        self.assertNotIn("secrets.", json.dumps(self.probe))
        self.assertNotIn("github.token", json.dumps(self.probe))
        self.assertNotIn("continue-on-error", json.dumps(self.probe))
        for workflow in (self.comment, self.probe):
            for job in workflow["jobs"].values():
                self.assertEqual(job["runs-on"], "ubuntu-24.04-firewall")
        policy = load(".github/egress-firewall.yaml")
        self.assertIn(policy["mode"], ("log", "enforce"))
        self.assertEqual(policy["allow"], ["api.github.com"])
        self.assertNotIn("no-default-urls", policy)
        self.assertFalse((ROOT / ".github/workflows/egress-firewall.yaml").exists())

    def test_comment_only_posts_the_note_without_demo_assertions(self):
        self.assertEqual(self.comment["jobs"]["comment"]["steps"], [{
            "name": "Post the note",
            "uses": "Steve-Glass/pr-note@v3",
            "with": {
                "token": "${{ github.token }}",
                "body": "Thanks for the pull request!",
            },
        }])

    def test_probe_outcomes_and_exact_credential_free_request(self):
        script = self.probe["jobs"]["probe"]["steps"][0]["run"]
        for expectation, code, http, expected_status in (
            ("reachable", 0, "200", 0), ("denied", 0, "200", 1),
            ("reachable", 22, "403", 22), ("denied", 22, "403", 22),
            ("denied", 6, "000", 6), ("reachable", 28, "000", 28),
            ("reachable", 0, "302", 1),
        ):
            with self.subTest(expectation=expectation, code=code, http=http):
                with tempfile.TemporaryDirectory() as temp:
                    curl = Path(temp) / "curl"
                    curl.write_text(
                        '#!/bin/bash\nprintf "%s\\n" "$@" > "$CURL_ARGS"\n'
                        'printf "%s" "$FAKE_HTTP"\nexit "$FAKE_EXIT"\n'
                    )
                    curl.chmod(0o755)
                    summary = Path(temp) / "summary"
                    args = Path(temp) / "args"
                    result = subprocess.run(["bash", "-e", "-c", script], env={
                        **os.environ, "PATH": temp + os.pathsep + os.environ["PATH"],
                        "GITHUB_STEP_SUMMARY": str(summary), "CURL_ARGS": str(args),
                        "FAKE_HTTP": http, "FAKE_EXIT": str(code), "EXPECTATION": expectation,
                        "RECORDING_ID": "receipt", "WORKFLOW_REF": "workflow@main",
                        "WORKFLOW_SHA": "test-sha", "RUN_URL": "https://github.com/test/run",
                    }, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected_status, result.stderr)
                    self.assertEqual(args.read_text().splitlines(), [
                        "--disable", "--silent", "--show-error", "--fail", "--proto", "=https",
                        "--connect-timeout", "10", "--max-time", "20", "--max-redirs", "0",
                        "--output", "/dev/null", "--write-out", "%{http_code}", "https://example.com/",
                    ])
                    self.assertIn("NOT proof of enforcement", summary.read_text())
                    self.assertIn(f"Actual curl exit: `{code}`; HTTP status: `{http}`",
                                  summary.read_text())


class HelperTests(unittest.TestCase):
    def test_write_defaults_to_preview(self):
        with patch.object(rehearse, "api") as api:
            result = rehearse.write_preview("POST", "endpoint", {"data": "fixture"}, False)
        api.assert_not_called()
        self.assertEqual(result, {"method": "POST", "path": "endpoint",
                                  "body": {"data": "fixture"}})

    def test_write_requires_explicit_apply(self):
        with patch.object(rehearse, "api", return_value={"id": 1}) as api:
            result = rehearse.write_preview("POST", "endpoint", {"data": "fixture"}, True)
        api.assert_called_once_with("endpoint", "POST", {"data": "fixture"})
        self.assertEqual(result, {"id": 1})

    def test_optional_api_never_hides_permission_errors(self):
        with patch.object(rehearse, "api", side_effect=RuntimeError("Forbidden (HTTP 403)")):
            with self.assertRaisesRegex(RuntimeError, "403"):
                rehearse.optional_api("endpoint")

    def test_trigger_preview_never_posts(self):
        pr = {"state": "open", "base": {"ref": "main"},
              "head": {"ref": rehearse.SAMPLE_BRANCH, "repo": {"full_name": rehearse.REPO}}}
        with patch.object(rehearse, "identity", return_value=({"default_branch": "main"}, "Steve-Glass")), \
                patch.object(rehearse, "active_workflow", return_value="sha-a"), \
                patch.object(rehearse, "api", return_value=pr) as api:
            receipt = rehearse.trigger(argparse.Namespace(pr=1, apply=False))
        self.assertFalse(receipt["applied"])
        self.assertEqual(api.call_args_list[0].args, (f"repos/{rehearse.REPO}/pulls/1",))
        self.assertEqual(api.call_count, 1)
        self.assertEqual(receipt["preview"]["method"], "POST")
        self.assertTrue(receipt["preview"]["body"]["body"].startswith("Demo checkpoint "))

    def test_dispatch_preview_never_posts(self):
        with patch.object(rehearse, "identity", return_value=({"default_branch": "main"}, "Steve-Glass")), \
                patch.object(rehearse, "active_workflow", return_value="sha-a"), \
                patch.object(rehearse, "contents", return_value={"content": "policy"}), \
                patch.object(rehearse, "api", return_value={"ref": "refs/heads/main"}) as api:
            result = rehearse.dispatch(argparse.Namespace(
                ref="main", expectation="reachable", apply=False,
            ))
        self.assertFalse(result["applied"])
        self.assertEqual(api.call_count, 1)
        self.assertEqual(api.call_args.args, (f"repos/{rehearse.REPO}/git/ref/heads/main",))
        self.assertEqual(result["request"]["body"]["inputs"]["expectation"], "reachable")
        self.assertTrue(result["title"].endswith(result["request"]["body"]["inputs"]["recording_id"]))

    def test_sample_preview_does_not_create_ref_file_or_pr(self):
        with patch.object(rehearse, "identity", return_value=({"default_branch": "main"}, "Steve-Glass")), \
                patch.object(rehearse, "api", side_effect=[[], {"sha": "sha-a"}]) as api, \
                patch.object(rehearse, "optional_api", return_value=None), \
                patch.object(rehearse, "command") as command:
            result = rehearse.sample_pr(argparse.Namespace(apply=False))
        command.assert_not_called()
        self.assertEqual(api.call_count, 2)
        self.assertEqual([step.get("method") for step in result["steps"]], ["POST", "PUT", None])
        self.assertFalse(result["applied"])

    def test_sample_reuses_existing_open_pr_without_writes(self):
        with patch.object(rehearse, "identity", return_value=({"default_branch": "main"}, "Steve-Glass")), \
                patch.object(rehearse, "api", return_value=[
                    {"state": "open", "html_url": "https://github.com/example/pr/1"},
                ]) as api:
            result = rehearse.sample_pr(argparse.Namespace(apply=True))
        self.assertTrue(result["reused"])
        self.assertEqual(api.call_count, 1)

    def test_closed_sample_does_not_create_duplicate(self):
        with patch.object(rehearse, "identity", return_value=({"default_branch": "main"}, "Steve-Glass")), \
                patch.object(rehearse, "api", return_value=[{"state": "closed"}]):
            with self.assertRaisesRegex(RuntimeError, "Reopen"):
                rehearse.sample_pr(argparse.Namespace(apply=True))

    def test_exact_run_matching_rejects_unrelated_runs(self):
        receipt = {"event": "issue_comment", "title": "PR note | comment 123", "sha": "sha-a",
                   "branch": "main", "actor": "Steve-Glass", "since": "2026-10-04T10:00:00+00:00"}
        correct = {"event": receipt["event"], "display_title": receipt["title"],
                   "head_sha": receipt["sha"], "head_branch": "main", "actor": {"login": "Steve-Glass"},
                   "created_at": "2026-10-04T10:00:01Z"}
        wrong = [
            {**correct, "display_title": "PR note | comment 124"},
            {**correct, "event": "workflow_dispatch"}, {**correct, "head_sha": "sha-b"},
            {**correct, "head_branch": "other"}, {**correct, "actor": {"login": "other"}},
            {**correct, "created_at": "2026-10-04T09:59:59Z"},
        ]
        self.assertEqual(rehearse.matched_runs(receipt, wrong + [correct]), [correct])

    def test_dry_run_receipt_is_not_execution_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt = Path(temp) / "receipt.json"
            receipt.write_text(json.dumps({"applied": False, "repo": rehearse.REPO}))
            with self.assertRaisesRegex(RuntimeError, "applied receipt"):
                rehearse.evidence(argparse.Namespace(receipt=str(receipt)))

    def test_evidence_rejects_rerun_and_preserves_exact_snapshots(self):
        receipt = {"applied": True, "repo": rehearse.REPO, "event": "workflow_dispatch",
                   "workflow": "firewall-demo.yml", "title": "Firewall probe | unique",
                   "branch": "main", "sha": "sha-a", "actor": "Steve-Glass",
                   "since": "2026-10-04T10:00:00+00:00"}
        run = {"id": 123, "event": receipt["event"], "display_title": receipt["title"],
               "head_sha": "sha-a", "head_branch": "main", "actor": {"login": "Steve-Glass"},
               "created_at": "2026-10-04T10:00:01Z", "run_attempt": 1, "status": "completed",
               "html_url": "https://github.com/test/run/123", "conclusion": "failure"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            path.write_text(json.dumps(receipt))
            args = argparse.Namespace(receipt=str(path), out=temp)
            with patch.object(rehearse, "identity"), patch.object(rehearse, "command", side_effect=[
                json.dumps([{"workflow_runs": [{**run, "run_attempt": 2}]}]),
            ]):
                with self.assertRaisesRegex(RuntimeError, "NEW trigger"):
                    rehearse.evidence(args)
            with patch.object(rehearse, "identity"), patch.object(rehearse, "command", side_effect=[
                json.dumps([{"workflow_runs": [run]}]), "raw log",
                json.dumps([{"artifacts": []}]),
            ]), patch.object(rehearse, "contents", return_value={
                "sha": "blob-id", "content": "c25hcHNob3Q=",
            }) as contents:
                result = rehearse.evidence(args)
            self.assertEqual(result["conclusion"], "failure")
            self.assertIn("NOT INFERRED", result["verdict"])
            self.assertEqual(result["artifacts"], [])
            self.assertTrue(all(call.args[1] == "sha-a" for call in contents.call_args_list))
            self.assertEqual((Path(temp) / "123/actions.lock").read_text(), "snapshot")
            self.assertEqual((Path(temp) / "123/run.log").read_text(), "raw log\n")


if __name__ == "__main__":
    unittest.main()
