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
| Consumer dependency identity | Show `gh actions-lock --no-narrow --no-interactive` and the existing A lock. Runtime enforcement remains unresolved in the open issue below. |
| Independent firewall request | Transition from dependency identity to a separate credential-free request. Keep the current log policy; any later enforce comparison needs its own approved run and correlated deny evidence. |

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

The after-B run selected B despite the unchanged workflow and lockfile. The
cause is unknown and tracked in [the open native-locking issue](https://github.com/Steve-Glass/pr-note-consumer/issues/2).
Do not claim A-after-B enforcement succeeded. Further runtime verification is
deferred; the next recording step can show the CLI itself without starting runs.

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

## Record the official CLI command

Use authenticated `gh` with the official
[github/gh-actions-lock](https://github.com/github/gh-actions-lock) extension.
If the extension is missing, install it with
`gh extension install github/gh-actions-lock`.

When ready to record manually:

```sh
gh actions-lock --help
cat .github/workflows/actions.lock
gh actions-lock --no-narrow --no-interactive
git diff -- .github/workflows
```

The command has already been used for this repository. With an existing
lockfile this is a maintenance run, not first-time onboarding, and it may
produce no diff. A visual recording is a separate manual step; it does not
authorize changing the preserved snapshot or publishing any resulting changes.
Do not use `--relock`, `--accept-moved`, or delete the lock to manufacture a diff.

**Show:** the exact command, existing native lockfile, recorded A identity, and
actual CLI output. Explain that `--no-narrow` preserves the literal `@v3`;
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
actual `demo-revision` output, and bot reply. Expected and actual values must
remain separate. With the currently unresolved locking behavior, a new comment
may execute B and fail the workflow's expected-A check; do not hide that failure.

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

### 4. Establish external reachability in log mode

This is independent of the locking comparison and has not been recorded.
Keep the committed policy in `log` mode on the explicitly selected ref.
The dispatch workflow must also exist on the default branch.

```sh
python3 scripts/rehearse.py dispatch --ref main --expectation reachable
# Only after approval:
python3 scripts/rehearse.py dispatch --ref main --expectation reachable --apply \
  > .demo-evidence/log-probe.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/log-probe.json
```

**Expected:** the bounded, credential-free `GET https://example.com/` returns
curl exit 0 and a 2xx status. **Evidence:** selected ref/SHA, committed policy,
request timestamp/result, and that run's native traffic record.
The `expectation` input labels the check; it does not select the policy mode.
A log-mode proxy failure, DNS error, or missing runner is a failed baseline,
not proof of enforcement.

### 5. Enforce and correlate a deny (not performed)

Only after a successful log baseline and separate approval, change the committed
policy to `mode: enforce`. Keep `api.github.com` allowed and `example.com`
outside the additive allowlist. Review real traffic before adding necessary
hosts; do not disable platform defaults or broaden permissions to force success.

```sh
# Only after the reviewed enforce policy is published on this ref:
python3 scripts/rehearse.py dispatch --ref main --expectation denied --apply \
  > .demo-evidence/enforce-probe.json
python3 scripts/rehearse.py evidence --receipt .demo-evidence/enforce-probe.json
# Use the exact run ID and an actual artifact name from its metadata:
gh run download "$RUN_ID" --repo Steve-Glass/pr-note-consumer \
  --name "$ARTIFACT_NAME" --dir ".demo-evidence/$RUN_ID/firewall"
```

**Required evidence:** the same run's native deny event for `curl` and
`https://example.com/`, its rule, and matching request time/ref/policy SHA.
Read the actual artifact schema; do not assume its name or fields.
The probe should remain visibly failed. A random network error is not proof,
and unexpected success explicitly fails the containment check.

Policy is read from the workflow's ref. Editing `main` does not change a
dispatch from another branch. Any repeat or return to log mode requires a
reviewed policy state and separate approval.

### 6. Legitimate commenting under enforcement (not performed)

After a future enforce-mode checkpoint, a separately approved new comment should
still receive the exact thank-you reply with only `pull-requests: write`.
Capture the real Action SHA/output, reply, committed policy, and native traffic
evidence. Any A-identity claim also depends on resolving the open locking issue.
Do not refresh pins or weaken unrelated protections to make the run green.

Firewall artifacts are not Policy insights; Policy insights concerns workflow
execution protections. Preview documentation access or repository admin
permission does not prove native runtime availability. Report actual errors
and use the open issue to resolve the locking mismatch without altering the
preserved reproduction.
