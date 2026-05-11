# Security Audit — status

This file documents vulnerabilities found by an automated security audit and their current fix status. **Read this before forking.**

**Status as of 2026-05-11:** all **4 CRITICAL** and **7 HIGH** items fixed in code. Remaining MEDIUM/LOW listed at the bottom — review per your threat model.

Severity order: CRITICAL > HIGH > MEDIUM > LOW.

---

## 🔴 CRITICAL

### ✅ FIXED — 1. JWT secret silently falls back to `BOT_TOKEN`
- **Where:** `app/config.py:2321-2333` — `get_cabinet_jwt_secret()`
- **Why bad:** If `CABINET_JWT_SECRET` is unset (only a non-fatal `warnings.warn`), cabinet JWTs are signed with `BOT_TOKEN`. The bot token is shared with Telegram's API, often committed to `.env`, and probeable via `getMe`. Knowing it = forging admin JWTs.
- **Fix:** Require `CABINET_JWT_SECRET` in production:
  ```python
  if not self.CABINET_JWT_SECRET:
      raise RuntimeError("CABINET_JWT_SECRET must be set")
  ```

### ✅ FIXED — 2. Telegram Stars payment is NOT idempotent — double credit on retry
- **Where:** `app/services/payment/stars.py:78-141`, `app/handlers/stars_payments.py:255-261`
- **Why bad:** No de-dupe on `telegram_payment_charge_id` before crediting. Telegram retries `successful_payment` on bot 5xx/timeout — second call credits balance again.
- **Fix:** `SELECT … FOR UPDATE` (or unique index) on `transactions(external_id, payment_method=TELEGRAM_STARS)` and short-circuit on existing completed row. Mirror the lock pattern in `cloudpayments.py:205-214`.

### ✅ FIXED — 3. Tribute webhook: identity confusion + double bookkeeping
- **Where:** `app/handlers/webhooks.py:25-86`, `app/external/tribute.py:36-149`, `app/services/payment/tribute.py:47-64`
- **Why bad:** (a) Calls `get_user_by_id(processed_data['user_id'])` but `user_id` in payload is actually `telegram_id` → wrong user credited. (b) Calls both `add_user_balance(...)` AND `create_transaction(...)` → two transaction rows. (c) `payment_id` falls back to forgeable `f'tribute_{telegram_user_id}_{amount_kopeks}'`. (d) Hardcoded placeholder URL `https://tribute.ru/pay?...`.
- **Fix:** Look up by `get_user_by_telegram_id`. Drop double bookkeeping. Require provider-issued `payment_id` and enforce uniqueness. Replace placeholder URL.

### ✅ FIXED — 4. Single-use promocode can be over-redeemed under concurrency
- **Where:** `app/services/promocode_service.py:185-192`, `app/database/crud/promocode.py:94-112`
- **Why bad:** Increment is `UPDATE … SET current_uses = current_uses + 1` with no `WHERE current_uses < max_uses`. Validity check is TOCTOU. N concurrent users of a 1-use code all succeed.
- **Fix:** Atomic conditional update + rollback if rowcount = 0:
  ```python
  result = await db.execute(
      update(PromoCode).where(PromoCode.id == pid, PromoCode.current_uses < PromoCode.max_uses)
      .values(current_uses=PromoCode.current_uses + 1)
  )
  if result.rowcount == 0:
      raise PromoCodeExhausted()
  ```

---

## 🟠 HIGH

### ✅ FIXED — 5. YooKassa webhook does not verify signature
- **Where:** `app/external/yookassa_webhook.py:246-248`, `app/webserver/payments.py:426-428`
- **Why bad:** `Signature` header is read but only logged. Defence is only `YOOKASSA_ALLOWED_IP_NETWORKS`. One misconfigured nginx (`X-Forwarded-For` from untrusted proxies) = arbitrary balance top-ups.
- **Fix:** Implement YooKassa Webhook v2 HMAC verification. Treat IP allowlist as defence-in-depth.

### ✅ FIXED — 6. CORS wildcard + bearer auth
- **Where:** `app/webapi/app.py:178-185`, `app/webserver/unified_app.py:69-77`
- **Why bad:** `allow_origins=["*"]` with `Authorization` header allowed. `allow_credentials=False` doesn't help when the API uses bearer tokens stored in localStorage.
- **Fix:** Refuse to start with wildcard origins in production. Require explicit allow-list.

### ✅ FIXED — 7. Webhook signatures logged in plain text
- **Where:** `app/external/yookassa_webhook.py:248`, `app/webserver/payments.py:428`
- **Why bad:** `logger.info(..., signature=signature)` writes attacker-supplied (or genuine) HMACs to logs that often ship to third parties.
- **Fix:** Log only `signature_present=True/False`.

### ✅ FIXED — 8. Webhook replay protection (yookassa/cloudpayments/cryptobot)
- **Where:** all `app/services/payment/*.py`, `app/handlers/webhooks.py`
- **Why bad:** Idempotency on `external_id` blocks duplicate credits for the *same* payment, but doesn't stop replay of an old webhook against a new session if the local payment row was deleted/reset, or via metadata manipulation in restore-missing paths.
- **Fix:** Reject events older than 5 min and persist `event_id` with a unique index per provider that supports it.

### ✅ FIXED — 9. Restore-missing-payment paths feature-flagged + capped
- **Where:** `app/services/payment/cloudpayments.py:168-200`, `app/services/payment/yookassa.py:1130-1240`
- **Why bad:** When webhook arrives for an unknown invoice, code creates a new local payment from body's `amount` and `user_id`. Combined with leaked signing key (test/prod sharing, employee, third-party processor breach) = forge any amount to any user.
- **Fix:** Refuse the restore path, or restrict to amounts validated against a server-side allowlist.

### ✅ FIXED — 10. CryptoBot USD→RUB float math + 1:1 fallback (now Decimal + reject on rate failure)
- **Where:** `app/services/payment/cryptobot.py:247-269`, `app/utils/currency_converter.py:44-46,110-118`
- **Why bad:** All three rate sources fail → fallback `amount_rubles = amount_usd` (1:1). $100 USDT becomes ₽100 (~100× under-credit). Conversely, hardcoded fallback rate `95.0` over-credits when real rate spikes.
- **Fix:** On rate-fetch failure, REJECT the credit and queue manual review.

### ✅ FIXED — 11. Float arithmetic on money (Decimal throughout)
- **Where:** `app/services/payment/cloudpayments.py:145` (`int(round(amount * 100))`), `app/utils/currency_converter.py` (entire module), `app/services/payment/cryptobot.py:71,253,268`
- **Why bad:** JSON-parsed floats + `* 100` + `round()` can flip kopeks. Cumulative drift across many payments = real money.
- **Fix:** Use `Decimal(str(amount)) * 100` like `yookassa.py:1251` already does.

---

## 🟡 MEDIUM

### ✅ FIXED — 12. `BOT_TOKEN` format validator
- **Where:** `app/config.py:24`
- **Why bad:** Empty/whitespace `BOT_TOKEN` silently accepted; combined with the JWT-secret fallback (CRITICAL #1), empty token = predictable JWT signing key.
- **Fix:** `@field_validator('BOT_TOKEN')` enforcing `\d+:[A-Za-z0-9_-]{30,}`.

### 13. CryptoBot signature verifier accepts 3 canonicalizations
- **Where:** `app/external/cryptobot.py:135-151`
- **Why bad:** Tries "expected", "reserialized", "ascii" forms. Multiple acceptable forms widens the attack surface.
- **Fix:** Accept only the official CryptoBot canonical form.

### 14. Referral commission credited OUTSIDE the main payment transaction
- **Where:** `process_referral_topup` called after `db.commit()` in `cryptobot.py:336`, `yookassa.py:717`, `stars.py:262`, `cloudpayments.py:350`
- **Why bad:** If the referral commit fails (DB blip), the payer was credited but the referrer wasn't. No outbox/retry queue.
- **Fix:** Move referral crediting into the same transaction OR add a durable outbox.

### 15. Withdrawal transaction sign convention is brittle
- **Where:** `app/services/referral_withdrawal_service.py:479-526`
- **Why bad:** Writes negative `amount_kopeks=-request.amount_kopeks`. Callers must remember to `abs()`. Anywhere downstream that `SUM`s without `abs()` will double-count negatives.
- **Fix:** Use a separate `direction` column or always-positive amounts.

### 16. Promocode `balance_bonus_kopeks` unbounded; reused for multiple purposes
- **Where:** `app/services/promocode_service.py:258,285-289`, `app/database/crud/promocode.py:54-84`
- **Why bad:** Same column means kopeks (BALANCE), percent (DISCOUNT), days (SUBSCRIPTION_DAYS). No upper bound at create. Compromised admin token ⇒ mint a ₽10B promocode. No validation that DISCOUNT ≤ 100.
- **Fix:** Split into separate columns and add explicit `Decimal` bounds.

### 17. NaloGO receipt amount = requested, not captured
- **Where:** `app/services/payment/yookassa.py:1003-1018`
- **Why bad:** Receipt sent to nalog.ru uses `payment.amount_kopeks` (requested) instead of the captured amount from the webhook. Mismatch with actual received funds = tax liability problem.
- **Fix:** Read captured amount from the merged webhook payload.

### 18. No refund webhook handling — refunds leak platform funds
- **Where:** No `refund` event handler anywhere
- **Why bad:** User disputes/refunds via provider → balance they spent stays gone for the platform; provider claws back funds from you.
- **Fix:** Implement refund/chargeback routes per provider that debit balance (or mark as debt) and freeze service.

### 19. No `TrustedHostMiddleware` on cabinet/webapi
- **Where:** `app/webapi/app.py`, `app/cabinet/routes/__init__.py:73`
- **Fix:** `TrustedHostMiddleware(allowed_hosts=settings.ALLOWED_HOSTS)`.

---

## 🟢 LOW

### 20. Throttling default 0.5s is generic
- **Where:** `app/middlewares/throttling.py:27`
- **Fix:** Tighter limits on `auth`, `promocode/redeem`, `referral/claim`, `payment/create` — both bot handlers and cabinet routes.

### 21. Stars `pre_checkout_query` doesn't verify `total_amount` matches payload
- **Where:** `app/handlers/stars_payments.py:130-192`

### 22. Stars `process_stars_payment` payload trusts `subscription_id` and `period_days`
- **Where:** `app/services/payment/stars.py:143-191`

### 23. `# TODO: post-payment business logic` placement is inconsistent
- **Where:** `stars.py:204` (BEFORE balance credit, outside transaction), `yookassa.py:652` (inside locked block), `cryptobot.py:22-23` (module-level stub)
- **Why bad:** Forks plug logic at TODO; placement determines whether it runs in the same DB transaction as the credit. Inconsistency = forks will get it wrong.
- **Fix:** Document the hook contract explicitly and standardize placement.

### 24. Currency converter Fixer URL contains literal `YOUR_API_KEY`
- **Where:** `app/utils/currency_converter.py:95-105` — silently never works.

---

## ✅ Verified safe

- All admin Telegram handlers use `@admin_required`.
- All cabinet admin routes use `Depends(require_permission)` (RBAC).
- All webapi routes use `Depends(require_api_token)`.
- No raw SQL string concatenation (`text(f"…")`) in CRUD/services/routes.
- Telegram WebApp `initData` validation: HMAC-SHA256, `WebAppData` secret, sorted params, `hmac.compare_digest`, 300s `auth_date` clock-skew check.
- Telegram OIDC via JWKS RS256 with audience+issuer+required-claims.
- Most payment webhooks DO verify signatures: Tribute (raw body), CryptoBot, WATA (RSA-PSS SHA-512), Heleket, MulenPay, CloudPayments (4 endpoints), Pal24, Platega.
- Concurrency for balance writes uses `SELECT … FOR UPDATE` in withdrawal/partner-app paths and per-provider CRUDs.
- CSRF state implemented for OAuth (Redis one-shot tokens).
- File-upload paths enforce `_SAFE_FILENAME_RE` (UUID-hex). Backup paths use `.resolve()`.
- No HTML templates rendered with user data (cabinet/webapi return JSON only).
- Webhook IP resolution uses explicit trusted-proxy allow-list, not raw `X-Forwarded-For`.
- No open redirects beyond static target URLs.
- JWT type field checked (refresh-token-as-access-token confusion prevented).

---

## Priority queue for the maintainer

1. **CRITICAL #1** — make `CABINET_JWT_SECRET` mandatory.
2. **CRITICAL #2** — add `external_id` uniqueness check for Stars (`telegram_payment_charge_id`).
3. **CRITICAL #3** — rewrite Tribute webhook end-to-end.
4. **CRITICAL #4** — atomic `WHERE current_uses < max_uses` on promocode.
5. **HIGH #5** — implement YooKassa HMAC.
6. **HIGH #6** — forbid wildcard CORS in production.
7. **HIGH #7** — stop logging signature values.
8. **HIGH #8** — add webhook replay protection.
9. **HIGH #9** — restrict restore-missing-payment paths.
10. **HIGH #10/#11** — replace float money math with `Decimal`.

Until these are fixed, **do not deploy this boilerplate to production with real money flowing through it.**
