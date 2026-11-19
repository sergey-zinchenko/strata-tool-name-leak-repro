# Strata tool-name leak repro (`TaskCreate`)

One production request that made Qwen3.8-Flash-Next invent `<function=TaskCreate>` while the declared Claude Code tool set had no such name ([Niko1221/Strata#6022](https://github.com/Niko1221/Strata/issues/6022), [PR #5969](https://github.com/Niko1221/Strata/pull/5969)).

## Why this fixture

Stock `tool_markup_retry` (default on) already rewrites once when a reply ends in unread tool markup. On this turn it often fires — and **the rewrite can still write `TaskCreate` again**, so the client still gets raw markup / an undeclared name. Constrained tool-name decoding (`tool_name_constraint`) removes that class of failure.

The full message history is kept on purpose: short synthetic prompts did not reproduce the leak in our runs.

Light edits only: `C:\Users\serge\` → `C:\Users\user\`, image parts → `[image omitted]`.

## Run

Against any OpenAI-compatible Strata (or similar) server:

```bash
export STRATA_URL=http://127.0.0.1:8080
export STRATA_KEY=…
# optional: print Strata /metrics tool_markup_retries before/after
export STRATA_METRICS=1
python validate.py fixtures/taskcreate_claude_code.json
```

- Exit `0` — no undeclared name in `tool_calls` and no call markup with an undeclared name in `content`.
- Exit `1` — leak (or HTTP error).

Expect, on `main` without `tool_name_constraint`: intermittent FAIL with `TaskCreate`, often with `tool_markup_retries` incremented. With the constraint on: OK and usually no retry.
