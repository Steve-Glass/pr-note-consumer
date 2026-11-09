// Offline harness for the exact compiler-pinned gh-aw setup runtime, not source-run code.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const directory = process.env.GH_AW_MEMBERSHIP_SOURCE;
assert.ok(directory, "Set GH_AW_MEMBERSHIP_SOURCE to the downloaded pinned runtime directory");
const hashes = {
  "check_membership.cjs": "ab1bf5eac4243efb3125043061990cbc0bb786d266ada15d8bd513400d176fc5",
  "check_permissions_utils.cjs": "089ead78269bbcb273640ca2ab38cbfbaa6292170e424493f30dc3db8dc30913",
};
const sources = {};
for (const [file, hash] of Object.entries(hashes)) {
  const bytes = fs.readFileSync(path.join(directory, file));
  assert.equal(crypto.createHash("sha256").update(bytes).digest("hex"), hash,
    "Runtime must match gh-aw-actions/setup@221ba4f4319de6b8e809d1a15528b3ae6a818aa5");
  sources[file] = bytes.toString("utf8");
}

async function authorize(eventName, actor, permission, errorStatus) {
  const outputs = {};
  const lookups = [];
  const core = {
    info() {}, warning() {}, debug() {},
    setOutput(key, value) { outputs[key] = value; },
  };
  const github = { rest: { repos: {
    async getCollaboratorPermissionLevel(request) {
      lookups.push(request.username);
      if (errorStatus) throw Object.assign(new Error("stubbed API failure"), { status: errorStatus });
      return { data: { permission, role_name: permission } };
    },
  } } };
  const context = {
    eventName, actor, repo: { owner: "Steve-Glass", repo: "pr-note-consumer" },
    // Deliberately different: workflow_run must validate context.actor, not this field.
    payload: { workflow_run: { actor: { login: "different-source-actor" } } },
  };
  const cache = {};
  const stubs = {
    "./error_helpers.cjs": { getErrorMessage: error => error.message },
    "./pre_activation_summary.cjs": { async writeDenialSummary() {} },
    "./error_recovery.cjs": {
      withRetry: operation => operation(),
      isTransientError: () => false,
    },
  };
  function load(file) {
    if (cache[file]) return cache[file];
    const module = { exports: {} };
    const sandbox = {
      module, exports: module.exports, core, github, context,
      process: { env: { GH_AW_REQUIRED_ROLES: "admin,maintainer,write" } },
      require(name) {
        if (stubs[name]) return stubs[name];
        const dependency = name.replace("./", "");
        assert.ok(Object.hasOwn(sources, dependency), "Unexpected runtime dependency");
        return load(dependency);
      },
    };
    vm.runInNewContext(sources[file], sandbox, { filename: file, timeout: 1000 });
    cache[file] = module.exports;
    return module.exports;
  }
  await load("check_membership.cjs").main();
  return { outputs, lookups };
}

test("schedules bypass role lookup even for non-writers or bots", async () => {
  for (const actor of ["reader", "github-actions[bot]"]) {
    const { outputs, lookups } = await authorize("schedule", actor, "read", 403);
    assert.equal(outputs.is_team_member, "true");
    assert.equal(outputs.result, "safe_event");
    assert.deepEqual(lookups, []);
  }
});

test("workflow_run accepts only matching trusted human roles", async () => {
  for (const role of ["admin", "maintain", "write"]) {
    const { outputs, lookups } = await authorize("workflow_run", "writer", role);
    assert.equal(outputs.is_team_member, "true");
    assert.deepEqual(lookups, ["writer"]);
  }
  for (const role of ["read", "triage"]) {
    const { outputs } = await authorize("workflow_run", "reader", role);
    assert.equal(outputs.is_team_member, "false");
    assert.equal(outputs.result, "insufficient_permissions");
  }
});

test("workflow_run bots do not bypass roles, and lookup failures deny", async () => {
  const denied = await authorize("workflow_run", "github-actions[bot]", "read");
  assert.equal(denied.outputs.is_team_member, "false");
  for (const status of [403, 404, 500]) {
    const { outputs, lookups } = await authorize("workflow_run", "github-actions[bot]", null, status);
    assert.equal(outputs.is_team_member, "false");
    assert.equal(outputs.result, "api_error");
    assert.deepEqual(lookups, ["github-actions[bot]"]);
  }
  // There is no blanket bot ban either: an API-confirmed writer still passes.
  const writer = await authorize("workflow_run", "trusted-bot[bot]", "write");
  assert.equal(writer.outputs.is_team_member, "true");
});
