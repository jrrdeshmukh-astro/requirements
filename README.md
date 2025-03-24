# 📄 Crypto Fund Manager – Technical Requirement Document (Non-Tokenized)

## 🧩 Overview

This is a web-based platform for managing a NAV-based crypto index fund. Users can invest and redeem using fiat, and the system handles asset allocation, rebalancing, NAV calculation, and user portfolio tracking. Fund logic is handled off-chain, with no tokenized units.

---

## 📦 Core Modules

### 1. 🔐 **User Authentication & Management**
- Simple JWT-based auth
- Email used as unique identifier
- Support for admin and user roles
- Optional: KYC status tracking (via Sumsub or Persona)

---

### 2. 💵 **Fiat Deposit (via Stripe Onramp)**
- Integrate Stripe Onramp for fiat → USDC (Polygon)
- Configure default deposit address (Fireblocks embedded user wallet or project wallet)
- Once funds arrive in treasury vault, trigger:
  - NAV fetch
  - Unit calculation
  - Ledger entry + allocation logic

---

### 3. 💸 **Fiat Withdrawal (Redemption via Transak)**
- Users initiate withdrawal in USD
- System burns units (calculated via latest NAV)
- Fireblocks sends USDC to a Transak-compatible wallet
- Transak off-ramps USDC to user's bank account
- Logs redemption with metadata (amount, fees, timestamps, Transak payout ID)

---

### 4. 📊 **NAV Calculation Engine**
- Fetch real-time prices from CoinGecko
- Sum Fireblocks vault balances (BTC_TEST, LTC_TEST)
- NAV = Total Asset Value / Total Units Issued
- Cronjob to log NAV daily to `nav_history`

---

### 5. 📈 **Investment Allocation Engine**
- Investments in USDC enter treasury vault
- Auto-split into assets using target weights
  - Example: 50% BTC_TEST, 50% LTC_TEST
- Fireblocks transfers from treasury → main vault
- Log to `investment_ledger` with per-asset breakdown

---

### 6. 🔁 **Rebalancing Logic**
- Check actual allocation vs. target allocation
- Trigger Fireblocks trades if deviation > 2%
- Logs all rebalancing activity and price data

---

### 7. 📋 **Admin Dashboard**
- View total AUM, user units, pending redemptions
- NAV charts
- CSV export for ledgers, NAV history, and users
- Manual override for:
  - NAV entries
  - Force rebalance
  - Treasury-to-main vault transfers

---

## 🧾 Database Tables

### `user_units`
| Field | Type | Description |
|--|--|--|
| email | string | Unique user identifier |
| units | float | Total units held |
| last_updated | timestamp | Timestamp of last update |

### `investment_ledger`
| Field | Type | Description |
|--|--|--|
| email | string | User email |
| amount_usd | float | Total invested in USD |
| asset_id | string | Asset (BTC_TEST, LTC_TEST) |
| asset_share | float | Allocation % |
| asset_value | float | Dollar value of allocation |
| units | float | Units credited |
| fireblocks_tx_id | string | Related Fireblocks transaction |
| timestamp | timestamp | When investment was logged |

### `investment_log`
| Field | Type | Description |
|--|--|--|
| email | string | User email |
| timestamp | timestamp | When investment occurred |
| amount_usd | float | Total amount invested |
| units | float | Units credited |
| nav | float | NAV at time of investment |
| fireblocks_tx_id | string | Transfer ID from Stripe/treasury |
| stripe_session_id | string | Original Stripe/Onramp session ID |
| status | string | pending / completed / failed |

### `nav_history`
| Field | Type | Description |
|--|--|--|
| date | date | Daily snapshot date |
| total_value | float | Total value of vault holdings |
| total_units | float | Sum of user units |
| nav | float | NAV value |

### `redemption_log`
| Field | Type | Description |
|--|--|--|
| email | string | User |
| amount_usd | float | Withdraw amount |
| units | float | Units burned |
| nav_used | float | NAV at time of redemption |
| fireblocks_tx_id | string | Transaction ID for transfer |
| transak_order_id | string | Transak order ID for off-ramp |
| status | string | pending / completed / failed |

---

## 📆 Cron Jobs
| Name | Frequency | Description |
|--|--|--|
| NAV Updater | Daily | Computes NAV and logs to DB |
| Rebalancer | Hourly | Checks and rebalances portfolio if needed |

---

## ✅ Recommended Enhancements
- User notifications (email or in-app)
- Admin approvals for large withdrawals
- Fee system (frontend + backend + accounting)
- Historical portfolio performance charts
