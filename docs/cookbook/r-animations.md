# Animated plots in R — Sectors API + ggplot2 + gganimate

> Sources:
> - <https://docs.sectors.app/recipes/animated-plots-in-r/00-telling-stories-w-ggplot>
> - <https://docs.sectors.app/recipes/animated-plots-in-r/01-top-stock-volume-animation-plot>
> - <https://docs.sectors.app/recipes/animated-plots-in-r/02-top-market-cap-animation-plot>
> - <https://docs.sectors.app/recipes/animated-plots-in-r/03-financial-comparison-animation-plot>
> - <https://docs.sectors.app/recipes/animated-plots-in-r/04-dividend-growth-investing>
>
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Five R recipes that turn Sectors data into **animated charts** — perfect for Instagram Reels, TikTok, and pitch decks. Each recipe is a self-contained R script you can lift wholesale.

## When to use this approach

- Your team is comfortable with R and `tidyverse`.
- The deliverable is **content** — short animations, not interactive dashboards.
- You're targeting **Track 3** (market intelligence app) with a content layer, or **Track 2** (automation) where the workflow publishes to socials.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | low | No LLM. |
| Track 2 — Automation | high | The recipes are designed for automated content publishing. |
| Track 3 — Market intelligence / apps | high | Polished animated charts = strong visual artefact. |

## Cost estimate

- Each recipe fetches data once and reuses it. ~5–20 credits total.
- Output: GIF or MP4 (one render per recipe).

## Setup

```r
install.packages(c("tidyverse", "gganimate", "gifski", "httr", "jsonlite"))
```

## Recipe 0 — BREN vs BBCA: telling a market-cap story with ggplot2

> Samuel Chan, May 2024

The story: Barito Renewables (BREN) overtook BBCA as the largest IDX company in mid-2024. This recipe fetches 6 weeks of price data for both and plots the moment of crossover.

```r
library(httr); library(jsonlite); library(ggplot2)

api_key <- "Your API Key"
symbols <- c("BBCA", "BREN", "TPIA")

get_daily <- function(symbol) {
  url      <- paste0("https://api.sectors.app/v2/transaction/daily/", symbol, "/?start=2024-04-01&end=2024-05-15")
  response <- GET(url, add_headers(Authorization = api_key))
  data     <- fromJSON(content(response, "text"), flatten = TRUE)
  data$symbol <- symbol
  data
}

df_daily <- do.call(rbind, lapply(symbols, get_daily))

ggplot(df_daily, aes(x = date, y = market_cap, colour = symbol, group = symbol)) +
  geom_line(linewidth = 1) +
  scale_y_continuous(labels = scales::label_number(scale = 1e-12, suffix = "T")) +
  labs(
    title    = "Market Cap over time — BREN overtakes BBCA",
    subtitle = "Barito Renewables (BREN) becomes largest IDX company",
    x = NULL, y = "Market cap (IDR trillions)",
    caption  = "Source: Sectors API"
  ) +
  theme(axis.text.x = element_text(angle = 90, hjust = 1),
        legend.position = "bottom", legend.justification = "left")
```

This is a static line plot, not animated — perfect for a single PNG in a slide deck. The animated versions below add time as a frame dimension.

## Recipe 1 — Most-traded stocks bar-chart race

> Gerald Bryan, Apr 2024

```r
library(tidyverse); library(gganimate); library(httr)

url    <- "https://api.sectors.app/v2/ranking/most-traded/?start=2024-01-01&end=2024-03-24&n_stock=10"
resp   <- GET(url, add_headers(Authorization = api_key))
data   <- content(resp, "parsed")

df <- do.call(rbind, lapply(names(data), function(date) {
  data.frame(
    date   = rep(date, each = length(data[[date]])),
    symbol = unlist(lapply(data[[date]], function(x) x[[1]])),
    volume = unlist(lapply(data[[date]], function(x) x[[3]]))
  )
}))

df_filter <- df %>%
  group_by(symbol) %>%
  arrange(date) %>%
  mutate(accumulated_volume = cumsum(volume))

df_finished <- df_filter %>%
  group_by(date) %>%
  top_n(10, accumulated_volume) %>%
  arrange(date, accumulated_volume) %>%
  group_by(date) %>%
  mutate(rank = rank(-accumulated_volume))

# Static plot
staticplot <- ggplot(df_finished, aes(rank, group = symbol)) +
  geom_tile(aes(y = accumulated_volume/2, height = accumulated_volume,
                fill = as.factor(symbol), width = 0.9), alpha = 0.8) +
  geom_text(aes(y = 0, label = paste(symbol, " ")), vjust = 0.2, hjust = 1, colour = "white", size = 7) +
  geom_text(aes(y = accumulated_volume, label = paste0(" ", scales::comma(accumulated_volume))),
            colour = "white", hjust = 0, size = 4) +
  coord_flip(clip = "off", expand = FALSE) +
  scale_y_continuous(labels = scales::comma) +
  scale_x_reverse() +
  guides(colour = FALSE, fill = FALSE) +
  theme_minimal()

# Animate
anim <- staticplot +
  transition_states(date, transition_length = 4, state_length = 1) +
  view_follow(fixed_x = TRUE) +
  labs(title = "Cumulative Transaction Volume: {closest_state}",
       subtitle = "Most traded stocks on Indonesia Stock Exchange")

animate(anim, 300, fps = 8, width = 1200, height = 1000,
        renderer = gifski_renderer("most_traded.gif"))
```

**`transition_states()`** is the key gganimate function. Each unique date becomes one frame. `view_follow(fixed_x=TRUE)` keeps the x-axis stable so bars race vertically without the chart jumping.

## Recipe 2 — Market-cap bar-chart race over 4 years

> Gerald Bryan, Apr 2024

Same shape as Recipe 1 but with a different endpoint and a longer window:

```r
stocks_list <- c("ICBP", "BBNI", "TPIA", "HMSP", "ASII", "UNVR", "BMRI",
                 "TLKM", "BBRI", "BBCA", "EMTK", "BRIS", "ARTO", "DCII",
                 "BYAN", "GOTO", "ADRO", "AMMN", "BREN")

# Build date list — one snapshot per month since 2020-12
get_date_list <- function(start_date) {
  seq(as.Date(start_date), Sys.Date(), by = "month")
}

df_daily_hist <- data.frame()
for (i in stocks_list) {
  for (j in 1:(length(date) - 1)) {
    start_date <- format(ifelse(j == 1, date[[j]][1], date[[j]][1] + 1), "%Y-%m-%d")
    end_date   <- format(date[[j + 1]][1], "%Y-%m-%d")
    url        <- paste0("https://api.sectors.app/v2/transaction/daily/", i, "/?start=", start_date, "&end=", end_date)
    response   <- GET(url, add_headers(Authorization = api_key))
    if (status_code(response) == 200) {
      chunk <- fromJSON(content(response, "text"), flatten = TRUE)
      df_daily_hist <- rbind(df_daily_hist, as.data.frame(chunk))
    }
  }
}

# Aggregate to monthly snapshots
df_daily_hist <- df_daily_hist %>%
  mutate(month = month(date), year = year(date)) %>%
  filter(date > "2020-12-01") %>%
  arrange(date) %>%
  group_by(symbol, year, month) %>%
  summarise(market_cap = last(market_cap), .groups = "drop")

# Build animated chart (same shape as Recipe 1)
staticplot <- ggplot(df_daily_hist, ...) +
  ... (same as Recipe 1)

anim <- staticplot +
  transition_states(date_formatted, transition_length = 4, state_length = 1) +
  view_follow(fixed_x = TRUE) +
  labs(title = "Market Capitalization: {closest_state}",
       subtitle = "Stocks with Highest Market Cap on IDX since December 2020")

animate(anim, 300, fps = 8, width = 1200, height = 1000,
        renderer = gifski_renderer("top_market_cap.gif"))
```

Two tweaks from Recipe 1:

- Each frame is one month, not one day — 60 frames over 5 years keeps the GIF under 30 seconds.
- `last(market_cap)` aggregates daily snapshots to the last-trading-day-of-month.

## Recipe 3 — Value-investing scatter (P/E vs P/B animated by year)

> Gerald Bryan, May 2024

This one is different — a scatter plot animated across years showing P/E vs P/B for 8 banks.

```r
banks <- c("BBCA", "BBRI", "BMRI", "MEGA", "BRIS", "NISP", "BNGA", "BBNI")

df_finance <- data.frame()
for (i in banks) {
  url      <- paste0("https://api.sectors.app/v2/company/report/", i, "/?sections=valuation")
  response <- GET(url, add_headers(Authorization = api_key))
  data     <- fromJSON(content(response, "text"), flatten = TRUE)
  valuation <- data$valuation
  # `valuation` is a data frame with rows per year; columns include pe_ratio, pb_ratio, year
  df_finance <- rbind(df_finance, cbind(symbol = i, valuation))
}

# Static scatter
p <- ggplot(df_finance, aes(x = pe_ratio, y = pb_ratio, colour = symbol)) +
  geom_point(size = 4, alpha = 0.7) +
  geom_text(aes(label = symbol), vjust = -1, size = 3) +
  scale_x_log10() + scale_y_log10() +
  labs(title = "P/E vs P/B — top 8 Indonesian banks",
       x = "P/E ratio (log)", y = "P/B ratio (log)") +
  theme_minimal() +
  theme(legend.position = "none")

# Animate by year
anim <- p + transition_time(year) +
  labs(subtitle = "Year: {frame_time}")

animate(anim, 200, fps = 8, width = 1200, height = 1000,
        renderer = gifski_renderer("banks_pe_pbv.gif"))
```

`transition_time(year)` is gganimate's continuous-time transition — each year smoothly interpolates between the previous and next frame's positions. Cleaner than discrete `transition_states()` when you have a numeric axis.

`scale_x_log10()` is essential for P/E and P/B — both have heavy right tails (one bank at 30× P/E while the rest cluster around 10×).

## Recipe 4 — Dividend growth investing (line chart animated)

> Gerald Bryan, May 2024

```r
library(tidyverse); library(httr); library(jsonlite); library(gganimate)

api_key <- "YOUR API KEY"
stocks  <- c("BBCA", "BBRI", "BYAN", "BMRI", "TLKM", "ASII", "BBNI")

df_div <- data.frame()
for (i in stocks) {
  url      <- paste0("https://api.sectors.app/v2/company/report/", i, "/?sections=dividend")
  response <- GET(url, add_headers(Authorization = api_key))
  if (status_code(response) == 200) {
    parsed  <- fromJSON(content(response, "text"), flatten = TRUE)
    hist    <- parsed$dividend$historical_dividends
    hist$symbol <- i
    hist <- hist %>% select(symbol, year, total_dividend)
    df_div <- rbind(df_div, hist)
  }
}

# Compute dividend yield growth per stock (% change vs base year)
df_div <- df_div %>%
  group_by(symbol) %>%
  arrange(year) %>%
  mutate(yield_growth = (total_dividend / first(total_dividend) - 1) * 100) %>%
  ungroup()

# Animated line chart
plot <- ggplot(df_div, aes(x = year, y = yield_growth, colour = symbol)) +
  geom_line(linewidth = 1) +
  geom_point(size = 6) +
  geom_text(aes(label = symbol), hjust = -0.1, size = 4) +
  labs(x = "year", y = "Dividend Growth (%)",
       title = "Dividend Yield Growth from 7 Major Companies in Indonesia") +
  theme_minimal() +
  theme(legend.position = "top")

anim <- plot + transition_reveal(year)
animate(anim, 200, fps = 8, width = 1400, height = 1000,
        renderer = gifski_renderer("dividend_growth.gif"))
```

`transition_reveal(year)` is gganimate's "draw the line as time progresses" transition — points appear one at a time as the line extends. Perfect for cumulative-style data.

## Known pitfalls (all recipes)

- **`.JK` suffix**: in older R examples you may see `BBCA.JK`. The Sectors REST API accepts both. Strip before passing to other endpoints (URLs, screener queries).
- **`add_headers(Authorization = ...)`**: spelling matters. `Authotization` (typo in the original BREN recipe) silently sends no header and you get a 401 you don't notice. Always confirm status code is 200.
- **`gifski` not installed**: `animate(..., renderer = gifski_renderer(...))` requires the `gifski` package. Install it once: `install.packages("gifski")`. If you don't, gganimate falls back to a slow default renderer.
- **Big loops are slow**: Recipe 2 fetches 19 stocks × ~60 months = ~1,100 API calls. At ~1 credit each, that's the entire budget. Cache the result to disk with `saveRDS(df_daily_hist, "marketcap_history.rds")` and re-render only the animation:
  ```r
  df_daily_hist <- readRDS("marketcap_history.rds")
  ```
- **`fromJSON()` column types**: integer columns sometimes come through as character if any value is `null`. Coerce with `mutate(across(where(is.character) & !symbol, as.numeric))` before plotting.
- **Date alignment**: dates from Sectors come as `YYYY-MM-DD` strings. Convert with `as.Date()` before passing to `transition_time()`.
- **Animation file size**: a 300-frame GIF at 1200×1000 can be 30+ MB. Reduce frames (`animate(anim, 100, fps = 5, ...)`) or width before publishing.

## Cross-links

- Static visualisation in Python: [`sectorscan-part1.md`](sectorscan-part1.md)
- Streamlit app with charts: [`sectorscan-part2.md`](sectorscan-part2.md)
- REST endpoints: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)