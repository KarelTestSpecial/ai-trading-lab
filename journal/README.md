# journal

The paper-trading track record.

`decisions.jsonl` is **append-only** and committed to this public repository by the
daily `daily-paper` GitHub Action. Each line is one decision: the exact input
snapshot, the judgment (if any), the target weights, the orders submitted, any
risk vetoes, and the account state.

Because the file is committed and its git history is public, the record is
**tamper-evident**: any edit after the fact is visible in the commit history.
This is what turns a backtest into real, auditable evidence over time.

The file is created on the first paper run; it does not exist yet.
