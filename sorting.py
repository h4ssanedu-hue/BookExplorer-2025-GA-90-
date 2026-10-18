import time


class Stats:
    """Counts comparisons and swaps (element moves) during a sort."""

    def __init__(self):
        self.comparisons = 0
        self.swaps = 0


# Every algorithm sorts a list of [key, row] pairs in place, ascending.

def bubble_sort(a, s):
    n = len(a)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            s.comparisons += 1
            if a[j][0] > a[j + 1][0]:
                a[j], a[j + 1] = a[j + 1], a[j]
                s.swaps += 1
                swapped = True
        if not swapped:
            break


def selection_sort(a, s):
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            s.comparisons += 1
            if a[j][0] < a[m][0]:
                m = j
        if m != i:
            a[i], a[m] = a[m], a[i]
            s.swaps += 1


def insertion_sort(a, s):
    for i in range(1, len(a)):
        cur = a[i]
        j = i - 1
        while j >= 0:
            s.comparisons += 1
            if a[j][0] > cur[0]:
                a[j + 1] = a[j]
                s.swaps += 1
                j -= 1
            else:
                break
        a[j + 1] = cur


def merge_sort(a, s):
    if len(a) <= 1:
        return
    mid = len(a) // 2
    left, right = a[:mid], a[mid:]
    merge_sort(left, s)
    merge_sort(right, s)
    i = j = k = 0
    while i < len(left) and j < len(right):
        s.comparisons += 1
        if right[j][0] < left[i][0]:
            a[k] = right[j]
            j += 1
        else:
            a[k] = left[i]
            i += 1
        s.swaps += 1
        k += 1
    while i < len(left):
        a[k] = left[i]
        i += 1
        k += 1
        s.swaps += 1
    while j < len(right):
        a[k] = right[j]
        j += 1
        k += 1
        s.swaps += 1


def quick_sort(a, s):
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        if lo >= hi:
            continue
        pivot = a[(lo + hi) // 2][0]
        i, j = lo, hi
        while i <= j:
            while True:
                s.comparisons += 1
                if a[i][0] < pivot:
                    i += 1
                else:
                    break
            while True:
                s.comparisons += 1
                if a[j][0] > pivot:
                    j -= 1
                else:
                    break
            if i <= j:
                if i != j:
                    a[i], a[j] = a[j], a[i]
                    s.swaps += 1
                i += 1
                j -= 1
        stack.append((lo, j))
        stack.append((i, hi))


def heap_sort(a, s):
    n = len(a)

    def sift_down(root, end):
        while True:
            child = 2 * root + 1
            if child > end:
                break
            if child + 1 <= end:
                s.comparisons += 1
                if a[child][0] < a[child + 1][0]:
                    child += 1
            s.comparisons += 1
            if a[root][0] < a[child][0]:
                a[root], a[child] = a[child], a[root]
                s.swaps += 1
                root = child
            else:
                break

    for start in range(n // 2 - 1, -1, -1):
        sift_down(start, n - 1)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        s.swaps += 1
        sift_down(0, end - 1)


def shell_sort(a, s):
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            cur = a[i]
            j = i
            while j >= gap:
                s.comparisons += 1
                if a[j - gap][0] > cur[0]:
                    a[j] = a[j - gap]
                    s.swaps += 1
                    j -= gap
                else:
                    break
            a[j] = cur
        gap //= 2


def comb_sort(a, s):
    n = len(a)
    gap = n
    done = False
    while not done:
        gap = int(gap / 1.3)
        if gap <= 1:
            gap = 1
            done = True
        for i in range(n - gap):
            s.comparisons += 1
            if a[i][0] > a[i + gap][0]:
                a[i], a[i + gap] = a[i + gap], a[i]
                s.swaps += 1
                done = False


# name -> info. "slow" = O(n^2) in the average case (asks for confirmation on big data)
ALGORITHMS = {
    "Bubble Sort":    {"func": bubble_sort,    "complexity": "O(n^2)",     "stable": True,  "slow": True},
    "Selection Sort": {"func": selection_sort, "complexity": "O(n^2)",     "stable": False, "slow": True},
    "Insertion Sort": {"func": insertion_sort, "complexity": "O(n^2)",     "stable": True,  "slow": True},
    "Merge Sort":     {"func": merge_sort,     "complexity": "O(n log n)", "stable": True,  "slow": False},
    "Quick Sort":     {"func": quick_sort,     "complexity": "O(n log n)", "stable": False, "slow": False},
    "Heap Sort":      {"func": heap_sort,      "complexity": "O(n log n)", "stable": False, "slow": False},
    "Shell Sort":     {"func": shell_sort,     "complexity": "O(n log^2 n)", "stable": False, "slow": False},
    "Comb Sort":      {"func": comb_sort,      "complexity": "O(n^2) worst", "stable": False, "slow": False},
}


def make_key(col):
    """Key for one column: strings are compared case-insensitively."""
    def key(row):
        v = row[col]
        return v.lower() if isinstance(v, str) else v
    return key


def sort_rows(rows, col, algo_name, descending=False):
    """Sort rows by one column. Returns (sorted_rows, time_ms, Stats)."""
    key = make_key(col)
    pairs = [(key(r), r) for r in rows]
    stats = Stats()
    func = ALGORITHMS[algo_name]["func"]
    start = time.perf_counter()
    func(pairs, stats)
    elapsed_ms = (time.perf_counter() - start) * 1000
    result = [p[1] for p in pairs]
    if descending:
        result.reverse()
    return result, elapsed_ms, stats
class MultiKey:
    """Key that compares several columns, each ascending or descending.
    Works with every sorting algorithm above (they only use < and >)."""

    __slots__ = ("vals", "desc")

    def __init__(self, vals, desc):
        self.vals = vals
        self.desc = desc

    def _cmp(self, other):
        for a, b, d in zip(self.vals, other.vals, self.desc):
            if a != b:
                r = -1 if a < b else 1
                return -r if d else r
        return 0

    def __lt__(self, other):
        return self._cmp(other) < 0

    def __gt__(self, other):
        return self._cmp(other) > 0


def sort_rows_multi(rows, levels, algo_name):
    """levels = [(column_index, descending), ...] from most to least important.
    Returns (sorted_rows, time_ms, Stats)."""
    key_funcs = [make_key(c) for c, _ in levels]
    desc = [d for _, d in levels]
    pairs = [(MultiKey([f(r) for f in key_funcs], desc), r) for r in rows]
    stats = Stats()
    func = ALGORITHMS[algo_name]["func"]
    start = time.perf_counter()
    func(pairs, stats)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return [p[1] for p in pairs], elapsed_ms, stats