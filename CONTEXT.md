# Domain

Account: a balance in one currency. Cash/card are liquid; investment is an asset; debt_lent is receivable; debt_borrowed is liability.
Operation: one atomic change with signed account movements. Opening balances and principal transfers are not income/expense.
Amount: integer hundredths of UZS or USD. Valuation: dated estimate, never a cash movement or automatically recognized profit.
Draft: persistent incomplete operation with no balance effect. Cancellation: audited invalidation with balance recalculation, never erasure of raw messages.

Reserve: an account purpose flag on cash/card, included in net worth but excluded from daily spendable funds. Funds are released by transfer. Split expense: one expense total with same-currency allocations and atomic signed movements. AI archive: full financial history with scoped period summary, not a raw transport/secrets dump.
