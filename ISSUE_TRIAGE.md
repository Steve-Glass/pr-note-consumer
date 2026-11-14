# Issue triage example

This small [GitHub Agentic Workflow](https://github.com/github/gh-aw) runs when
an issue is **opened**. Copilot reads it and requests one existing label:
`bug`, `enhancement`, or `documentation`. No schedule, backfill, dispatch,
comment, memory, or report issue is configured.

## Setup and demo

**Live inference is not ready:** this is a personal public repository, and no
Actions secrets were present when this example was prepared. Current
[authentication documentation](https://github.github.com/gh-aw/reference/auth/#copilot_github_token)
requires `COPILOT_GITHUB_TOKEN` for personal repositories: a fine-grained PAT
owned by a licensed Copilot user, with account permission **Copilot Requests:
Read**. The organization-billed `copilot-requests: write` Actions-token path
requires an organization subscription and centralized billing; it is not a
verified substitute here. This change creates no PAT/secret and changes no
billing, ownership, or repository settings. Credential setup requires separate
operator authorization before a live demo.

After authorized authentication setup and review/merge onto `main`, a maintainer
can open an issue titled **README is missing setup instructions**, with a body
such as "Please document the prerequisites and local setup commands." Watch
**Actions > Issue triage** and inspect the safe-output result and the issue's
`documentation` label. Opening this PR does not activate or run the example.
No issue or live workflow run was created to validate this change.

## Enforced boundaries

The compiled agent has only `contents: read` and `issues: read`. Its sole GitHub
MCP tool is `issue_read`, restricted to this repository with `approved` integrity.
The default activation gate requires `admin`, `maintainer`, or `write` access;
owner/maintainer-authored issues satisfy the integrity policy. This intentionally
does **not** promise triage for arbitrary external issue authors. Protections
have not been weakened for the demo.

The label handler uses the repository's `GITHUB_TOKEN`, accepts only the three
named labels, permits one call with one label, targets the triggering issue,
and rejects missing labels rather than creating them. Default threat detection
is retained before safe-output processing. Automatic failure, missing-tool, and
incomplete-run issue creation are disabled; diagnostics remain in Actions.
The generated conclusion job still has `issues: write`, even with reporting
disabled. The engine step has a 10-minute/10-turn limit; the generated agent job
allows 60 minutes for setup/cleanup, detection allows 10, and safe outputs 15.
Three generated orchestration jobs omit explicit timeouts and use Actions
defaults; the static checker flags this.

Choosing the right category, reading only the current issue (the read tool can
also address other issues in this repository), preserving existing labels, and
using `noop` for ambiguous/already-classified issues are agent instructions,
not deterministic classification guarantees. The compiler enables local
shell/file tools for its runtime; repository write permissions are not granted
to the agent. Network access uses gh-aw's `defaults` and `github` presets.

## Editing and validation

Edit `.github/workflows/issue-triage.md`, then compile with **gh-aw v1.2.2**:

```sh
gh aw version
gh aw compile issue-triage --validate --no-check-update
.demo-evidence/venv/bin/python -m unittest discover -s tests -p 'test_issue_triage.py' -v
```

Use the README's Python environment setup if needed. Commit the generated
`.lock.yml`, `.github/aw/actions-lock.json` compiler pin cache, and
`.gitattributes` generated-file marker. Never hand-edit the compiled YAML.
The native `.github/workflows/actions.lock` is a **separate** dependency-lock
format: it does not currently enroll this new workflow. It and the native
egress policy are preserved; SHA/digest pins in gh-aw output do not prove native
lock enrollment or live firewall compatibility. A future native-lock update
needs separate review without refreshing the recorded producer pin.

Compilation and focused configuration tests do not prove inference or labeling
works live. The Actions plugin's bounded ref check verifies gh-aw-actions
v1.2.2, but `actions/*` lookups were blocked by organization SAML authorization;
those refs remain unverified by that check. Its 30-occurrence cap also truncates
the generated workflow. Local actionlint/zizmor were unavailable; no runner,
container, or runtime enforcement success is claimed.
