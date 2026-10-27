# Reserves, split expenses and complete AI exports

Accepted owner requests: reserve marking for emergency UZS/USD cash, detailed all-history financial exports for manual AI review, and one expense paid from several accounts.

- Schema v2 adds a reserve flag, preserving existing records with default ordinary purpose. Reserves count in net worth but not daily spendable funds. Transfer before spending. Metadata-only corrections to existing transactions remain possible after marking an account reserve, including secondary split legs; new reserve spending remains blocked.
- One split expense has one amount/category and positive same-currency allocations summing exactly to the total. Account debits, cancellation and replacement are atomic. Source message links and incomplete split state survive restart.
- One SQLite snapshot supplies Excel, complete prompt/text records, canonical JSON and a SHA-256/count manifest. The requested-period summary is separate from full history and current balances. All 10 financial tables are covered; technical transport/runtime tables are excluded. Long Excel cells point to lossless TXT/JSON. Numbered parts preserve all rows.

Validation: 64 tests and Ruff pass. A read-only production backup was restored privately, migrated, compared against every existing financial record, and exported; source and archive table counts and file hashes matched. Fresh code review found a reserve-history edit issue; regression tests reproduced and verified the fix. Container tests are repeated on the final release before deploy.

No personal amounts are invented. The owner creates UZS/USD reserve accounts with actual balances in onboarding, or marks an existing liquid account. Private verification artifacts stay outside the repository.
