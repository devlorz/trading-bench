---
status: accepted
date: 2026-10-18
---

# Layer liquidation is the stop-loss; no stop orders exist

TSM Principle 4 defines a fixed "SL" per layer but also tells the trader to hold losing positions (NAV-) and free them with hostage profit, and the user chose the literal mapping "100 นาย = ทั้งบัญชี" (4 layers × 25%). We model each Layer as an isolated sub-account with fixed collateral holding one position of fixed notional; the Layer is lost when its collateral is exhausted by Hyperliquid's maintenance-margin rule, and the Engine offers no stop order at all. Leverage is therefore not a choice but notional / collateral, capped by the asset's max leverage on Hyperliquid.

## Considered Options

- Hard stop at `capital / N` per layer (my recommendation): safer benchmark, but contradicts the document's hold-and-rescue mechanic that the user wants to measure.
- Strategist-chosen stop distance: breaks the "RP constant, size never adjusted by ego" rule.

## Consequences

- A Contestant can lose 25% of equity per layer and all equity in one week. Elimination below 1,000 USDC is the only floor.
- Funding payments reduce a Layer's collateral, so liquidation creeps closer the longer a position is held.
- Collateral per Layer is fixed at Reallocation (weekly, only when all Layers are flat), so profits sit as Hostage in free equity and are only used to reopen lost Slots or at the next Reallocation.
