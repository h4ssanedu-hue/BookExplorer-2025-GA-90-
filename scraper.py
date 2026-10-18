import csv
import os
import threading
import time
from urllib.parse import urlparse, parse_qs, unquote

import requests
from PyQt5.QtCore import QThread, pyqtSignal

DEFAULT_URL = "https://openlibrary.org/search.json"
DEFAULT_QUERY = "subject:fiction"
FIELDS = ("key,title,author_name,first_publish_year,edition_count,language,"
          "subject,publisher,isbn,number_of_pages_median,ratings_average")
COLUMNS = ["Title", "Author", "First Publish Year", "Edition Count",
           "Language", "Subject", "Publisher", "ISBN", "Pages", "Rating"]
CSV_PATH = os.path.join("data", "books.csv")
PAGE_SIZE = 100


def query_from_url(text):
    """Turn an Open Library URL typed by the user into a search query."""
    text = text.strip()
    if not text:
        raise ValueError("Please paste a URL.")
    if not text.startswith("http"):
        text = "https://" + text
    parsed = urlparse(text)
    if not parsed.netloc.endswith("openlibrary.org"):
        raise ValueError("Only openlibrary.org URLs are supported.")
    params = parse_qs(parsed.query)
    if parsed.path.startswith("/search") and "q" in params:
        return params["q"][0]
    if parsed.path.startswith("/subjects/"):
        name = unquote(parsed.path.split("/subjects/")[1].strip("/"))
        return 'subject:"' + name.replace("_", " ") + '"'
    raise ValueError(
        "Unsupported URL. Use an Open Library search URL, e.g. "
        "https://openlibrary.org/search?q=subject:romance")


def first(value, default=""):
    """Return the first item of a list, or the value itself."""
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def parse_book(doc):
    """Convert one API document into a row (list of 10 attributes)."""
    return [
        str(doc.get("title", "")).strip(),
        str(first(doc.get("author_name"), "Unknown")),
        int(doc.get("first_publish_year") or 0),
        int(doc.get("edition_count") or 0),
        str(first(doc.get("language"), "N/A")),
        str(first(doc.get("subject"), "N/A")),
        str(first(doc.get("publisher"), "N/A")),
        str(first(doc.get("isbn"), "N/A")),
        int(doc.get("number_of_pages_median") or 0),
        round(float(doc.get("ratings_average") or 0), 2),
    ]


def save_csv(rows):
    os.makedirs("data", exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def load_csv():
    """Load saved books from disk. Numeric columns are converted back."""
    if not os.path.exists(CSV_PATH):
        return []
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for r in reader:
            rows.append([r[0], r[1], int(r[2]), int(r[3]), r[4], r[5],
                         r[6], r[7], int(r[8]), float(r[9])])
    return rows


class ScraperWorker(QThread):
    progress = pyqtSignal(int, int)      # scraped, target
    finished_ok = pyqtSignal(list)       # all rows
    failed = pyqtSignal(str)

    def __init__(self, existing_rows=None, target=15000, url=DEFAULT_URL,
                 query=DEFAULT_QUERY, start_page=None):
        super().__init__()
        self.rows = list(existing_rows or [])
        self.target = target
        self.url = url
        self.query = query
        self.start_page = start_page
        self._run_flag = threading.Event()
        self._run_flag.set()             # set = running, cleared = paused
        self._stopped = False
        self._seen = {r[0] + "|" + r[1] for r in self.rows}

    # ----- controls -----
    def pause(self):
        self._run_flag.clear()

    def resume(self):
        self._run_flag.set()

    def stop(self):
        self._stopped = True
        self._run_flag.set()             # wake up if paused

    # ----- main loop -----
    def run(self):
        page = self.start_page or (len(self.rows) // PAGE_SIZE + 1)
        errors = 0
        while len(self.rows) < self.target and not self._stopped:
            self._run_flag.wait()        # blocks here while paused
            if self._stopped:
                break
            try:
                resp = requests.get(
                    self.url,
                    params={"q": self.query, "fields": FIELDS,
                            "limit": PAGE_SIZE, "page": page},
                    headers={"User-Agent": "BookExplorer-CS200/1.0"},
                    timeout=30,
                )
                resp.raise_for_status()
                docs = resp.json().get("docs", [])
                if not docs:
                    break
                for doc in docs:
                    row = parse_book(doc)
                    key = row[0] + "|" + row[1]
                    if row[0] and key not in self._seen:
                        self._seen.add(key)
                        self.rows.append(row)
                page += 1
                errors = 0
                self.progress.emit(len(self.rows), self.target)
                time.sleep(0.3)          # be polite to the server
            except Exception as e:
                errors += 1
                if errors >= 5:
                    self.failed.emit(str(e))
                    break
                time.sleep(2)
        save_csv(self.rows)
        self.finished_ok.emit(self.rows)