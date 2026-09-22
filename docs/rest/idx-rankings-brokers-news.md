# IDX Rankings, Brokers, News & Filings — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. IDX ticker = 4-letter code, optionally `.JK`.

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/companies/top-changes/` | Top gainers/losers × 1d/7d/14d/30d/365d |
| `GET /v2/most-traded/` | Most traded by volume over a date range |
| `GET /v2/brokers/` | Curated broker registry (name, origin, cohort, license type) |
| `GET /v2/brokers/top/` | Top brokers by gross/net for one date |
| `GET /v2/broker-summary/{symbol}/` | Per-broker activity for one symbol (≤14d) |
| `GET /v2/broker-summary/{symbol}/top/` | Top buyers/sellers for one symbol |
| `GET /v2/broker-activity/{broker_code}/` | One broker's daily activity across symbols (≤14d) |
| `GET /v2/broker-activity/{broker_code}/top/` | One broker's top accumulations/distributions |
| `GET /v2/foreign-flow/{symbol}/` | Daily net foreign inflow for one symbol (≤90d) |
| `GET /v2/news/` | News articles (IDX or mining extension) |
| `GET /v2/filings/` | Insider trading filings |
| `GET /v2/suspensions/` | Historical stock suspensions with PDF URLs |
| `GET /v2/tags/` | Discovery — valid news/filings tag slugs |

> Path corrections vs the high-level `sectors-api-and-mcp.md` index:
> - `/v2/companies/top-changes/` is the actual top-movers path (NOT `/v2/ranking/top-changes/`).
> - `/v2/news/`, `/v2/filings/`, `/v2/suspensions/` are top-level (NOT under `/v2/news/news/`, `/v2/news/filings/`, `/v2/news/suspensions/`).
> - Broker endpoints are nested: `/v2/brokers/` (registry), `/v2/brokers/top/`, `/v2/broker-summary/{symbol}/`, `/v2/broker-summary/{symbol}/top/`, `/v2/broker-activity/{broker_code}/`, `/v2/broker-activity/{broker_code}/top/`, `/v2/foreign-flow/{symbol}/`.

---

### `GET /v2/companies/top-changes/`

- **Purpose:** Top gainers and losers across 5 periods × 2 classifications, optionally filtered by subsector and minimum market cap.

- **Query parameters**

| Name | Type | Default | Allowed / range | Notes |
|---|---|---|---|---|
| `classifications` | array | both | `top_gainers`, `top_losers` | Comma-separated. Bad value → 400. |
| `periods` | array | all 5 | `1d`, `7d`, `14d`, `30d`, `365d` | Comma-separated. Bad value → 400. |
| `sub_sector` | string | — | kebab-case slug from `/v2/subsectors/` | Restrict the movers to one subsector. |
| `n_stock` | int | 5 | 1–10 | Per-period list length. Max 10. |
| `min_mcap_billion` | int | 5000 | ≥0 | Min market cap in billion IDR. Default 5000 = 5T IDR floor. |

- **Cost:** 1 credit per `classification × period` pair. Defaults (2×5) = 10 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/companies/top-changes/?sub_sector=banks&periods=1d,7d&n_stock=5" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/companies/top-changes/",
    headers={"Authorization": "<api-key>"},
    params={"sub_sector": "banks", "periods": "1d,7d", "n_stock": 5},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response (truncated)**

```json
{
  "top_gainers": {
    "1d": [
      { "name": "PT Nitrasanata Dharma Tbk", "symbol": "JECX.JK", "price_change": 0.25, "last_close_price": 1950, "latest_close_date": "2026-07-08" }
    ],
    "7d": [
      { "name": "PT Samator Indo Gas Tbk", "symbol": "AGII.JK", "price_change": 0.232, "last_close_price": 3080, "latest_close_date": "2026-07-08" }
    ]
  },
  "top_losers": {
    "1d": [
      { "name": "Sentul City Tbk", "symbol": "BKSL.JK", "price_change": -0.0895, "last_close_price": 61, "latest_close_date": "2026-07-08" }
    ]
  }
}
```

- **Gotchas**
  - `price_change` is a decimal multiplier (0.25 = +25%).
  - Default `min_mcap_billion=5000` quietly excludes micro-caps. Set `min_mcap_billion=0` to see everything.
  - `n_stock` caps at 10 — there's no way to get a top-20 from this endpoint.

---

### `GET /v2/most-traded/`

- **Purpose:** Most traded IDX stocks by transaction volume over a date range (≤90 days). Results keyed by date.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | 30 days before `end` | `YYYY-MM-DD` | Wider ranges clamped to most recent 90. |
| `end` | string (date) | today | `YYYY-MM-DD` | Future → 400. |
| `sub_sector` | string | — | kebab-case slug | Filter to one subsector; bad value → 400 "The requested sub_sector does not exist." |
| `n_stock` | int | 5 | 1–10 | Per-day list length. |
| `adjusted` | bool | false | true/false | `true` ranks by volume × close (turnover), `false` by raw volume. |

- **Cost:** 2 credits per call.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/most-traded/?start=2025-05-02&end=2025-05-02&n_stock=5&adjusted=true" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/most-traded/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-02", "end": "2025-05-02", "n_stock": 5, "adjusted": "true"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "2025-05-02": [
    { "symbol": "GOTO.JK", "company_name": "PT GoTo Gojek Tokopedia Tbk", "volume": 2627450200, "price": 82 },
    { "symbol": "DEWA.JK", "company_name": "Darma Henwa Tbk", "volume": 1563426700, "price": 138 }
  ]
}
```

- **Gotchas**
  - Response is **dict keyed by date** — call across a range and you get a map of date → array.
  - `adjusted=true` is the "real" turnover measure; `false` rewards cheap stocks with huge share counts.

---

### `GET /v2/brokers/`

- **Purpose:** Curated registry of every IDX exchange-member broker with name, origin (`foreign`/`domestic`), cohort (`retail`/`mixed`/`institutional`/`unknown`), and license type. Authoritative source for valid `broker_code` values used by other broker endpoints.

- **Query parameters**

| Name | Type | Allowed | Notes |
|---|---|---|---|
| `origin` | string | `domestic`, `foreign` | Case-insensitive filter. |
| `cohort` | string | `institutional`, `mixed`, `retail`, `unknown` | Case-insensitive filter. |

- **Cost:** 1 credit.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/brokers/?origin=foreign&cohort=institutional" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/brokers/",
    headers={"Authorization": "<api-key>"},
    params={"origin": "foreign", "cohort": "institutional"},
    timeout=30,
)
r.raise_for_status()
codes = [b["code"] for b in r.json()]
```

- **Sample response**

```json
[
  {
    "code": "AD",
    "name": "Sukadana Prima Sekuritas",
    "is_foreign": false,
    "cohort": "institutional",
    "license_type": "Online, Online AO, Penjamin Emisi Efek, Perantara Pedagang Efek, RT AO"
  }
]
```

- **Gotchas**
  - Broker codes are **two letters** (`AD`, `MG`, `AK`, `CC`...).
  - Cache this once per build — it changes rarely and is required to make sense of `top/`, `summary/`, `activity/` responses.
  - `cohort` may be `null` for unclassified brokers (schema marks it nullable).

---

### `GET /v2/brokers/top/`

- **Purpose:** Top brokers by gross trade value (default) or absolute net flow for one date, optionally filtered by origin/c cohort.

- **Query parameters**

| Name | Type | Default | Allowed / range | Notes |
|---|---|---|---|---|
| `date` | string (date) | latest available | `YYYY-MM-DD` | — |
| `metric` | string | `gross` | `gross`, `net` | `gross` = buy + sell value; `net` = absolute net flow. |
| `origin` | string | `all` | `all`, `domestic`, `foreign` | — |
| `cohort` | string | `all` | `all`, `institutional`, `mixed`, `retail`, `unknown` | — |
| `n_brokers` | int | all (~88) | 1–90 | Cap the result list. |

- **Cost:** 2 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/brokers/top/?date=2026-07-08&metric=gross&origin=foreign&n_brokers=10" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/brokers/top/",
    headers={"Authorization": "<api-key>"},
    params={"date": "2026-07-08", "metric": "gross", "origin": "foreign", "n_brokers": 10},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "date": "2026-07-08",
  "metric": "gross",
  "origin": "foreign",
  "cohort": "all",
  "results": [
    { "rank": 1, "broker_code": "AK", "gross": 1984643350000, "net": -326211642600 }
  ]
}
```

- **Gotchas**
  - 404 "No broker activity available" when the date has no broker data — 1 credit (lookup ran).
  - Without `n_brokers` you get all ~88 brokers; payload can be large.

---

### `GET /v2/broker-summary/{symbol}/`

- **Purpose:** Per-broker daily trading rows for one ticker over ≤14 days. Each row lists every broker active that day with buy/sell/net values, lots, frequency, weighted avg price.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX ticker, 4 letters, optionally `.jk`. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `broker_code` | string | — | e.g. `MG` | Optional filter to a single broker. |
| `start` | string (date) | end - 14 days | `YYYY-MM-DD` | Max 14 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | — |

- **Cost:** 1 credit.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/broker-summary/BBCA/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/broker-summary/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "start": "2025-05-01",
  "end": "2025-05-14",
  "data": [
    {
      "date": "2025-05-02",
      "summary": [
        {
          "broker_code": "AF",
          "bfreq": 1, "blot": 55, "bval": 48950000, "bavg_per_share": 8900,
          "sfreq": 1, "slot": 50, "sval": 44875000, "savg_per_share": 8975,
          "nlot": 5, "nval": 4075000, "navg_per_share": 8900
        }
      ]
    }
  ]
}
```

- **Gotchas**
  - 14-day window — for older history, paginate `start`/`end`.
  - `bval`/`sval` are buy/sell value in IDR; `bval/100` = nominal buy volume in lots.
  - 404 "Symbol 'XYZA' not found in broker data" → 1 credit.

---

### `GET /v2/broker-summary/{symbol}/top/`

- **Purpose:** Top net buyers and top net sellers for one symbol over ≤90 days. Spot institutional accumulation/distribution.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX ticker, 4 letters, optionally `.jk`. |

- **Query parameters**

| Name | Type | Default | Allowed / range | Notes |
|---|---|---|---|---|
| `start` | string (date) | end - 30 days | `YYYY-MM-DD` | Max 90 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | — |
| `origin` | string | `all` | `all`, `domestic`, `foreign` | — |
| `cohort` | string | `all` | `all`, `institutional`, `mixed`, `retail`, `unknown` | — |
| `n_brokers` | int | 10 | 1–90 | Each list (`top_buyers` and `top_sellers`) gets this many entries. |

- **Cost:** 2 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/broker-summary/BBCA/top/?start=2025-05-01&end=2025-05-14&origin=foreign" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/broker-summary/BBCA/top/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14", "origin": "foreign"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "start": "2025-05-01",
  "end": "2025-05-14",
  "origin": "all", "cohort": "all",
  "top_buyers": [
    { "rank": 1, "broker_code": "KZ", "net_idr": 645536242500, "buy_idr": 1163325432500, "sell_idr": 517789190000 }
  ],
  "top_sellers": [
    { "rank": 1, "broker_code": "BK", "net_idr": -318961117500, "buy_idr": 561727337500, "sell_idr": 880688455000 }
  ]
}
```

- **Gotchas**
  - `top_sellers[].net_idr` is **negative** — sort ascending to get biggest sellers.
  - Default `n_brokers=10` (not 5 like most top endpoints). Max 90.

---

### `GET /v2/broker-activity/{broker_code}/`

- **Purpose:** One broker's daily activity across all symbols it touched (≤14 days). Filter to one symbol to see a single-stock view from that broker.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `broker_code` | string | Two-letter code, e.g. `MG`, `AK`, `CC`. Get from `/v2/brokers/`. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `symbol` | string | — | e.g. `BBCA` | Optional filter to one stock. |
| `start` | string (date) | end - 14 days | `YYYY-MM-DD` | Max 14 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | — |

- **Cost:** 1 credit.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/broker-activity/YP/?start=2025-05-01&end=2025-05-02" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/broker-activity/YP/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-02"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "broker_code": "YP",
  "start": "2025-05-01",
  "end": "2025-05-02",
  "data": [
    {
      "date": "2025-05-02",
      "summary": [
        {
          "symbol": "AADI.JK",
          "bfreq": 588, "blot": 8591, "bval": 5764735000, "bavg_per_share": 6710.2025,
          "sfreq": 401, "slot": 7301, "sval": 4896690000, "savg_per_share": 6706.8758,
          "nlot": 1290, "nval": 868045000, "navg_per_share": 6710.2025
        }
      ]
    }
  ]
}
```

- **Gotchas**
  - This is the **mirror** of `/v2/broker-summary/{symbol}/` (per-broker vs per-symbol).
  - 404 "Broker 'ZZ' not found in broker data" → 1 credit.

---

### `GET /v2/broker-activity/{broker_code}/top/`

- **Purpose:** One broker's top net accumulations and distributions across the universe (≤90 days).

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `broker_code` | string | Two-letter code. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | end - 30 days | `YYYY-MM-DD` | Max 90 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | — |
| `n_brokers` | int | 10 | 1–90 | Each list size. |

- **Cost:** 2 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/broker-activity/YP/top/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/broker-activity/YP/top/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "broker_code": "YP",
  "start": "2025-05-01",
  "end": "2025-05-14",
  "top_accumulations": [
    { "rank": 1, "symbol": "ASII.JK", "net_idr": 58416394000, "buy_idr": 117493365000, "sell_idr": 59076971000 }
  ],
  "top_distributions": [
    { "rank": 1, "symbol": "BBCA.JK", "net_idr": -99677162500, "buy_idr": 97605242500, "sell_idr": 197282405000 }
  ]
}
```

- **Gotchas**
  - Mirror of `/v2/broker-summary/{symbol}/top/`. Use it to ask "what is broker X doing across the universe?" instead of "who's trading symbol Y?"

---

### `GET /v2/foreign-flow/{symbol}/`

- **Purpose:** Daily net foreign-broker inflow (IDR) for one IDX ticker over ≤90 days.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX ticker, 4 letters, optionally `.jk`. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | end - 30 days | `YYYY-MM-DD` | Max 90 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | — |

- **Cost:** 1 credit.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/foreign-flow/BBCA/?start=2025-05-01&end=2025-05-05" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/foreign-flow/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-05"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "start": "2025-05-01",
  "end": "2025-05-05",
  "data": [
    { "date": "2025-05-02", "net_foreign_inflow": 199859810000 }
  ]
}
```

- **Gotchas**
  - Only foreign flow is exposed because IDX is a closed market — domestic flow = `−net_foreign_inflow`. Don't double-count.
  - Positive = net foreign buying; negative = net foreign selling.
  - 404 "Symbol 'XYZA' not found in broker data" → 1 credit.

---

### `GET /v2/news/`

- **Purpose:** Paginated news articles from IDX or mining extension sources. Each extension accepts a different parameter set.

- **Query parameters**

| Name | Type | Default | Allowed / format | Applies to | Notes |
|---|---|---|---|---|---|
| `extension` | string | `idx` | `idx`, `mining` | both | Data source. |
| `keyword` | string | — | substring | both | Case-insensitive substring match on article title. |
| `sector` | string | — | comma-sep kebab slugs | idx only | Bad mix with `extension=mining` → 400. |
| `sub_sector` | string | — | comma-sep kebab slugs | idx only | Same. |
| `tags` | string | — | comma-sep tag slugs | idx only | From `/v2/tags/`. |
| `symbols` | string | — | comma-sep IDX symbols, e.g. `BBCA,BBRI` | idx only | — |
| `commodity_type` | string | — | `Bauxite`, `Coal`, `Copper`, `Gold`, `Iron`, `Nickel`, `Non-Metallic Mineral`, `Sand, Stone, Gravel`, `Tin` | mining only | — |
| `start` | string (date) | — | `YYYY-MM-DD` | both | Optional lower bound on `timestamp`. |
| `end` | string (date) | — | `YYYY-MM-DD` | both | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | both | Page size. |
| `offset` | int | 0 | ≥0 | both | Pagination offset. |

- **Cost:** 1 credit per page.

- **Sample request (IDX)**

```bash
curl "https://api.sectors.app/v2/news/?extension=idx&sub_sector=banks&symbols=BBCA,BBRI&limit=20" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/news/",
    headers={"Authorization": "<api-key>"},
    params={"extension": "idx", "sub_sector": "banks", "symbols": "BBCA,BBRI", "limit": 20},
    timeout=30,
)
r.raise_for_status()
articles = r.json()["results"]
```

- **Sample response (IDX)**

```json
{
  "results": [
    {
      "title": "OJK says Henry Surya's false statements delayed the investigation into PT Asuransi Jiwa Prolife Indonesia fraud case",
      "body": "The Financial Services Authority (OJK) said Henry Surya's lies prolonged the probe of a fraud at PT Asuransi Jiwa Prolife Indonesia. ...",
      "source": "https://money.kompas.com/read/2026/07/09/.../ojk-sebut-kebohongan-henry-surya-buat-pengusutan-kasus-indosurya-makan-waktu",
      "thumbnail": "https://asset.kompas.com/crops/.../230x152/data/photo/2026/07/09/6a4f38026d694.jpg",
      "timestamp": "2026-07-09T18:05:00",
      "sector": "financials",
      "sub_sector": ["insurance"],
      "tags": ["Violation", "Risk & Compliance", "Politics & Regulation", "Bearish"],
      "symbols": [],
      "dimension": {
        "future": 0, "dividend": 0, "ownership": 0, "technical": 0,
        "valuation": 0, "financials": 0, "management": 0, "sustainability": 0
      }
    }
  ],
  "pagination": {
    "total_count": 8665, "showing": 1, "limit": 2, "offset": 0,
    "has_next": true, "has_previous": false,
    "next_offset": 2, "previous_offset": null
  }
}
```

- **Gotchas**
  - **`extension` is the most common foot-gun** — passing IDX-only filters like `sector=...` while `extension=mining` returns 400 listing the valid params.
  - `dimension` is IDX-only; mining responses have `commodity_type` instead and omit sector/sub_sector/tags/symbols/dimension/thumbnail.
  - `timestamp` is an ISO datetime string for IDX; check format before parsing.
  - 400 cases are free; 2xx bills 1 credit; 404 not applicable (empty result is 200).

---

### `GET /v2/filings/`

- **Purpose:** IDX insider-trading filings — buy/sell transactions by insiders and major shareholders.

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `symbol` | string | — | IDX ticker, e.g. `BBCA` | Filter to one symbol. |
| `sector` | string | — | kebab-case sector slug | From `/v2/subsectors/`. |
| `sub_sector` | string | — | kebab-case subsector slug | From `/v2/subsectors/`. |
| `transaction_type` | string | — | `buy`, `sell`, `others` | — |
| `holder_type` | string | — | `corporate-investor`, `insider`, `institution` | Case-insensitive. |
| `tags` | string | — | comma-sep tag slugs | From `/v2/tags/`. |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `timestamp`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | Page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |

- **Cost:** 1 credit per page.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/filings/?symbol=BBCA&transaction_type=buy&limit=20" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/filings/",
    headers={"Authorization": "<api-key>"},
    params={"symbol": "BBCA", "transaction_type": "buy", "limit": 20},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [
    {
      "title": "Samuel Sekuritas Indonesia buys shares of Nusantara Sawit Sejahtera",
      "body": "This is Samuel Sekuritas Indonesia's 5th insider purchase in the last 6 months, ...",
      "source": "https://www.idx.co.id/StaticData/NewsAndAnnouncement/.../LK-09072026-5264-00.pdf",
      "timestamp": "2026-07-09T14:29:39",
      "sector": "consumer-non-cyclicals",
      "sub_sector": "food-beverage",
      "tags": ["placement", "repurchase-agreement"],
      "symbol": "NSSS.JK",
      "transaction_type": "buy",
      "holder_type": "institution",
      "holder_name": "Samuel Sekuritas Indonesia",
      "holding_before": 9559919000,
      "holding_after": 10169179100,
      "amount_transaction": 609260100,
      "price": 576.478,
      "transaction_value": 351225097500,
      "price_transaction": [{ "date": "2026-07-07", "type": "buy", "price": 580, "amount_transacted": 180108000 }],
      "share_percentage_before": 40.17,
      "share_percentage_after": 42.73,
      "share_percentage_transaction": 2.56,
      "idx_investor_slug": null,
      "idx_conglomerates_group_slug": null
    }
  ],
  "pagination": { "total_count": 3016, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - Most fields are nullable; design for missing values.
  - `holding_before`/`holding_after` are **share counts**, not IDR.
  - `price_transaction` is an array (multi-day transactions happen).
  - `transaction_value` and `share_percentage_transaction` are the headline metrics for "how big was this insider move".

---

### `GET /v2/suspensions/`

- **Purpose:** Historical IDX stock suspensions with official reason + IDX PDF notice link.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `symbol` | string | — | IDX ticker (case-insensitive) | Filter to one company. |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `suspension_date`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | Page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |

- **Cost:** 1 credit per page.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/suspensions/?limit=20" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/suspensions/",
    headers={"Authorization": "<api-key>"},
    params={"limit": 20},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [
    {
      "symbol": "FLMC.JK",
      "suspension_date": "2026-07-03",
      "reason": "Terjadinya penurunan harga kumulatif yang signifikan pada saham FLMC.JK",
      "pdf_url": "https://www.idx.co.id/Portals/0/StaticData/NewsAndAnnouncement/.../20260702-WAS_Suspensi_FLMC.pdf"
    }
  ],
  "pagination": { "total_count": 556, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - Reasons are in **Indonesian**. Render the text directly, or translate with your LLM layer.
  - `pdf_url` links directly to IDX — treat as the authoritative source.
  - 556 historical suspensions in the universe — useful for backtests of "is suspension a leading indicator".

---

### `GET /v2/tags/`

- **Purpose:** Discovery — sorted alphabetical array of valid `tags` slugs for news/filings.

- **Query parameters:** none.

- **Cost:** 1 credit.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/tags/" -H "Authorization: <api-key>"
```

```python
r = requests.get("https://api.sectors.app/v2/tags/", headers={"Authorization": "<api-key>"}, timeout=30)
r.raise_for_status()
tags = r.json()  # ["analyst-ratings", "Bearish", "Bullish", ...]
```

- **Sample response**

```json
["analyst-ratings"]
```

- **Gotchas**
  - Cache aggressively — the full list is ~80 slugs and rarely changes.
  - Tags are case-sensitive in the `tags=` filter even though they look mixed-case.

---

## Cross-reference

- **Rankings** (`top-changes`, `most-traded`) are the cheapest "what's moving?" surfaces — 1–2 credits per call.
- **Broker endpoints** form a complete picture when combined: `registry` → discover codes → `top/` → who's hot today → `broker-summary/{symbol}/top/` → who's trading a stock → `broker-activity/{broker_code}/top/` → what else that broker is doing.
- **Foreign flow** is the cleanest "smart money" signal — pair with `/v2/daily/{symbol}/` for context.
- **News/filings/suspensions** are the narrative surface — use `extension=idx` for company moves, `extension=mining` for sector stories.
- See `idx-screener.md` for universe feeds, `idx-company.md` for per-company reports, `idx-financials-transactions.md` for time-series, `sgx.md`/`klse.md`/`mining.md` for the other regions.