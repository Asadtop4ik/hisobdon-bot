# V1 verification

Local full suite: 48 passing tests; Ruff check and format pass. Synthetic data only. Initial Linux container run passed all then-existing 41 tests; final release container is tested again before launch.

A fresh independent whole-branch review identified four material interactions. Regression tests now prove:

- Restoring only the database regenerates pending export/backup artifacts and subsequent commands proceed.
- Same-day loan principal revisions retain their original event order; genuinely overdrawn principal remains rejected.
- Backdated wizard and correction answers remain in the operation period's source-message export.
- Future and conflicting Uzbek date markers request clarification.

Owner requested daily encrypted backups in the private Telegram chat. Recovery key is stored separately. Actual deployment credentials and personal financial values are never in this repository.

Daily reports display actual generation time and scheduled time. Delayed generation reflects currently recorded information, and does not claim a snapshot captured while the bot was offline. Telegram acceptance followed by a connection loss can still cause duplicate delivery; financial postings are idempotent.
