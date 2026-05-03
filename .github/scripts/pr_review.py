#!/usr/bin/env python3
"""
Kiri PR Review Agent.

Called by .github/workflows/pr-review.yml.
Reads the PR diff, calls Claude, posts a structured review comment.

Required env vars:
  ANTHROPIC_API_KEY
  GH_TOKEN
  PR_NUMBER
  PR_TITLE
  PR_BODY          (may be empty)
  GITHUB_REPOSITORY  (set automatically by GitHub Actions)
"""
import json
import os
import subprocess
import sys
import tempfile

import anthropic

SYSTEM_PROMPT = """\
You are a senior code reviewer for Kiri, an open-source on-premises LLM proxy.
Kiri intercepts LLM calls (Claude Code, Cursor, Copilot) and prevents proprietary source code from leaving the network.

Your task: review the pull request diff for correctness, security, and adherence to the project's architecture.

## Critical invariants — BLOCK the PR if any are violated
1. Fail-open on L1/L3 errors: filter errors must result in PASS, never BLOCK (ADR-004).
2. L2 symbol matching must always be active and must never fail silently.
3. `kiri serve` must bind to 127.0.0.1 — never to 0.0.0.0 (REQ-S-005).
4. The indexer stores float vectors only — never source text (REQ-NF-005).

## Review checklist (flag issues in Findings)
- Tests: new/changed behaviour covered by tests?
- Branch convention: `feat/`, `fix/`, `sec/`, or `docs/` prefix?
- ADR: if architecture changed, is an ADR referenced or updated?
- Requirements: relevant REQ-F-NNN IDs mentioned?
- Security: injection, path traversal, binding to 0.0.0.0, logging of secrets?

## Strict output format — no preamble, no trailing text
**Status**: PASS | NEEDS WORK | BLOCK

**Summary**: One concise sentence describing what this PR does and your verdict.

**Findings**:
- <finding or "None">

**Invariant check**: All clear | <invariant name and how it is violated>

**Suggested action**: What the author should do next, or "Ready to merge" if PASS.
"""


def read_file_capped(path: str, max_chars: int = 3000) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read(max_chars)


def post_comment(pr_number: str, body: str) -> None:
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    # Look for an existing agent comment to update instead of spamming
    result = subprocess.run(
        [
            "gh", "api",
            f"repos/{repo}/issues/{pr_number}/comments",
            "--jq", '.[] | select(.body | contains("kiri-agent:pr-review")) | .id',
        ],
        capture_output=True,
        text=True,
    )
    existing_id = result.stdout.strip()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"body": body}, f)
        json_file = f.name

    try:
        if existing_id:
            subprocess.run(
                [
                    "gh", "api",
                    f"repos/{repo}/issues/comments/{existing_id}",
                    "--method", "PATCH",
                    "--input", json_file,
                ],
                check=True,
            )
        else:
            subprocess.run(
                ["gh", "pr", "comment", pr_number, "--body-file", json_file.replace(".json", ".md")],
                check=True,
            )
            # gh pr comment doesn't support --body-file with JSON, use --body
            raise RuntimeError("fallback")
    except Exception:
        # Fallback: direct body argument
        subprocess.run(
            ["gh", "pr", "comment", pr_number, "--body", body],
            check=True,
        )
    finally:
        os.unlink(json_file)


def main() -> None:
    pr_number = os.environ["PR_NUMBER"]
    pr_title = os.environ.get("PR_TITLE", "(no title)")
    pr_body = os.environ.get("PR_BODY", "")

    with open("pr_diff.txt", encoding="utf-8", errors="replace") as f:
        diff = f.read()

    truncation_notice = ""
    max_diff_chars = 80_000
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars]
        truncation_notice = (
            "\n\n> ⚠️ Diff truncated at 80 000 characters — large PR, review may be incomplete."
        )

    context = ""
    for path in ("CLAUDE.md", "DECISIONS.md"):
        chunk = read_file_capped(path)
        if chunk:
            context += f"\n\n### {path}\n{chunk}"

    user_message = f"""\
Review PR #{pr_number} for the Kiri project.

**Title**: {pr_title}

**Description**:
{pr_body or "(no description provided)"}

**Diff**:
```diff
{diff}
```{truncation_notice}

---
**Project context excerpts**:
{context or "(not available)"}
"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    review_text = response.content[0].text

    comment_body = f"""\
<!-- kiri-agent:pr-review -->
## Kiri Agent — PR Review

{review_text}

---
*Automated review · [pr-review.yml](.github/workflows/pr-review.yml) · `claude-sonnet-4-6`*
"""

    post_comment(pr_number, comment_body)
    print(f"Review posted for PR #{pr_number}.")

    if "**Status**: BLOCK" in review_text:
        print("::error::PR review agent issued a BLOCK — invariant violation detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
