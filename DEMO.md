# Recording runbook: two independent controls

This is a **pre-recorded, narrated** TRU1556M demonstration. The dependency clip
selects benign A after `v3` moves to benign B; the firewall clip makes a separate
credential-free request. No payload blocked by locking subsequently runs. No
real secret is sent. Do not present intended results as observations.

Producer context for adjacent clips: `lint-defaults.yml` shows the original
checkout/cache defaults, improved `lint.yml` uses `pull_request`, and `release.yml`
uses `cache-mode: none` with an explicit Steve-Glass-only actor policy targeting
that release workflow. Those belong to the producer, not this repository.
Fork approval is a **producer settings-only highlight**: no recorded fork PR,
waiting-approval screen, or approval flow. The ordinary consumer sample PR and
human comment below are still required. Firewall artifacts are not Policy
insights; Policy insights concerns workflow execution protections.

## Approval and preparation

The implementation branch may be pushed with approval. Publishing to `main`,
opening PRs, writing sample fixtures/comments, dispatching runs, changing policy,
and changing settings are separate mutations requiring approval. None of the
validation commands does those operations. Helpers preview by default; an
operator runs `--apply` only for a specifically approved phase. Coding agents
use the app's PR-creation tool when supported rather than silently bypassing it.

Feature-owner approval for the planned locked-dependency recording is confirmed.
It is not blanket approval to publish private source documentation or sensitive
preflight data. Keep evidence local and only use approved recording material.
Use the existing authenticated human account; never print an auth token.

```sh
python3 scripts/rehearse.py preflight
gh actions-lock --help
mkdir -p .demo-evidence
```

Record the actual default branch, producer A SHA, published release metadata
and branch containing A. Do not assign a made-up SHA to `A_SHA`.

```sh
gh api repos/Steve-Glass/pr-note/commits/v3 --jq .sha
gh api repos/Steve-Glass/pr-note/commits/v3.0.0 --jq .sha
gh api repos/Steve-Glass/pr-note/releases/tags/v3.0.0 \
  --jq '{tag_name,target_commitish,immutable,published_at,html_url}'
gh api repos/Steve-Glass/pr-note/commits/"$A_SHA"/branches-where-head
```

Call this "published v3.0.0 at reviewed A," not a platform-enforced immutable
release: the observed release reports `immutable: false`. The locking claim is
about the reviewed commit identity, not release immutability.

Both resolved refs must equal the coordinator's reviewed A SHA. If A is not
currently a branch head, use the producer's named retaining branch and verify
`gh api repos/Steve-Glass/pr-note/compare/"$A_SHA"...BRANCH --jq .status` is
`ahead` or `identical`; do not equate an empty head lookup with unreachability.
No producer mutations from this session.

## 1. A simple Action posts the note

**Initial state:** Published producer `v3 -> A`; actual **unenrolled** consumer
workflow and `log` policy published on `main` through an approved change.
Preserve that real consumer baseline commit as `BASELINE_SHA` in the recording
notes. The display file alone is not a baseline run.

```sh
python3 scripts/rehearse.py sample-pr                 # inspect preview first
python3 scripts/rehearse.py sample-pr --apply         # only after approval
# Record the returned PR number as PR_NUMBER.
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER"
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER" --apply \
  > .demo-evidence/baseline-comment.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/baseline-comment.json
```

**Capture:** sample PR's human trigger and bot reply, corresponding run, producer
log marker, actual output A, and runner Action-resolution SHA. Opening the PR
alone does not trigger it. Do not use a workflow's `GITHUB_TOKEN` for the trigger.

**Narration:** "This simple Action thanks someone for their pull request. Today
this friendly `v3` reference points to the benign revision I reviewed."

**Expected:** the reply is exactly `Thanks for the pull request!`, the Action
reports A, and the runner uses A. **Actual evidence:** receipt comment URL/ID,
exact run URL, resolved SHA, summary output, reply URL, and baseline commit.
If there is no run, inspect default-branch publication and event policy, not the
most recent unrelated run.

**Repeat/reset:** reuse the same open sample PR and create a new human comment
with a new receipt filename. No duplicate PRs or automatic comment deletion.
Preserve the baseline commit and `demo/before/issuecomment.yml`; do not overwrite
enrolled YAML with the display snapshot later.

## 2. Lock the reviewed A identity

**Initial state:** actual baseline captured, producer still at A, all workflow
scaffolding complete. Wait for the producer handoff before generation.

```sh
gh actions-lock --no-narrow --no-interactive
git diff -- .github/workflows
cat .github/workflows/actions.lock
gh actions-lock --verify-local --no-fix
gh actions-lock --verify --json
```

Keep the full-directory scan. `--no-narrow` is required here to preserve the
literal `Steve-Glass/pr-note@v3`; the CLI's generic default would narrow it.
Review actual generated entries and repository IDs against
`gh api repos/Steve-Glass/pr-note --jq '{id,owner_id:.owner.id}'`.
Verify the producer entry's commit equals `A_SHA`, its recorded ref/reachability
is valid, and the comment workflow is enrolled. Do not manufacture fields or
an entry for the action-free probe. No `--relock` or `--accept-moved`.

After **separate approval**, publish this reviewed workflow/lockfile state to
`main`, record its commit as `LOCKED_SHA`, then:

```sh
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER" --apply \
  > .demo-evidence/locked-a-comment.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/locked-a-comment.json
```

**Capture:** display-only before source versus the actual generated diff,
native lock entry and workflow enrollment, then the exact run's dependency
resolution and actual A output/reply.

**Narration:** "I keep the readable version reference and review the identity
recorded by the native lockfile tool. I then verify the runner actually executes A."

**Expected:** enrolled execution resolves and runs A. **Actual evidence:** CLI
version/output, reviewed lock identity and generated diff, run metadata/logs,
actual marker/output and reply. Local coverage is not runtime proof. If startup
rejects the dependency or native access is missing, record the real error and
mark this checkpoint blocked; do not narrate it as A executing.

**Repeat/reset:** a fresh comment may repeat A; do not regenerate or refresh pins.
**STOP HERE. Tell the coordinator A executed successfully and supply evidence.
Do not let the producer advance `v3` before that handoff.**

## 3. Upstream changes; a NEW run still executes A

**Initial state:** coordinator confirms approved benign B publication;
`v3.0.1 -> B`, `v3 -> B`, and reviewed A remains branch-reachable.
Consumer workflow and lockfile stay byte-for-byte unchanged.

```sh
gh api repos/Steve-Glass/pr-note/commits/v3 --jq .sha
gh api repos/Steve-Glass/pr-note/commits/v3.0.1 --jq .sha
# Save these observed B resolutions before posting the new trigger.
git diff "$LOCKED_SHA" -- .github/workflows/issuecomment.yml .github/workflows/actions.lock
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER" --apply \
  > .demo-evidence/after-b-comment.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/after-b-comment.json
```

**Capture:** actual upstream B SHA next to reviewed A lock identity, new comment
ID/new run ID (attempt 1), runner resolution SHA A, and actual Action output A.
Compare the exact committed workflow/lockfile snapshots collected for both runs,
not merely the working tree. No rerun of the previous run.

**Narration:** "The publisher moved `v3` to another harmless revision. This new
consumer run still selects my reviewed A identity, even though the alias now resolves to B."

**Expected:** actual resolution and execution A, unchanged reply. **Actual
evidence:** upstream B lookup, both runs' committed blob identities, new receipt,
runner SHA A and Action output A. B output, lock errors, skipped steps, or printed
expectations are not success. A output alone does not establish native selection.

**Repeat/reset:** post a new comment without touching the lockfile or workflow.
Do not automatically relock. Any deliberate update is outside the core clip
and requires its own approval.

## 4. Establish external reachability in log mode

**Initial state:** committed `mode: log` on the explicitly dispatched branch;
completed locking checkpoints remain separate. The probe workflow must also
exist on the default branch.

```sh
python3 scripts/rehearse.py dispatch --ref main --expectation reachable
python3 scripts/rehearse.py dispatch --ref main --expectation reachable --apply \
  > .demo-evidence/log-probe.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/log-probe.json
```

**Capture:** selected ref, committed log policy, exact request, actual curl
exit 0 and 2xx status, run summary and firewall artifacts. The helper creates
a unique recording ID to correlate dispatches; it never guesses the latest run.

**Narration:** "This is a separate, credential-free network request, not part
of the comment Action. I first establish that the same destination is reachable."

**Expected:** successful request. **Actual evidence:** receipt/run ID, workflow
SHA, committed policy snapshot, request time/status and native traffic record.
If log mode fails, investigate proxy, runner or destination behavior. Do not
proceed as though the baseline succeeded.

**Repeat/reset:** dispatch again on the same reviewed log ref with a new receipt.
Keep every dependency lock on any named recording branch. A change on `main`
cannot change a dispatch from another ref.

## 5. Enforce and correlate the actual deny

**Initial state:** successful log baseline captured. With approval, change only
`.github/egress-firewall.yaml` from `mode: log` to `mode: enforce`, retain
`api.github.com`, and publish that reviewed policy change to `main`. Keep
`example.com` outside the additive allowlist. Record the policy commit.

```sh
git diff -- .github/egress-firewall.yaml
# Publish the reviewed policy only after approval, then:
python3 scripts/rehearse.py dispatch --ref main --expectation denied
python3 scripts/rehearse.py dispatch --ref main --expectation denied --apply \
  > .demo-evidence/enforce-probe.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/enforce-probe.json
# From that exact result, set RUN_ID and select an actual artifact name:
gh api repos/Steve-Glass/pr-note-consumer/actions/runs/"$RUN_ID"/artifacts \
  --jq '.artifacts[] | {id,name,expired,archive_download_url}'
gh run download "$RUN_ID" --repo Steve-Glass/pr-note-consumer \
  --name "$ARTIFACT_NAME" --dir ".demo-evidence/$RUN_ID/firewall"
```

**Capture:** exact run's native firewall summary and downloaded artifact showing
the deny for `curl`, `https://example.com/`, and its rule; correlate run/ref/SHA
and request time with the probe summary. Read the actual artifact schema rather
than assuming its name or fields. Preserve its ID and download reference.

**Narration:** "The same harmless request is now outside the enforced allowlist.
This matching firewall deny event, not just a network error, is the evidence."

**Expected:** the probe is **intentionally visibly failed**, with a matching
native deny event. **Actual evidence:** raw request result, committed enforce
policy, native deny rule/destination/command and same-run artifact. A random
curl error, missing artifact/runner, or proxy failure is not proof; an unexpected
2xx response is explicitly flagged as failure to demonstrate containment.

**Repeat/reset:** dispatch a new run on the same enforce ref. To repeat log
baseline, approve and publish a log-mode policy change or use a preserved,
clearly identified log ref. Never edit policy silently between captures.

## 6. Legitimate commenting still works

**Initial state:** reviewed enforce policy active on `main`, API host allowed,
consumer workflow/lockfile unchanged; upstream still at approved B.

```sh
python3 scripts/rehearse.py trigger --pr "$PR_NUMBER" --apply \
  > .demo-evidence/enforced-comment.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/enforced-comment.json
```

**Capture:** new reply, actual A output, runner A identity, enforce policy
snapshot, and native traffic evidence for legitimate commenting.

**Narration:** "The external request was contained, while the intended GitHub
comment still works. Dependency identity and outbound traffic are separate controls."

**Expected:** successful A execution and exact thank-you reply under enforcement.
**Actual evidence:** new trigger/run/reply URLs, resolved SHA and actual output,
same-ref policy and native artifacts. If legitimate requests fail, inspect real
traffic and propose only the necessary additional hosts for review.

**Repeat/reset:** new human comment and receipt; do not change permissions,
weaken inherited policy, or refresh the lock to force a green recording.

## Initial status and remaining gaps

| Checkpoint | Status at scaffold delivery | Resolution/evidence required |
| --- | --- | --- |
| Local workflows, guards, summaries, bounded probe, helper dry-runs | Verified locally | Unit tests stub all requests; no remote execution claim. |
| Producer A readiness | Blocked | Coordinator supplies published A SHA, actual release/ref evidence and retaining branch. |
| Native onboarding | Blocked on A | Run official `gh actions-lock --no-narrow --no-interactive`; inspect generated diff and identity. |
| Native runtime enforcement | Not rehearsed | Approved enrolled A run, then stop; approved upstream B move followed by new unchanged consumer run selecting A. |
| Preview sources / authentication | Inspect with read-only preflight | Keep access results local. Documentation access does not prove runtime access. |
| Firewall runner and log baseline | Implemented, not rehearsed | Approved same-ref dispatch must start and successfully reach the destination; inspect real traffic. |
| Enforced deny and legitimate comment | Implemented, not rehearsed | Approved committed enforce policy, correlated native deny artifact, then successful real comment. |
| Event/organization/enterprise policy | Runtime untested | If blocked, inspect exact run/policy error and its source. Request scoped help; never weaken unrelated protections. |
| Locked-dependency recording approval | Confirmed separately | Use only approved recording material; no private source documentation or sensitive preflight output in Git. |

No documented supported API was used to assert that this repository's native
runtime enforcement is enabled. Do not invent an enrollment flag, call future
capabilities available today, or equate repository admin permission with preview
availability. If a run cannot start, report its queue/startup error and seek
preview access help through the coordinator. Settings-only UI capture may still
be needed on the producer; it is not a consumer code or permission change.
