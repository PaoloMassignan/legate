# Kiri — Automated Agents

This document describes the automated agents that run on every pull request and issue in this repository.
All agents run on GitHub-hosted infrastructure (not locally) and use the Anthropic API.

---

## PR Review Agent

**Workflow**: [`.github/workflows/pr-review.yml`](.github/workflows/pr-review.yml)
**Script**: [`.github/scripts/pr_review.py`](.github/scripts/pr_review.py)
**Trigger**: Every PR opened, updated (new push), or reopened

### What it does
1. Fetches the full PR diff.
2. Reads `CLAUDE.md` and `DECISIONS.md` for project context.
3. Calls `claude-sonnet-4-6` with the diff and a system prompt that knows Kiri's architecture.
4. Posts (or updates) a structured review comment on the PR with one of three verdicts:

| Verdict | Meaning |
|---------|---------|
| **PASS** | No issues found. Ready for owner review. |
| **NEEDS WORK** | Minor issues — tests missing, naming convention, etc. |
| **BLOCK** | Critical invariant violated. Merge should not proceed. |

5. If the verdict is **BLOCK**, the workflow step exits with a non-zero code, marking the check as failed.

### What it checks
- All four [critical invariants](CLAUDE.md) (fail-open, L2 always active, bind to 127.0.0.1, vectors only)
- Test coverage for new/changed code
- Branch naming convention (`feat/`, `fix/`, `sec/`, `docs/`)
- ADR referenced if architecture changed
- Common security issues (injection, path traversal, credential logging)

### Limitations
- Diffs larger than 80 000 characters are truncated; the agent will note this.
- The agent does not run the test suite — that is CI's job (`ci.yml`).
- The agent's verdict is advisory for **PASS** and **NEEDS WORK**; only **BLOCK** fails the check.
  The owner ([@PaoloMassignan](https://github.com/PaoloMassignan)) must still approve before merge.

---

## Issue Triage Agent

**Workflow**: [`.github/workflows/issue-triage.yml`](.github/workflows/issue-triage.yml)
**Script**: [`.github/scripts/issue_triage.py`](.github/scripts/issue_triage.py)
**Trigger**: Every new issue opened

### What it does
1. Reads the issue title and body.
2. Calls `claude-sonnet-4-6` with the issue content and knowledge of Kiri's components and requirements.
3. Posts a triage comment that:
   - Acknowledges the report
   - Summarises the agent's reading of the issue
   - Links to relevant requirements (REQ-F-NNN) or ADRs if applicable
   - States next steps or asks for missing information
4. Applies labels from the allowed set: `bug`, `enhancement`, `question`, `security`, `priority:high`, `priority:medium`, `priority:low`, `needs-info`

### Security issues
Security vulnerabilities should be reported via [GitHub's private Security Advisory](../../security/advisories/new), not as public issues.
The issue templates enforce this with a banner and a redirect link.

---

## Merge policy

```
contributor opens PR
        ↓
CI (lint + type check + pytest)   ← must be green
        ↓
PR Review Agent posts verdict     ← BLOCK fails the check
        ↓
Owner (@PaoloMassignan) reviews   ← required approval (CODEOWNERS)
        ↓
merge into main
```

**No direct pushes to `main`.** Branch protection rules enforce this in GitHub Settings.

---

## Branch naming convention

| Prefix | Use for |
|--------|---------|
| `feat/US-XX-*` | New feature linked to a user story |
| `fix/REQ-*` or `fix/issue-NNN` | Bug fix |
| `sec/CVE-*` or `sec/advisory-*` | Security fix |
| `docs/*` | Documentation only |
| `chore/*` | Tooling, CI, dependencies |

---

## Secrets required

| Secret | Where to add | Purpose |
|--------|-------------|---------|
| `ANTHROPIC_API_KEY` | GitHub → Settings → Secrets → Actions | Anthropic API for all agents |

`GITHUB_TOKEN` is provided automatically by GitHub Actions.
