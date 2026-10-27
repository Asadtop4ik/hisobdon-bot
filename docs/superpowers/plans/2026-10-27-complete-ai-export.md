# Complete financial AI export

The owner requests a complete, detailed financial database view for manual AI analysis. Every export will contain a scoped period summary plus a clearly distinguished complete financial archive, all produced from one SQLite snapshot.

- Include accounts/openings, all operation versions/statuses and signed movements, all valuations/rates, categories/aliases, all source messages, drafts and audit history. Exclude transport queues, delivery state, secret/runtime settings and Telegram routing identifiers.
- Provide Excel, a ready-to-use Uzbek prompt plus full text records, canonical JSON, and a manifest with row counts and hashes. Financial IDs remain for joins. Document integer money units, cancelled records, reserve purpose, principal transfers, valuation and date semantics.
- Clearly separate requested-period figures, period-end balances, and current balances. Include monthly recorded cashflow and explicit completeness limitations; never invent missing history.
- Large data splits into numbered parts with complete row coverage. JSON/TXT remain lossless where Excel cell size is limited.
- Add end-to-end export tests with old/out-of-period/cancelled records, movements, valuation history, drafts, aliases, formula-like text, file hashes and forced chunking. Inspect an isolated production snapshot without printing private contents.
- Reserve account behavior is being clarified separately. Do not insert approximate balances or create personal accounts without their actual opening values.

## Accepted additions

The owner selected reserve marking. Add `accounts.is_reserve` through an additive v1→v2 migration; existing accounts default to ordinary. Reserve counts toward net worth but not daily spendable funds; release it through transfer/exchange before use. Never create real reserve accounts or invent opening amounts. New reserve creation and existing-account marking are available in Telegram.

The owner also requested split expense payment: e.g. 60,000 UZS total, 17,000 cash and 43,000 card. Store one expense with same-currency positive allocations summing exactly to its amount. Signed movements debit each ordinary account atomically. Report the expense once; edit/cancel restores every allocation. Wizard state and source-message links persist across restart.
