# Expense date selection

Undated expense input previously inherited today's date and bypassed the existing date picker. The draft now distinguishes an explicit/selected date from an inferred default. Undated expenses require Today / Yesterday / Other date, including generic operation entry and resumed legacy drafts. Explicit textual dates remain fast and editable.

Revision-bound Change date buttons preserve amount, category, accounts and split allocations. Custom date input accepts ISO or DD.MM.YYYY, survives restart, and refuses future dates. Relative buttons also display the absolute date so older messages are unambiguous. Existing recorded transactions and the database schema do not change.

Validation: targeted screenshot reproduction, custom date/restart, stale account buttons, future-date retry and legacy confirmation tests; existing wizard/dedup tests updated to select the newly required date. Full suite: 69 passing tests.
