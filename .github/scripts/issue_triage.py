#!/usr/bin/env python3
"""
Kiri Issue Triage Agent.

Called by .github/workflows/issue-triage.yml.
Reads a newly opened issue, calls Claude, posts a triage comment and applies labels.

Required env vars:
  ANTHROPIC_API_KEY
  GH_TOKEN
  ISSUE_NUMBER
  ISSUE_TITLE
  ISSUE_BODY        (may be empty)
  ISSUE_LABELS      (comma-separated, may be empty)
  GITHUB_REPOSITORY (set automatically by GitHub Actions)
"""
import os
import subprocess

import anthropic

SYSTEM_PROMPT = """\
You are an issue triage agent for Kiri, an open-source on-premises LLM proxy.
Kiri intercepts LLM calls (Claude Code, Cursor, Copilot) and prevents proprietary code from leaving the network.

The project tracks requirements with IDs like REQ-F-NNN (functional), REQ-S-NNN (security), REQ-NF-NNN (non-functional).
User stories are US-01 through US-13.
Architecture decisions are in ADR-001 through ADR-NNN (docs/adr/).

Key components:
- Filter pipeline: L1 (regex), L2 (symbol matching, always active), L3 (semantic/embedding)
- Proxy: intercepts HTTP calls from Claude Code, Cursor, Copilot
- Indexer/embedder: builds vector index of the codebase (stores float vectors only, never source text)
- CLI: `kiri serve`, `kiri add`, `kiri rm`, `kiri status`, `kiri inspect`

Critical invariants (anything that threatens these is HIGH priority):
- Fail-open on L1/L3 errors (ADR-004)
- kiri serve must bind to 127.0.0.1, never 0.0.0.0 (REQ-S-005)
- Indexer must not store source text (REQ-NF-005)

Your task: analyse this GitHub issue and produce:
1. A triage comment for the author
2. Labels to apply (choose from: bug, enhancement, question, security, priority:high, priority:medium, priority:low, needs-info)

## Strict output format

COMMENT:
<the markdown comment to post, addressed to the issue author — acknowledge the report, summarise your reading, link related requirements/ADRs if applicable, state next steps, ask for missing info if needed>

LABELS:
<comma-separated list of labels from the allowed set above>

Rules:
- Security issues that could affect the critical invariants → security + priority:high
- Bugs with reproduction steps → bug + appropriate priority
- Feature requests → enhancement + priority:medium (default)
- Add needs-info if the report lacks information needed to act on it
- Be concise and professional. Do not promise timelines.
"""


def main() -> None:
    issue_number = os.environ["ISSUE_NUMBER"]
    issue_title = os.environ.get("ISSUE_TITLE", "(no title)")
    issue_body = os.environ.get("ISSUE_BODY", "")
    existing_labels = os.environ.get("ISSUE_LABELS", "")

    user_message = f"""\
New issue #{issue_number} opened in the Kiri project.

**Title**: {issue_title}

**Body**:
{issue_body or "(no body provided)"}

**Labels already applied**: {existing_labels or "none"}

Triage this issue.
"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    output = response.content[0].text

    # Parse agent output
    comment_text = ""
    labels_text = ""

    if "COMMENT:" in output and "LABELS:" in output:
        parts = output.split("LABELS:", 1)
        comment_text = parts[0].replace("COMMENT:", "", 1).strip()
        labels_text = parts[1].strip()
    else:
        # Fallback: use entire output as comment
        comment_text = output
        labels_text = "triage"

    comment_body = f"""\
<!-- kiri-agent:issue-triage -->
## Kiri Agent — Issue Triage

{comment_text}

---
*Automated triage · [issue-triage.yml](.github/workflows/issue-triage.yml) · `claude-sonnet-4-6`*
"""

    # Post comment
    subprocess.run(
        ["gh", "issue", "comment", issue_number, "--body", comment_body],
        check=True,
    )
    print(f"Triage comment posted for issue #{issue_number}.")

    # Apply labels
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    allowed = {
        "bug", "enhancement", "question", "security",
        "triage", "priority:high", "priority:medium", "priority:low", "needs-info",
    }
    labels = [l.strip() for l in labels_text.split(",") if l.strip() in allowed]
    # Always remove generic "triage" label once the agent has processed it
    labels_to_remove = ["triage"]

    if labels:
        subprocess.run(
            ["gh", "issue", "edit", issue_number, "--add-label", ",".join(labels)],
            check=True,
        )
        print(f"Labels applied: {labels}")

    for label in labels_to_remove:
        subprocess.run(
            ["gh", "issue", "edit", issue_number, "--remove-label", label],
            capture_output=True,  # don't fail if label isn't present
        )


if __name__ == "__main__":
    main()
