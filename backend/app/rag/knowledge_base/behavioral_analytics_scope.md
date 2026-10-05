# Behavioral Analytics Scope

QuantumFinGuard computes per-user and per-merchant behavioral baselines
(mean/standard deviation of transaction amount, minimum 20 historical
transactions required) from the IBM Credit Card Transactions dataset,
and flags transactions that deviate more than 2.5 standard deviations
from a customer's or merchant's own baseline as statistically unusual.

## Important: unusual is not the same as fraudulent

A large deviation from baseline is contextual evidence, not a fraud
determination. The system deliberately reports "is_unusual: true/false"
as a separate signal alongside — never merged into — the fraud/risk
score.

## Important limitation: dataset linkage

**Behavioral context only applies to transactions sourced from the IBM
Credit Card Transactions dataset** (`customer_id` starting with
`ibm_user_`). IEEE-CIS and IBM Credit Card Transactions are separate
Kaggle datasets with unrelated synthetic identifier spaces — there is
no real-world correspondence between an IEEE-CIS `card1`-derived
customer ID and an IBM `User` index. Behavioral analytics is therefore
NOT available for IEEE-CIS-sourced transactions; requesting it for one
returns an explicit "not from the IBM dataset" explanation rather than
a fabricated or incorrectly-linked baseline.

This is a deliberate design choice consistent with the project's
principle of keeping the three source datasets integrated at the
intelligence layer, not blindly merged.
