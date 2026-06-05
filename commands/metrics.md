## /metrics

View pipeline statistics from the Caveman Harness database.

### Commands

**Latest pipeline run:**
```
poorify --metrics
```

**Specific pipeline:**
```
poorify --metrics <pipeline_id>
```

**Aggregate statistics across all runs:**
```
poorify --metrics-all
```

### Sample output
```
──────────────────────────────────────────────────────────────────────────────
  Pipeline: P20260604-191500-a1b2c3
──────────────────────────────────────────────────────────────────────────────
  Phase              Input   Output   Cached    Ctx%   Dur(ms)   Retry    Saved
  ---------------------------------------------------------------------------
  requirements        300       80        0    3.8%      1200        0        0
  ingestion             0        0        0    0.0%       300        0     2400
  development         1200      420      180   15.0%      8400        2        0
  gate                180       90        0    2.2%       400        0        0
  ---------------------------------------------------------------------------
  TOTAL              1680      590      180   15.0%     10300                 2400
──────────────────────────────────────────────────────────────────────────────
```
