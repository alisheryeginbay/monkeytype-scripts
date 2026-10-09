# monkeytype-analysis

`my_average.py` prints your average wpm, raw wpm, accuracy and consistency for one
[Monkeytype](https://monkeytype.com) mode (default: English, time 15). It's a standalone
[uv](https://docs.astral.sh/uv/) script with no dependencies (plain `python3` works too).

```sh
MONKEYTYPE_APE_KEY=... uv run my_average.py
uv run my_average.py --mode2 30                # time 30 instead
uv run my_average.py --language english_1k     # another word list
uv run my_average.py --last 100                # only your 100 most recent matching runs
```

Only plain runs count by default (no punctuation, numbers or funbox); see `--help` for flags.

`MONKEYTYPE_APE_KEY` is required (Account settings → Ape keys). Your results are cached in
`.cache/` (git-ignored) because the endpoint is heavily rate limited; pass `--refresh` to
re-download. Non-premium accounts can only fetch their latest 1000 results.
