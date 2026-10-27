# Domain

Account: a balance in one currency. Cash/card are liquid; investment is an asset; debt_lent is receivable; debt_borrowed is liability.
Operation: one atomic change with signed account movements. Opening balances and principal transfers are not income/expense.
Amount: integer hundredths of UZS or USD. Valuation: dated estimate, never a cash movement or automatically recognized profit.
Draft: persistent incomplete operation with no balance effect. Cancellation: audited invalidation with balance recalculation, never erasure of raw messages.
