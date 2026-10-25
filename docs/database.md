# Database design

Database: `fintwin_ai` (configurable via `DATABASE_NAME`). User ids are stored as strings of the user's ObjectId. Dates are naive UTC/local-midnight `datetime` values.

## users

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `full_name` | string | 2–80 chars |
| `email` | string | lower-case, **unique index** |
| `password_hash` | string | bcrypt; never leaves the auth layer |
| `created_at`, `last_login_at` | datetime | |

## transactions

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | exposed as `id` |
| `user_id` | string | owner |
| `date` | datetime | |
| `category` | string | Salary, Food, Shopping, Transport, Bills, Entertainment, Investment, Healthcare, Education, Rent, Travel, Insurance, Other |
| `transaction_type` | string | Income, Expense, Investment |
| `amount` | double | > 0, ≤ ₹100 crore |
| `description` | string | sanitised, ≤ 200 chars |
| `source` | string | manual, statement, demo |
| `created_at`, `updated_at` | datetime | |

Indexes: `(user_id, date desc)`, `(user_id, category)`.

## budgets

`user_id`, `category` (expense categories only), `monthly_limit`, timestamps. **Unique index** `(user_id, category)`; saving is an upsert.

## financial_profiles

One per user (**unique** `user_id`): `emergency_fund`, `monthly_debt_payment` (both optional; `null` means "not provided"), `expected_annual_return`, `risk_profile`, `goals` (array of `{name, target_amount, target_years}`), `updated_at`.

## predictions

`user_id`, `kind` (`spending`, `cashflow`, `anomaly_scan`), `payload`, `created_at`. Index `(user_id, kind, created_at desc)`. Only the 20 most recent per kind are kept.

## fraud_alerts

`user_id`, `transaction_id`, `date`, `description`, `category`, `amount`, `label`, `score`, `reasons[]`, `status` (`open`, `reviewed`, `dismissed`), timestamps. **Unique** `(user_id, transaction_id)` so rescans update rather than duplicate; reviewed and dismissed alerts keep their status.

## ai_conversations

`user_id`, `role` (`user`/`assistant`), `content`, `meta` (`source`, `intent`), `created_at`. Index `(user_id, created_at)`.

## reports

`user_id`, `period`, `summary` (income, expenses, savings, health score), `created_at`. Index `(user_id, created_at desc)`.

## Data isolation

Every repository function takes `user_id` and includes it in the filter, including updates and deletes (`{"_id": oid, "user_id": user_id}`), so a user can never read or modify another user's records even with a valid document id. This is covered by `tests/test_database.py`.
