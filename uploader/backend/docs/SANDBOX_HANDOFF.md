# Glenn Daily Uploader — Sandbox Handoff

**Status:** Live and ready for Glenn's daily entry workflow (sandbox only).  
**Last verified:** 2026-07-10 — custom-domain smoke passed on Fly.io.

## Sandbox URL

**https://uploader-sandbox.hcresearch.ltd**

- Valid Let's Encrypt TLS
- Fly app: `glenn-uploader-sandbox` (region `iad`)
- Alternate URL: `https://glenn-uploader-sandbox.fly.dev` (same deployment)

Production URL **`uploader.hcresearch.ltd` does not exist yet** and was not
configured for this sandbox.

---

## What Glenn can do today

1. **Enter daily rows** for all four programs (date, NLV fields, cash transfer).
2. **See the performance chart** update from entered rows plus real SPX/NDX/BTC
   benchmarks (individual program view).
3. **Review last-seven-rows tables** per program card.
4. **Run Export All Changes** — preview only; confirms what *would* be exported.
5. **Persist data** across sessions — SQLite and benchmark cache live on the
   Fly `/data` volume.

Glenn should treat this sandbox as the **authoritative place to enter and
review daily uploader data** until production is explicitly launched.

---

## Programs

| Program | Full name (internal) | Fields Glenn enters | Notes |
| ------- | -------------------- | ------------------- | ----- |
| **TKP** | TKP tearsheet program | Date · StoneX NLV · Plus500 NLV · Cash Transfer | Only program with **both** StoneX and Plus500 NLV |
| **TCP** | TCP tearsheet program | Date · StoneX NLV · Cash Transfer | StoneX NLV only |
| **AGM** | AGM / Momentum Pacer program | Date · TradeStation NLV · Cash Transfer · **Fee** | Only program with a **Fee** field |
| **Y&Q** | Y&Q program | Date · StoneX NLV · Cash Transfer | StoneX NLV only |

Cash transfers are neutralized in the performance chart (they do not count as
strategy return). AGM **fee** is stored on the row but **excluded** from the
performance line (placeholder until fee logic is finalized).

---

## AGM-only Fee rule

- **`fee` is accepted only for AGM** (`POST /api/rows/AGM`).
- **TKP, TCP, and Y&Q reject `fee`** — the API returns an error if fee is
  sent for those programs.
- AGM fee does not affect the strategy performance line today.

---

## Export All — what it does today

Glenn clicks **Export All Changes** → `POST /api/export/all`.

| Sandbox setting | Value |
| --------------- | ----- |
| `EXPORT_DOWNSTREAM_ENABLED` | `false` |
| `EXPORT_DRY_RUN` | `true` |
| `EXPORT_ENABLED` | `false` |

**Current behavior:**

- Returns a **dry-run preview** of rows that would be exported.
- `dry_run: true`, `transport_implemented: false`, `external_calls_made: 0`.
- **Does not push** data to live TKP, TCP, AGM, or Y&Q tearsheet apps.
- **Does not** change any production tearsheet page or state file.

> **Warning:** Export All is **dry-run only**. It is safe to click, but it
> will **not** update live tearsheet sites. Do not assume tearsheet pages
> reflect uploader entries until a future production export phase is complete.

See also: `downstream_export_contract.md`, `daily_update_workflow.md`.

---

## Performance chart (top of page)

**Title:** *Performance of $100,000 Investment*

### Strategy lines (TKP / TCP / AGM / Y&Q)

- Built **only** from rows Glenn enters in this uploader (`uploader_daily_rows`).
- Normalized to a $100,000 starting base from the first entered row.
- **No historical tearsheet backfill** — the line starts when Glenn's first
  row exists; missing dates are not gap-filled.
- Does **not** read live TKP/TCP/AGM/Y&Q tearsheet apps.

### Benchmark lines (SPX / NDX / BTC)

- **Real market closes** from cached CSV + optional live fetch (yfinance).
- Tickers: SPX → `^GSPC`, NDX → `^NDX`, BTC → `BTC-USD`.
- Labels show plain **SPX**, **NDX**, **BTC** when data is real/cached.
- Shown in **individual program** mode only (not on the combined four-program view).
- Weekend/holiday alignment: prior close within 5 calendar days.

### Banner cues

| Banner | Meaning |
| ------ | ------- |
| *From uploader entries* | Strategy lines are real entered data |
| *Preview chart — demo data only* | Backend unreachable; frontend mock (should not happen on live sandbox) |

Details: `PERFORMANCE_PROVENANCE.md`.

---

## Known limitations

1. **No live downstream export** — tearsheet apps (83xx) are untouched.
2. **No historical strategy import** — chart history = uploader rows only.
3. **Export All is preview/dry-run** — `external_calls_made` is always `0`.
4. **Y&Q export destination** — not implemented even in sandbox file export.
5. **AGM fee** — stored but not reflected in performance line.
6. **Sandbox data is isolated** — separate DB from any future production deploy.
7. **TCP live-page caveat** (future export phase): TCP v2 bakes layout at
   process start; even after real export exists, TCP may need a restart to
   show new rows on the live page (TKP/AGM re-read on each load).

---

## Who should not use production assumptions

- **Glenn / operators:** Do not expect TKP/TCP/AGM/Y&Q tearsheet pages to
  update when you click Export All on the sandbox.
- **Investors / external readers:** Sandbox URL is **not** the public
  production tearsheet experience.
- **Engineering:** Do not point `EXPORT_DOWNSTREAM_ENABLED=true` or production
  export URLs at this sandbox without a reviewed production deploy plan.
- **Anyone comparing to 83xx apps:** Strategy lines here are uploader-only;
  they will diverge from tearsheets until backfill and export are built.

---

## Operator smoke checklist

Run after deploy, DNS change, or cert renewal:

- [ ] Open **https://uploader-sandbox.hcresearch.ltd**
- [ ] Confirm **`GET /health`** → `{"status":"ok",...}`
- [ ] Confirm **`GET /api/programs`** → 4 programs (TKP, TCP, AGM, YQ)
- [ ] Enter **one test row** (e.g. TCP, today's date, test NLV)
- [ ] Confirm row appears in the program table and **graph updates**
- [ ] Call **`/api/performance`** (individual program, SPX+NDX+BTC) — expect
      `program_data_source: uploader_daily_rows`
- [ ] Click **Export All Changes**
- [ ] Confirm response: `dry_run: true`, `transport_implemented: false`,
      `external_calls_made: 0`
- [ ] Confirm **no change** on live TKP/TCP/AGM/Y&Q tearsheet pages
- [ ] (Optional) Restart Fly machine — confirm saved row still exists

Quick curl health check:

```bash
curl -s https://uploader-sandbox.hcresearch.ltd/health
```

---

## Next engineering phase (not in scope today)

1. **Real downstream export contracts** — authenticated ingest paths on
   TKP/TCP/AGM (and later Y&Q); implement `transport_implemented` per
   `downstream_export_contract.md`.
2. **Optional historical strategy backfill** — import prior tearsheet rows so
   uploader chart matches legacy history (explicit scope + sign-off).
3. **Production deployment** — separate Fly app or host at
   `uploader.hcresearch.ltd`, reviewed env (`APP_ENV=production`), export
   flags, and operator runbook. **Do not promote sandbox config as-is.**

Deploy/infra reference: `SANDBOX_DEPLOY.md`, `uploader/fly.toml`.

---

## Related docs

| Document | Purpose |
| -------- | ------- |
| `SANDBOX_DEPLOY.md` | Docker / Fly build and env contract |
| `PERFORMANCE_PROVENANCE.md` | Chart data sources and API fields |
| `daily_update_workflow.md` | Manual daily flow and future automation |
| `downstream_export_contract.md` | Export payload spec and sandbox files |
