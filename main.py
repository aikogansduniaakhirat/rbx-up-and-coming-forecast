# roblox-up-and-coming-forecast-01 entry: a recency-weighted rank model.
# Reads /input/history.ndjson (the chart's reads) and /input/task.json, writes
# /output/forecast.json: for each of the top 10 places, a probability for each of a
# set of candidate games, plus a top-10 order. Deterministic: no clock, no randomness.
import json
import math
import os

IN = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUT = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

N_CAND = 8
SIGMA = 1.8
MASS = 0.94
HALFLIFE = 1.0
W_MEAN = 0.20
W_LAST = 0.80
AGE_PEN = 2.6
YOUNG = 0.2
SLOPE = 0.4


def ranks_of(reading):
    out = {}
    for row in reading.get("up_and_coming") or []:
        r = row.get("rank")
        u = row.get("universe_id")
        if isinstance(r, int) and isinstance(u, int):
            out[u] = r
    return out


def main():
    with open(os.path.join(IN, "history.ndjson"), encoding="utf-8") as fh:
        history = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(IN, "task.json"), encoding="utf-8") as fh:
        task = json.load(fh)
    places = int(task.get("places", 10))
    n = len(history)
    acc = {}
    for i, reading in enumerate(history):
        ranks = ranks_of(reading)
        if not ranks:
            continue
        w = 0.5 ** ((n - 1 - i) / HALFLIFE)
        for u, r in ranks.items():
            a = acc.get(u)
            if a is None:
                acc[u] = [w, w * r, r, i, i, [r]]
            else:
                a[0] += w
                a[1] += w * r
                a[2] = r
                a[3] = i
                a[5].append(r)
    score = {}
    for u, (w, wr, last_rank, last_i, first_i, seen) in acc.items():
        mean_rank = wr / w if w else float(last_rank)
        s = W_MEAN * mean_rank + W_LAST * last_rank
        if len(seen) >= 3:
            k = min(4, len(seen) - 1)
            s += SLOPE * (last_rank - seen[-1 - k]) / k
        s += (n - 1 - last_i) * AGE_PEN
        s -= min(first_i, 6) * YOUNG
        score[u] = s
    order = sorted(score, key=lambda u: (score[u], u))
    cand = order[:N_CAND]
    exp_place = {u: i + 1 for i, u in enumerate(cand)}
    probabilities = []
    for k in range(1, places + 1):
        ws = []
        tot = 0.0
        for u in cand:
            dd = exp_place[u] - k
            w = math.exp(-(dd * dd) / (2.0 * SIGMA * SIGMA))
            ws.append((u, w))
            tot += w
        if tot <= 0:
            continue
        for u, w in ws:
            p = MASS * w / tot
            if p >= 1e-6:
                probabilities.append({"universe_id": u, "place": k, "p": round(p, 6)})
    top10 = order[:places]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, task.get("output", "forecast.json")), "w", encoding="utf-8") as fh:
        json.dump({"probabilities": probabilities, "top10": top10}, fh, separators=(",", ":"))
        fh.write("\n")


main()
