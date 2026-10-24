# Glossary Map

## Contexts

- [Investor Basecamp](./GLOSSARY.md): portfolios, holdings, scenarios, shocks, and risk budgets for Schwab accounts
- [Schwab CLI](./tools/schwab/GLOSSARY.md): single-contract option repricing and P/L what-ifs at the command line

## Relationships

- **Shared pricing terms**: [Mark, Mark-implied IV, Settlement instant, and Remaining life](./GLOSSARY.md) are defined once, in Investor Basecamp. The Schwab CLI and the pricing engine use them as defined there.
- **Schwab CLI → Investor Basecamp**: CLI **Entry** (per-share premium for P/L) is not [Total Cost](./GLOSSARY.md) on a held **Position**. A CLI **Scenario** in plain language is not the app’s **Scenario** grid — the app runs **Shocks** across a **Portfolio**; the CLI runs one contract with pricing modes (fair value, hold-to-expiry, pre-expiry sale).
- **Investor Basecamp ↔ Schwab CLI**: **Underlying** and option contracts mean the same instrument; the app aggregates **Positions**, the CLI addresses one OCC symbol at a time.
