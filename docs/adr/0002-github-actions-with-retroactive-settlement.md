---
status: accepted
date: 2026-10-18
---

# Run on GitHub Actions cron and settle liquidations/TPs retroactively at each Tick

There is no always-on server: a public GitHub repository runs an hourly workflow (`7 * * * *`, offset to avoid the :00 scheduling pile-up) and a weekly one (Monday 00:07 UTC), state is committed back into `data/` as JSON, and the dashboard is a static GitHub Pages site reading those files. Because the Engine only wakes hourly, it replays the past hour's 1-minute candles at each Tick to settle liquidations and TP fills in time order before the Executor decides; cron delays therefore change when a Tick runs, not what it settles.

## Considered Options

- Long-running process on a VPS watching every minute: more real-time, but costs money, needs a host and a dashboard backend, and the hourly decision cadence makes minute-level reaction pointless.
- Private repository: 2,000 free Actions minutes/month is below the ~2,900 an hourly 4-minute job needs.

## Consequences

- Dashboard and settlement lag reality by up to one hour plus cron delay.
- A missed Tick is skipped, never replayed for decisions; the next Tick settles the whole gap from 1m candles. Hyperliquid serves only the latest 5,000 bars per interval, so a gap longer than ~3.5 days settles on 15m bars (up to ~52 days) and beyond that on 1h; every settled event records the `resolution` used. A coarse bar straddling the previous Tick counts in full, so it can settle a liquidation or TP from prices before the gap began.
- A funding hour that no candle reached (feed lag at :07) still settles at the Tick, priced at the last known close, so funding is never dropped.
- Raw model prompts are too large to commit hourly; they go to workflow artifacts (90-day retention) while responses and market snapshot ids live in the repo.
