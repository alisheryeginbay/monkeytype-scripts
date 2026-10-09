#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Average of your own Monkeytype results for one mode (default: English, time 15).

Fetches your results history from GET /results, which needs an Ape key
(monkeytype.com → Account settings → Ape keys). The endpoint is heavily rate
limited, so results are cached in .cache/my_results.json; pass --refresh to
re-download. Non-premium accounts can only fetch their latest 1000 results.

By default only plain runs count: no punctuation, no numbers, no funbox.

Usage:
    MONKEYTYPE_APE_KEY=... uv run my_average.py
    uv run my_average.py --mode2 30
    uv run my_average.py --language english_1k --punctuation
    uv run my_average.py --last 100          # only your most recent 100 matching runs
"""

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import mean, median, stdev

API = "https://api.monkeytype.com"
CACHE = Path(__file__).parent / ".cache" / "my_results.json"
PAGE_SIZE = 1000
APE_KEY = os.environ.get("MONKEYTYPE_APE_KEY")


class ApiError(Exception):
    pass


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def get(path, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    headers = {"User-Agent": "my-average-script", "Authorization": f"ApeKey {APE_KEY}"}
    req = urllib.request.Request(url, headers=headers)
    attempts = 0
    while True:
        attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset = e.headers.get("x-ratelimit-reset")
                wait_until_reset(int(reset) if reset else int(time.time()) + 60)
                continue
            if e.code < 500:
                try:
                    message = json.load(e).get("message")
                except ValueError:
                    message = e.reason
                raise ApiError(f"Monkeytype API error {e.code}: {message}")
            if attempts >= 5:
                raise
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempts >= 5:
                raise
            log(f"  transient error ({type(e).__name__}), retrying...")
        time.sleep(2 * attempts)


def wait_until_reset(reset_epoch):
    delay = max(reset_epoch - time.time(), 0) + 2
    log(f"  rate limited; sleeping {delay / 60:.1f} min until reset "
        f"({time.strftime('%H:%M:%S', time.localtime(reset_epoch))})")
    time.sleep(delay)


def fetch_results(refresh):
    if CACHE.exists() and not refresh:
        log(f"Using cached results from {CACHE.name} (--refresh to re-download)")
        return json.loads(CACHE.read_text())
    if not APE_KEY:
        sys.exit("Set MONKEYTYPE_APE_KEY to your Ape key (Account settings → Ape keys).")
    results, offset = [], 0
    while True:
        log(f"Fetching results {offset}-{offset + PAGE_SIZE}...")
        try:
            page = get("/results", {"offset": offset, "limit": PAGE_SIZE})["data"]
        except ApiError as e:
            # Non-premium accounts get an error past the first 1000 results.
            if results:
                log(f"  stopping pagination: {e}")
                break
            raise
        results.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(results))
    log(f"Cached {len(results)} results")
    return results


def matches(r, args):
    # Monkeytype omits default values when storing results (e.g. language "english").
    funbox = r.get("funbox") or []
    if isinstance(funbox, str):
        funbox = [] if funbox == "none" else funbox.split("#")
    return (r.get("mode") == "time"
            and str(r.get("mode2")) == args.mode2
            and r.get("language", "english") == args.language
            and bool(r.get("punctuation")) == args.punctuation
            and bool(r.get("numbers")) == args.numbers
            and (args.any_funbox or not funbox))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode2", default="15", help="test length in seconds (default 15)")
    p.add_argument("--language", default="english", help="word list (default english)")
    p.add_argument("--punctuation", action="store_true", help="only runs with punctuation on")
    p.add_argument("--numbers", action="store_true", help="only runs with numbers on")
    p.add_argument("--any-funbox", action="store_true", help="include runs with a funbox active")
    p.add_argument("--last", type=int, help="only the N most recent matching runs")
    p.add_argument("--refresh", action="store_true", help="ignore the cache and re-download")
    args = p.parse_args()

    runs = sorted((r for r in fetch_results(args.refresh) if matches(r, args)),
                  key=lambda r: r["timestamp"], reverse=True)
    if args.last:
        runs = runs[:args.last]
    if not runs:
        sys.exit(f"No {args.language} time {args.mode2} runs found.")

    wpm = [r["wpm"] for r in runs]
    print(f"{args.language} time {args.mode2}: {len(runs)} runs")
    print(f"  wpm          avg {mean(wpm):.2f}   median {median(wpm):.2f}   "
          f"best {max(wpm):.2f}   stdev {stdev(wpm) if len(wpm) > 1 else 0:.2f}")
    for key, label in [("rawWpm", "raw"), ("acc", "accuracy"), ("consistency", "consistency")]:
        vals = [r[key] for r in runs if r.get(key) is not None]
        if vals:
            print(f"  {label:<12} avg {mean(vals):.2f}")


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        sys.exit(str(e))
