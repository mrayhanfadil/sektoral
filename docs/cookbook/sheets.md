# Google Sheets → Sectors API

> Source: <https://docs.sectors.app/recipes/non-programmatical-tools/02-sheets/02-sheets>
> Author of original recipe: Vincentius C. Calvin (Jul 2024)
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Two ways to get live IDX data into Google Sheets:

1. **API Connector** (no-code, click-and-config) — recommended for most people.
2. **Apps Script** (JavaScript in the cloud) — for the cases API Connector can't handle: parameterised loops, scheduled triggers, complex transforms.

## When to use this approach

- Audience lives in Sheets already (most Indonesian analysts, retail investors, students).
- You want to share a live workbook publicly via link.
- You want to schedule hourly/daily refreshes without owning a server.
- You plan to feed the data into **Looker Studio** for charts (see [`looker.md`](looker.md)).

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents / assistants | low | Sheets itself isn't an agent runtime. Combine with n8n or Apps Script LLM calls if you want an AI component. |
| Track 2 — Automation workflows | high | Hourly refresh of a watchlist + alert when conditions trip = classic automation track. |
| Track 3 — Market intelligence / apps | high | A polished Sheets+Looker dashboard with sector comps is a credible artefact. |

## Cost estimate

Same logic as the Excel cookbook — every refresh costs credits. A typical watchlist workbook with ~10 endpoints refreshes in ~5–10 credits. Free API Connector scheduled refresh is **not available** (paid feature only). Apps Script time-driven triggers are free and call on whatever schedule you set.

## End-to-end walkthrough

### Method A — API Connector (recommended)

1. Install **API Connector** from the Google Workspace Marketplace (`Extensions` → `Add-ons` → `Get add-ons` → search `API Connector`).
2. `Extensions` → `API Connector` → `Open`. A sidebar opens on the right.
3. Click **Create request**:
   - **Method**: `GET`
   - **Request URL**: `https://api.sectors.app/v2/transaction/daily/bbca`
   - **Headers**: add `Authorization` → value = your raw Sectors API key (no `Bearer` prefix for REST).
4. **Output settings**: pick which sheet/cell to land the data. `Set current` (default) overwrites the active cell. For multi-ticker workflows, pick a separate request per ticker with `Output mode` = `append` and tick **Remove header row**.
5. Click **Run**.

Nested JSON is auto-exploded into columns — one click less than Power Query. For deeper nesting (e.g. `company.report.{sections}`), iterate by running a separate request per section.

### Method B — Apps Script (JavaScript)

For control freaks and people who want to schedule refreshes for free:

1. `Extensions` → `Apps Script`.
2. Paste a function like:

```javascript
function ImportDailyData(ticker) {
  const url = `https://api.sectors.app/v2/transaction/daily/${ticker}`;
  const options = {
    headers: { Authorization: PropertiesService.getScriptProperties().getProperty('SECTORS_API_KEY') },
    muteHttpExceptions: true,
  };
  const response = UrlFetchApp.fetch(url, options);
  if (response.getResponseCode() !== 200) return;
  const rows = JSON.parse(response.getContentText());
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ticker.toUpperCase());
  sheet.getRange(1, 1, rows.length, Object.keys(rows[0]).length).setValues(
    rows.map(r => Object.values(r))
  );
}
```

3. Store your API key safely: `Project Settings` → **Script Properties** → add `SECTORS_API_KEY` = `<your key>`. Never hardcode.
4. Schedule: clock icon → `+ Add Trigger` → pick the function, set time-driven (hourly/daily/weekly).

Apps Script triggers need **wrapper functions without parameters** (because time-driven triggers can't pass arguments):

```javascript
function RunDailyDataBBCA() { ImportDailyData('bbca'); }
function RunDailyDataBMRI() { ImportDailyData('bmri'); }
```

## Known pitfalls

- **Apps Script quotas**: free Google accounts are limited to ~90 minutes of script execution time per day and 20,000 URL Fetch calls/day. For heavy refreshes you'll bump into this.
- **API Connector auto-refresh** is a paid feature. Don't promise hourly free refreshes in your hackathon pitch — use Apps Script triggers instead.
- **Time zone**: Sheets is in your sheet's timezone, but Sectors returns dates as `YYYY-MM-DD`. Anchor everything to WIB (UTC+7) for consistency with IDX trading hours.
- **`.JK` suffix**: REST tolerates both `bbca` and `bbca.jk`. Sheets won't care, but be consistent across your requests so copy-paste stays reliable.
- **API Connector flatten depth**: deeply nested objects (e.g. quarterly financials with sub-objects like `financials_sector_metrics.net_interest_income`) sometimes flatten weirdly. When that happens, switch to Apps Script and explicitly pick the fields you need.
- **Don't put your API key in a cell.** That's a Sectors-grade leak — anyone with edit access to your sheet can grab it. Use Script Properties or API Connector's credential storage.

## Build-quality checklist

- [ ] One tab per endpoint or per ticker; consistent naming.
- [ ] Header row frozen (`View` → `Freeze` → `1 row`).
- [ ] Date column formatted as Date (not text).
- [ ] Trigger wrapper functions exist for every scheduled fetch.
- [ ] Script Properties used for the API key; no plain-text keys in cells.
- [ ] Logs visible: `Executions` tab in Apps Script editor — confirm successful runs.

## Cross-links

- Excel equivalent: [`excel.md`](excel.md)
- Feed your Sheets into Looker: [`looker.md`](looker.md)
- A more powerful automation story: [`n8n-api.md`](n8n-api.md)
- REST endpoint reference: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)