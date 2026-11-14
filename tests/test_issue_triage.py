import json
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class IssueTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (ROOT / ".github/workflows/issue-triage.lock.yml").read_text()
        cls.workflow = yaml.load(text, Loader=yaml.BaseLoader)
        cls.manifest = json.loads(text.splitlines()[1].split(": ", 1)[1])

    def step(self, job, step_id):
        return next(step for step in self.workflow["jobs"][job]["steps"]
                    if step.get("id") == step_id)

    def test_event_and_read_only_agent(self):
        self.assertEqual(self.workflow["on"], {"issues": {"types": ["opened"]}})
        self.assertEqual(self.workflow["permissions"], {})
        agent = self.workflow["jobs"]["agent"]
        self.assertEqual(agent["permissions"], {"contents": "read", "issues": "read"})
        tools = {server["name"]: server["tools"] for server in self.manifest["mcp_servers"]}
        self.assertEqual(tools["github"], ["issue_read"])
        self.assertEqual(set(tools["safeoutputs"]), {
            "add_labels", "noop", "report_incomplete", "report_missing_data",
            "report_missing_tool",
        })
        run = next(step for step in agent["steps"]
                   if "GH_AW_MAX_TURNS" in step.get("env", {}))
        self.assertEqual(run["env"]["GH_AW_MAX_TURNS"], "10")
        self.assertEqual(run["timeout-minutes"], "10")

    def test_label_output_is_single_existing_category_on_triggering_issue(self):
        output = self.workflow["jobs"]["safe_outputs"]
        self.assertEqual(output["permissions"], {"issues": "write"})
        step = self.step("safe_outputs", "process_safe_outputs")
        config = json.loads(step["env"]["GH_AW_SAFE_OUTPUTS_HANDLER_CONFIG"])
        self.assertEqual(config["add_labels"], {
            "allowed": ["bug", "enhancement", "documentation"],
            "create_if_missing": False,
            "max": 1,
            "max_labels": 1,
            "target": "triggering",
        })
        self.assertNotIn("create_issue", config)
        self.assertNotIn("create_report_incomplete_issue", config)
        self.assertEqual(step["with"]["github-token"], "${{ secrets.GITHUB_TOKEN }}")

    def test_role_integrity_and_detection_gates_are_retained(self):
        roles = self.step("pre_activation", "check_membership")["env"]
        self.assertEqual(roles["GH_AW_REQUIRED_ROLES"], "admin,maintainer,write")
        self.assertEqual(self.workflow["jobs"]["activation"]["if"],
                         "needs.pre_activation.outputs.activated == 'true'")
        agent = self.workflow["jobs"]["agent"]
        gateway = next(step["run"] for step in agent["steps"]
                       if "start_mcp_gateway.cjs" in step.get("run", ""))
        self.assertIn('"min-integrity": "approved"', gateway)
        self.assertIn('"steve-glass/pr-note-consumer"', gateway)
        self.assertIn('"GITHUB_READ_ONLY": "1"', gateway)
        output = self.workflow["jobs"]["safe_outputs"]
        self.assertIn("detection", output["needs"])
        self.assertIn("needs.detection.result == 'success'", output["if"])
        self.assertEqual(self.manifest["threat_detection"]["mode"], "enabled")

    def test_diagnostic_issue_creation_is_disabled_without_hiding_failure(self):
        self.assertEqual(self.step("conclusion", "missing_tool")["env"]
                         ["GH_AW_MISSING_TOOL_CREATE_ISSUE"], "false")
        self.assertEqual(self.step("conclusion", "report_incomplete")["env"]
                         ["GH_AW_REPORT_INCOMPLETE_CREATE_ISSUE"], "false")
        failure = self.step("conclusion", "handle_agent_failure")["env"]
        self.assertEqual(failure["GH_AW_FAILURE_REPORT_AS_ISSUE"], "false")
        self.assertEqual(failure["GH_AW_MISSING_TOOL_REPORT_AS_FAILURE"], "true")
        self.assertEqual(failure["GH_AW_MISSING_DATA_REPORT_AS_FAILURE"], "true")
        self.assertNotIn("report_failed_jobs", {
            step.get("id") for step in self.workflow["jobs"]["conclusion"]["steps"]
        })


if __name__ == "__main__":
    unittest.main()
