# Debt repayment interface fix

Debt repayment already had atomic ledger support but was hidden behind the generic operation menu. The debt detail now offers partial/full repayment and the liquid account choice. Income/expense category selectors also allow switching to principal repayment while preserving the entered amount and source message.

Zero-balance debts are shown in a separate closed list, with history intact. Closure is derived from the ledger, so cancelling a repayment reopens the debt. Existing database schema and balances are unchanged by deployment.

Validation: synthetic conversation tests cover partial receipt to card, remaining receipt to cash, closing/reopening, outgoing borrowed principal, the reported income-category screen, and stale full-payment confirmation. Full suite: 53 tests. Independent review also identified and tests verified correction of full repayments: changing the payment account preserves the debt target, and editing the amount restores the original repayment contribution when calculating the full amount.
