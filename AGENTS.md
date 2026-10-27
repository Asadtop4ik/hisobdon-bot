# Hisobdon

Single-owner Uzbek Telegram finance bot. Read the approved design in docs/superpowers/specs before changing money semantics.

Run `uv run ruff check .` and `uv run pytest -q` before delivery. Money is integer tiyin/cents. Never log or commit tokens, owner identifiers, raw finance messages, databases or backups. Test fixtures must be synthetic.

## Agent skills

Issue tracker: GitHub Issues in this repository. External PRs are not a request surface. See docs/agents/issue-tracker.md.
Triage labels: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix.
Domain docs: single context in CONTEXT.md and docs/adr/.
