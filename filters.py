import math
import time

from sorting import make_key

STRING_COLS = {0, 1, 4, 5, 6, 7}
NUMERIC_COLS = {2, 3, 8, 9}

STRING_OPS = ["contains", "starts with", "ends with", "equals", "does not contain"]
NUMERIC_OPS = ["=", "!=", ">", "<", ">=", "<="]


def parse_value(col, text):
    """Convert the typed text to the right type for the column."""
    text = text.strip()
    if col == 9:
        return float(text)
    if col in NUMERIC_COLS:
        return int(text)
    return text.lower()


def make_predicate(col, op, value):
    """Return a function row -> True/False for one condition."""
    def get(row):
        v = row[col]
        return v.lower() if isinstance(v, str) else v

    if op == "contains":
        return lambda r: value in get(r)
    if op == "does not contain":
        return lambda r: value not in get(r)
    if op == "starts with":
        return lambda r: get(r).startswith(value)
    if op == "ends with":
        return lambda r: get(r).endswith(value)
    if op in ("equals", "="):
        return lambda r: get(r) == value
    if op == "!=":
        return lambda r: get(r) != value
    if op == ">":
        return lambda r: get(r) > value
    if op == "<":
        return lambda r: get(r) < value
    if op == ">=":
        return lambda r: get(r) >= value
    if op == "<=":
        return lambda r: get(r) <= value
    raise ValueError("Unknown operator: " + op)


def apply_filter(rows, col, op, value):
    """Linear scan filter. Returns (result, time_ms, comparisons)."""
    pred = make_predicate(col, op, value)
    start = time.perf_counter()
    result = [r for r in rows if pred(r)]
    ms = (time.perf_counter() - start) * 1000
    return result, ms, len(rows)


# ---------- exact-match search algorithms ----------
# Each one gets: keys (list), rows (same order), target.
# Each one returns: (matching_rows, comparisons)

def _collect(keys, rows, idx, target):
    """Given one matching index, return all neighbours with the same key."""
    lo = idx
    while lo > 0 and keys[lo - 1] == target:
        lo -= 1
    hi = idx
    while hi < len(keys) - 1 and keys[hi + 1] == target:
        hi += 1
    return rows[lo:hi + 1]


def linear_search(keys, rows, target):
    comps = 0
    out = []
    for i, k in enumerate(keys):
        comps += 1
        if k == target:
            out.append(rows[i])
    return out, comps


def binary_search(keys, rows, target):
    lo, hi = 0, len(keys) - 1
    comps = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        comps += 1
        if keys[mid] == target:
            return _collect(keys, rows, mid, target), comps
        comps += 1
        if keys[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return [], comps


def jump_search(keys, rows, target):
    n = len(keys)
    comps = 0
    if n == 0:
        return [], 0
    step = int(math.sqrt(n)) or 1
    prev, cur = 0, step
    while prev < n:
        comps += 1
        if keys[min(cur, n) - 1] >= target:
            break
        prev = cur
        cur += step
    if prev >= n:
        return [], comps
    for i in range(prev, min(cur, n)):
        comps += 1
        if keys[i] == target:
            return _collect(keys, rows, i, target), comps
        if keys[i] > target:
            break
    return [], comps


def interpolation_search(keys, rows, target):
    """Numeric columns only."""
    lo, hi = 0, len(keys) - 1
    comps = 0
    while lo <= hi and keys[lo] <= target <= keys[hi]:
        comps += 1
        if keys[hi] == keys[lo]:
            if keys[lo] == target:
                return _collect(keys, rows, lo, target), comps
            break
        pos = lo + int((target - keys[lo]) * (hi - lo) / (keys[hi] - keys[lo]))
        comps += 1
        if keys[pos] == target:
            return _collect(keys, rows, pos, target), comps
        if keys[pos] < target:
            lo = pos + 1
        else:
            hi = pos - 1
    return [], comps


SEARCH_ALGORITHMS = {
    "Linear Search":        {"func": linear_search,        "complexity": "O(n)",            "needs_sorted": False},
    "Binary Search":        {"func": binary_search,        "complexity": "O(log n)",        "needs_sorted": True},
    "Jump Search":          {"func": jump_search,          "complexity": "O(sqrt n)",       "needs_sorted": True},
    "Interpolation Search": {"func": interpolation_search, "complexity": "O(log log n) avg", "needs_sorted": True},
}


def exact_search(rows, col, value, algo_name):
    """Exact match search with the chosen algorithm.
    Binary/Jump/Interpolation need sorted data, so the data is sorted first
    (that preparation time is NOT included in the reported time).
    Returns (result, time_ms, comparisons)."""
    info = SEARCH_ALGORITHMS[algo_name]
    key = make_key(col)
    if info["needs_sorted"]:
        pairs = sorted(((key(r), r) for r in rows), key=lambda p: p[0])
        keys = [p[0] for p in pairs]
        srows = [p[1] for p in pairs]
    else:
        keys = [key(r) for r in rows]
        srows = rows
    start = time.perf_counter()
    result, comps = info["func"](keys, srows, value)
    ms = (time.perf_counter() - start) * 1000
    return result, ms, comps
def apply_composite(rows, conditions):
    """conditions = [(connector, negate, col, op, value), ...]
    connector is 'AND' or 'OR' (ignored for the first condition).
    AND binds tighter than OR: A OR B AND C  ==  A OR (B AND C).
    Returns (result, time_ms, evaluations)."""
    groups = []
    for i, (connector, negate, col, op, value) in enumerate(conditions):
        pred = make_predicate(col, op, value)
        if negate:
            pred = (lambda p: (lambda r: not p(r)))(pred)
        if i == 0 or connector == "OR":
            groups.append([pred])
        else:
            groups[-1].append(pred)

    start = time.perf_counter()
    result = [r for r in rows if any(all(p(r) for p in g) for g in groups)]
    ms = (time.perf_counter() - start) * 1000
    return result, ms, len(rows) * len(conditions)