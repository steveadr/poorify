## /inspect <module>

Query the architecture state for everything related to a module keyword.

### Action
Call `poorify --inspect "<keyword>"` to search across all tables.

### What it shows
- **Specs** — technical pre/post conditions for files matching the keyword
- **Complexity** — routed files, SKELETON/FULL mode, cyclomatic complexity scores
- **Assertions** — business rules and their last validation status
- **Metrics** — aggregated token usage across pipeline runs (input, output, cached, skeleton savings)
- **Cascade** — any pending compiler cascade repairs
- **Logs** — recent execution log entries

### Example output
```
[poorify] Inspect: "Trading"

  Files (4)
    src/trading/executor.rs    12.0 kB       FULL  (cx: 12)  3 fn  imports: validator, serde, tokio
    src/trading/validator.rs    4.2 kB       FULL  (cx: 8)   2 fn  imports: config, thiserror
    src/trading/config.rs       1.1 kB    SKELETON (cx: 2)   1 fn  imports: serde
    src/trading/types.rs        0.8 kB    SKELETON (cx: 1)        imports: serde

  Specs (2)
    src/trading/executor.rs   pre: fee=2%   post: fee=1.5%
    src/trading/validator.rs  pre: no limit  post: 10k max

  Complexity (3 files)
    2 FULL, 1 SKELETON  |  avg complexity: 7.3
    src/trading/executor.rs  FULL (cx: 12)

  Assertions (2)
    TRADING_FEE    src/trading/executor.rs    (last: 2026-06-04)
    TRADING_LIMIT  src/trading/validator.rs   (last: 2026-06-04)

  Metrics (2 runs)
    4200 in / 1560 out / 360 cached / 2400 saved

  Cascade: none
  Logs: none
```

### No argument
`poorify --inspect` (without a keyword) shows a compact summary of the entire architecture.
