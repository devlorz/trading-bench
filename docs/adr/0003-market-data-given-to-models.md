---
status: accepted
date: 2026-10-18
---

# Models receive raw candles plus a fixed Indicator Pack, and nothing else

LLMs, especially the small Executor models, are unreliable at arithmetic over dozens of candles, and this benchmark is meant to measure the Strategist's tactic and the Executor's discipline, not mental RSI calculation. So the Engine computes one Indicator Pack per symbol and timeframe with stdlib code and attaches it to every candle series it sends, identical for every Contestant, and sends fewer raw candles in exchange. The pack is a versioned contract (`indicator_pack_version` recorded with every model response) frozen before Week 1; changing its definition or parameters means starting a new benchmark.

## What is given

- Candles (OHLCV), trimmed: Executor 4H × 30, 1H × 24, 15m × 16 per watchlist symbol; Strategist 1D × 30 and raw weekly × 12 per universe symbol. The Engine fetches ~200 bars per timeframe to warm the indicators up and sends only the tail.
- Candles are sent compactly: one start timestamp per series (bars are contiguous), then `[o, h, l, c, v]` per bar with prices rounded to the asset's tick size and volume to a whole number. The first live run showed 50 symbols × 56 bars at full float precision cost ~234k characters, more than the full TSM text; this encoding halves it. The encoding is part of the frozen contract and carries its own `prompt_encoding_version` recorded with every response.
- Indicator Pack on every series except weekly, computed from closed bars only. Series values come as three points (now, 1 bar ago, 5 bars ago): EMA 20, EMA 50, RSI 14 (Wilder; a flat series reads 50), ATR 14 (Wilder, as price and as % of close), MACD 12/26/9 (line, signal, histogram). Swings are single points: the last confirmed fractal swing high and swing low (3 bars each side; price and bars ago) plus one `swing_position` value, above/below/between the two, null while either swing is missing.
- Per symbol: % change over 24h and 7d (Strategist also 30d); VWAP from 15m bars with typical price (H+L+C)/3, with % distance of price from it and the number of bars accumulated: for the Executor anchored at 00:00 UTC today (null with 0 bars right after midnight); for the Strategist the VWAP of the Week that just ended, [previous Monday 00:00, this Monday 00:00), since the weekly run happens minutes after the boundary when the new Week has no closed bar yet.
- Mark price, current and predicted funding rate, open interest, max leverage (unchanged).

## What is deliberately withheld

- L2 order book (the Engine uses it for fills only), news, social, on-chain and cross-exchange data.
- Any indicator outside the list above, including volume indicators other than VWAP.

## Considered Options

- Raw candles only (the implicit default before this decision): fairer in a purist sense, but mixes arithmetic ability into the score and costs more tokens.
- Letting each Strategist request its own indicators: measures something interesting but breaks comparability and multiplies prompt code.
