# Demo guide

This repository separates dependency identity from outbound network policy.
The producer Action and its A/B revisions are benign. The independent firewall
probe sends no credentials, files, environment data, or query payloads. No
payload blocked by locking subsequently runs.

## Producer-to-consumer flow

Use the producer's verified source and annotations for the lead-in; do not
duplicate its setup here. Keep on-screen highlights limited to the relevant
event, annotation, policy target, or cache line.

| Step | Focus and on-screen highlight |
| --- | --- |
| Original attack model | Explain the risk of contributor-controlled code entering a privileged workflow or shared cache path. This is a model, not an attack performed by the demo. |
| Implicit producer defaults | Show the original `pull_request_target` lint workflow and its checkout-hardening/read-only-cache annotations. Keep the workflow unchanged for this comparison; a YAML migration is not the main protection being demonstrated. |
| Upcoming default WEP event restriction | Show the [default `pull_request_target` policy](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target#default-policy-for-pull_request_target) for affected public repositories. Enforcement is scheduled for November 2, 2026 for the affected rollout cohort; check the effective policy. Briefly show an optional `pull_request` migration for lint needing no secrets or elevated permissions. |
| Explicit release actor policy | Highlight the Steve-Glass-only actor allowlist and its `release.yml` target. It is separate from the upcoming default event restriction. |
| Release cache opt-out | Retain setup-node `cache: npm` with workflow-level `cache-mode: none`: the [producer's read-only hosted check](https://github.com/Steve-Glass/pr-note/actions/runs/37483252644) succeeded with cache-read/cache-write denial warnings, confirming tolerance of denied cache access, not a poisoned-entry experiment or release publication. |
| Consumer dependency identity | Show the new zizmor workflow, then manually run `gh actions-lock --no-narrow --no-interactive` to add its dependencies while retaining the existing A lock. Runtime enforcement remains unresolved in the open issue below. |
| Independent firewall request | Open **Actions > Firewall demo > Run workflow** on `main`. Show the enforce-mode domain allowlist and single credential-free request, then inspect matching native deny evidence rather than treating a red step as proof. |

As of October 6, 2026, the upcoming default event restriction is not an observed
active enforcement result. Its scope excludes private/internal repositories
and does not replace an applicable existing Actions event policy.

Changing an event to `pull_request` is not universal isolation for unsafe code,
especially on persistent self-hosted runners. Fork/external-contributor approval
is background context only, not part of the core recording or an approval-flow
demonstration; no existing producer setting needs to change.

## Current state

The official `gh-actions-lock` CLI has already generated and committed
`.github/workflows/actions.lock`, recording reviewed A while retaining
`Steve-Glass/pr-note@v3` in the workflow.

The manual locking recording has added `.github/workflows/zizmor.yml` and its
dependencies to the lockfile, with `actions/checkout@v6.1.0` and
`zizmorcore/zizmor-action@v0.6.4` in the workflow. Preserve these generated changes.
The analyzer version is fixed at `1.30.1`; its normal PR/main-push workflow only
analyzes files and uploads SARIF, without executing checked-out project code.

The after-B run selected B despite the unchanged workflow and lockfile. The
cause is unknown and tracked in [the open native-locking issue](https://github.com/Steve-Glass/pr-note-consumer/issues/2).
Do not claim A-after-B enforcement succeeded. Further runtime verification is
deferred; the manual CLI recording need not start a comment replay or firewall
probe. Publishing the zizmor workflow on `main` triggers its own analysis job.

| Reference | Preserved identity |
| --- | --- |
| Unlocked consumer baseline | `53f8dd1f4f056bc37f043d2a3883e3e16e0ed510` |
| Consumer state used for both locked comparisons | `60d19c783b1c12b3654cd6f7f6e94fea27234c4e` |
| Reviewed producer A (`v3.0.0`) | `a53b99fc9738713d0a1d0dba397606f0f0352a98` |
| Published producer B (`v3.0.1`, moved `v3`) | `47713a3d521b26f4fa13e43fb64b0687c7603980` |

These release names identify published commits, not platform-enforced immutable
releases. The display-only `demo/before/issuecomment.yml` does not activate a
baseline. Preserve the real commits and run evidence; do not reset tags, delete
the lockfile, or overwrite enrolled YAML to stage a different result.

Neither the current comment workflow nor the display-only before example
includes the demo-only output summary or expected-A assertion. Earlier commits
and runs retain that diagnostic history. Removing the check does not resolve
or verify native locking.

## Record the official CLI command

Use authenticated `gh` with the official
[github/gh-actions-lock](https://github.com/github/gh-actions-lock) extension.
If the extension is missing, install it with
`gh extension install github/gh-actions-lock`.

When ready to record manually:

```sh
gh actions-lock --help
cat .github/workflows/zizmor.yml
cat .github/workflows/actions.lock
gh actions-lock --no-narrow --no-interactive
git diff -- .github/workflows
```

The command has already been used for both the comment and zizmor workflows.
The lock now includes zizmor's direct and transitive dependencies, including
its SARIF upload Action. A repeat manual run may produce no diff. Inspect any
actual changes and confirm the existing `pr-note@v3` pin stays at A.
Review resulting changes before publishing. Do not use `--relock`,
`--accept-moved`, or delete the lock to manufacture a diff.

**Show:** the new workflow's `uses` lines, the exact CLI command, the generated
dependency additions, and the unchanged recorded A identity. Explain that
`--no-narrow` preserves the literal tag references, including `@v3`;
without it, the CLI normally narrows new version references to full semver tags.
`--no-interactive` avoids prompts. Neither flag proves runtime enforcement.

The comment workflow is listed in the generated workflow map. The independent
probe has no `uses` dependencies; do not invent an empty enrollment entry.
Keep CLI output distinct from runtime evidence and leave the mismatch issue
open until the behavior is understood.

## Optional runtime checks

The steps below describe later, separately approved checks. They are not
required for the CLI recording and must not run automatically. Helpers preview
mutations by default. Adding `--apply` posts a comment, creates a sample fixture,
or dispatches a workflow; inspect the preview and approve the specific operation.

Use the existing authenticated human account, never print a token, and keep
raw evidence in the ignored `.demo-evidence/` directory. Use only material
approved for disclosure; do not publish private source documentation or
sensitive preflight output.

```sh
python3 scripts/rehearse.py preflight
mkdir -p .demo-evidence
```

### 1. Comment workflow

The workflow must be on the default branch. It handles human comments on pull
requests, excludes bots, and does not check out PR code. Opening a PR alone is
not a trigger; a comment made with a workflow's `GITHUB_TOKEN` generally does
not trigger another workflow.

```sh
python3 scripts/rehearse.py sample-pr
# After approval, create or reuse the single sample PR:
python3 scripts/rehearse.py sample-pr --apply
# Set PR_NUMBER from the returned PR.
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER"
# After approval, use a new receipt filename:
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER" --apply \
  > .demo-evidence/comment.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/comment.json
```

**Expected behavior:** the Action posts `Thanks for the pull request!`.
**Evidence:** the human trigger URL/ID, exact fresh run, runner Action SHA,
producer revision marker in the logs, and bot reply. Expected and actual values
must remain separate. The workflow no longer asserts revision A, so a successful
comment job is not evidence that the recorded identity was selected. Inspect
the actual runner SHA and marker for any separately approved investigation.

Reuse the open sample PR instead of creating duplicates. Preserve the earlier
unlocked baseline as historical evidence rather than reenacting it by resetting
current state.

### 2. Inspect the recorded identity

Review `.github/workflows/actions.lock` alongside the workflow's literal `@v3`.
The reviewed pin is A, not whatever commit the alias currently selects.
No lockfile generation, dependency update, or tag reset is needed for this view.

For any later runtime investigation, preserve the exact workflow and lockfile
blob identities and compare them to the run's own commit. A file on disk, a
managed-file comment, a valid local check, or a successful A run while `v3 = A`
does not prove native enforcement.

### 3. Compare after the alias moves (deferred)

Upstream has already moved to B. The original comparison is complete and
recorded in the open issue; do not post another trigger automatically.

For a later approved investigation:

```sh
gh api repos/Steve-Glass/pr-note/commits/v3 --jq .sha
gh api repos/Steve-Glass/pr-note/commits/v3.0.1 --jq .sha
# Compare against the preserved locked checkpoint:
git diff "$LOCKED_SHA" -- .github/workflows/issuecomment.yml .github/workflows/actions.lock
```

**Intended result:** with upstream at B, a new unchanged consumer run selects A.
**Observed result so far:** the fresh run selected B and reported B; the
expected-A check failed. The cause is not established. Confirmation of runtime
enablement/compatibility must come from the feature owner, not an invented flag
or a silent inline-SHA substitution.

If another run is later approved, use a new human comment and receipt, not a
rerun. Compare upstream resolution, run ID/attempt, workflow/lockfile snapshots,
actual runner SHA, actual output, and real reply. A rejected or skipped Action
is not evidence that A executed.

### 4. Run the simple firewall demo manually

Open **Actions > Firewall demo > Run workflow**, select **main**, and run it
when ready. There are no required inputs and no log-baseline step in this flow.
This request is independent of dependency locking.

**Show:** `.github/egress-firewall.yaml` with `mode: enforce` and the added
domains `api.github.com`, `registry.npmjs.org`, and `ghcr.io`, then the workflow's
single `curl` request to `https://example.com/`. The allowlist adds domains to
platform defaults; it does not filter URL paths. `example.com` is outside the
added list. The request contains no credentials or payload, disables implicit
curl configuration, follows no redirects, and has bounded timeouts.

Optional CLI alternative (preview first; `--apply` starts the manual workflow):

```sh
python3 scripts/rehearse.py dispatch --ref main
# Only when ready to run:
python3 scripts/rehearse.py dispatch --ref main --apply \
  > .demo-evidence/firewall-dispatch.json
```

Publishing the workflow does not dispatch it. These instructions do not claim
the request has run, been denied, or encountered a runner/backend problem.

### 5. Inspect the actual outcome

Use the exact run opened from the manual dispatch. A failed curl step alone
is not evidence of enforcement. Look for that run's native firewall deny event
matching `curl`, `https://example.com/`, the request time, and the policy ref/SHA.
Preserve its rule and artifact reference; read the actual artifact schema.

```sh
gh run view "$RUN_ID" --repo Steve-Glass/pr-note-consumer --log
gh api repos/Steve-Glass/pr-note-consumer/actions/runs/"$RUN_ID"/artifacts
gh run download "$RUN_ID" --repo Steve-Glass/pr-note-consumer \
  --name "$ARTIFACT_NAME" --dir ".demo-evidence/$RUN_ID/firewall"
# If the optional helper created a dispatch receipt:
python3 scripts/rehearse.py evidence --receipt .demo-evidence/firewall-dispatch.json \
  --run-id "$RUN_ID"
```

The helper requires a selected run ID for input-free dispatches and checks its
event, ref, SHA, actor and time against the receipt. It does not choose the
latest run automatically.

Curl failures remain failures without suppression. DNS, timeout, arbitrary
HTTP errors, or runner unavailability must not be labeled a policy deny.
Unexpected success does not demonstrate containment either; this simple
workflow does not add an expected-result assertion. Configuration alone does
not prove or fix runner/backend access.

Policy comes from the workflow's ref. Editing `main` does not change a dispatch
from another branch. Keep evidence tied to the selected commit.

### 6. Legitimate commenting under enforcement (not performed)

After a confirmed firewall checkpoint, a separately approved new comment should
still receive the exact thank-you reply with only `pull-requests: write`.
Capture the real Action SHA/output, reply, committed policy, and native traffic
evidence. Any A-identity claim also depends on resolving the open locking issue.
Do not refresh pins or weaken unrelated protections to make the run green.

Firewall artifacts are not Policy insights; Policy insights concerns workflow
execution protections. Preview documentation access or repository admin
permission does not prove native runtime availability. Report actual errors
and use the open issue to resolve the locking mismatch without altering the
preserved reproduction.
