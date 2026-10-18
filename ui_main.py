from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QProgressBar, QTableView, QLabel, QMessageBox, QHeaderView, QSpinBox,
    QComboBox, QApplication, QDialog, QTableWidget, QTableWidgetItem,
    QLineEdit, QGridLayout, QDialogButtonBox,
)

import filters
from composite_dialog import CompositeDialog
import scraper
import sorting
from scraper import COLUMNS, ScraperWorker, query_from_url


class BenchmarkDialog(QDialog):
    """Shows a comparison table of all sorting algorithms."""

    HEADERS = ["Algorithm", "Time (ms)", "Comparisons", "Swaps",
               "Complexity", "Stable"]

    def __init__(self, results, column_name, row_count, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Benchmark - '{column_name}' ({row_count} rows)")
        self.resize(820, 380)
        layout = QVBoxLayout(self)

        table = QTableWidget(len(results), len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)

        fastest = min(r["time"] for r in results if r["time"] is not None)
        for i, r in enumerate(results):
            if r["time"] is None:
                values = [r["name"], "Skipped", "-", "-",
                          r["complexity"], "Yes" if r["stable"] else "No"]
            else:
                values = [r["name"], f"{r['time']:.2f}", f"{r['comparisons']:,}",
                          f"{r['swaps']:,}", r["complexity"],
                          "Yes" if r["stable"] else "No"]
            for j, v in enumerate(values):
                item = QTableWidgetItem(v)
                if j > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                if r["time"] is not None and r["time"] == fastest:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)

        note = QLabel("Fastest algorithm is shown in bold.")
        layout.addWidget(note)


class MultiSortDialog(QDialog):
    """Lets the user choose up to 3 sort levels and an algorithm."""

    LEVELS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Level Sort")
        self.resize(480, 260)
        layout = QVBoxLayout(self)

        grid = QGridLayout()
        self.col_boxes = []
        self.order_boxes = []
        for i in range(self.LEVELS):
            label = "Sort by:" if i == 0 else "Then by:"
            grid.addWidget(QLabel(label), i, 0)
            col_box = QComboBox()
            col_box.addItem("(none)")
            col_box.addItems(COLUMNS)
            order_box = QComboBox()
            order_box.addItems(["Ascending", "Descending"])
            grid.addWidget(col_box, i, 1)
            grid.addWidget(order_box, i, 2)
            self.col_boxes.append(col_box)
            self.order_boxes.append(order_box)
        self.col_boxes[0].setCurrentIndex(2)   # default: Author
        self.col_boxes[1].setCurrentIndex(3)   # default: First Publish Year
        self.order_boxes[1].setCurrentIndex(1)
        layout.addLayout(grid)

        algo_row = QHBoxLayout()
        algo_row.addWidget(QLabel("Algorithm:"))
        self.algo_box = QComboBox()
        for name, info in sorting.ALGORITHMS.items():
            stable = "Stable" if info["stable"] else "Not stable"
            self.algo_box.addItem(f"{name}  [{info['complexity']}, {stable}]", name)
        self.algo_box.setCurrentIndex(self.algo_box.findData("Merge Sort"))
        algo_row.addWidget(self.algo_box)
        layout.addLayout(algo_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_levels(self):
        levels = []
        for col_box, order_box in zip(self.col_boxes, self.order_boxes):
            idx = col_box.currentIndex()
            if idx > 0:
                levels.append((idx - 1, order_box.currentIndex() == 1))
        return levels

    def get_algo(self):
        return self.algo_box.currentData()


class BookTableModel(QAbstractTableModel):
    """Table model that shows a list of rows (each row is a list)."""

    NUMERIC_COLUMNS = {2, 3, 8, 9}

    def __init__(self, rows=None):
        super().__init__()
        self.rows = rows or []

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return str(self.rows[index.row()][index.column()])
        if role == Qt.TextAlignmentRole and index.column() in self.NUMERIC_COLUMNS:
            return Qt.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Book Explorer - CS200 Project 1")
        self.resize(1300, 700)

        self.all_rows = scraper.load_csv()     # full dataset
        self.current_rows = self.all_rows      # what the table shows (filtered)
        self.worker = None

        self._build_ui()
        self._update_status()
        self._set_buttons(idle=True)

    # ---------- UI building ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- scraping controls ---
        scrape_bar = QHBoxLayout()
        scrape_bar.addWidget(QLabel("Target books:"))
        self.target_spin = QSpinBox()
        self.target_spin.setRange(100, 100000)
        self.target_spin.setValue(15000)
        self.target_spin.setSingleStep(1000)
        scrape_bar.addWidget(self.target_spin)

        self.btn_start = QPushButton("Start")
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Resume")
        self.btn_stop = QPushButton("Stop")
        self.btn_start.clicked.connect(self.start_scraping)
        self.btn_pause.clicked.connect(self.pause_scraping)
        self.btn_resume.clicked.connect(self.resume_scraping)
        self.btn_stop.clicked.connect(self.stop_scraping)
        for b in (self.btn_start, self.btn_pause, self.btn_resume, self.btn_stop):
            scrape_bar.addWidget(b)
        scrape_bar.addStretch()
        layout.addLayout(scrape_bar)

        # --- bonus: scrape from URL ---
        url_bar = QHBoxLayout()
        url_bar.addWidget(QLabel("Scrape from URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://openlibrary.org/search?q=subject:romance")
        self.url_edit.setMinimumWidth(420)
        url_bar.addWidget(self.url_edit)
        url_bar.addWidget(QLabel("Add up to:"))
        self.url_count = QSpinBox()
        self.url_count.setRange(100, 50000)
        self.url_count.setValue(2000)
        self.url_count.setSingleStep(500)
        url_bar.addWidget(self.url_count)
        self.btn_url = QPushButton("Scrape URL")
        self.btn_url.clicked.connect(self.start_url_scraping)
        url_bar.addWidget(self.btn_url)
        url_bar.addStretch()
        layout.addLayout(url_bar)

        # --- progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat("%v%")
        layout.addWidget(self.progress_bar)

        # --- sorting controls ---
        sort_bar = QHBoxLayout()
        sort_bar.addWidget(QLabel("Sort by:"))
        self.col_combo = QComboBox()
        self.col_combo.addItems(COLUMNS)
        sort_bar.addWidget(self.col_combo)

        sort_bar.addWidget(QLabel("Algorithm:"))
        self.algo_combo = QComboBox()
        for name, info in sorting.ALGORITHMS.items():
            stable = "Stable" if info["stable"] else "Not stable"
            self.algo_combo.addItem(f"{name}  [{info['complexity']}, {stable}]", name)
        sort_bar.addWidget(self.algo_combo)

        self.order_combo = QComboBox()
        self.order_combo.addItems(["Ascending", "Descending"])
        sort_bar.addWidget(self.order_combo)

        sort_bar.addWidget(QLabel("Scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["Full dataset", "Filtered results only"])
        sort_bar.addWidget(self.scope_combo)

        self.btn_sort = QPushButton("Sort")
        self.btn_sort.clicked.connect(self.run_sort)
        sort_bar.addWidget(self.btn_sort)

        self.btn_multi = QPushButton("Multi-Level Sort")
        self.btn_multi.clicked.connect(self.run_multi_sort)
        sort_bar.addWidget(self.btn_multi)

        self.btn_bench = QPushButton("Benchmark")
        self.btn_bench.clicked.connect(self.run_benchmark)
        sort_bar.addWidget(self.btn_bench)
        sort_bar.addStretch()
        layout.addLayout(sort_bar)

        self.sort_label = QLabel("No sort performed yet")
        layout.addWidget(self.sort_label)

        # --- search controls ---
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Search in:"))
        self.s_col_combo = QComboBox()
        self.s_col_combo.addItems(COLUMNS)
        search_bar.addWidget(self.s_col_combo)

        self.s_op_combo = QComboBox()
        search_bar.addWidget(self.s_op_combo)

        self.s_value = QLineEdit()
        self.s_value.setPlaceholderText("Type a value...")
        self.s_value.setMinimumWidth(200)
        self.s_value.returnPressed.connect(self.run_search)
        search_bar.addWidget(self.s_value)

        search_bar.addWidget(QLabel("Algorithm (for exact match):"))
        self.s_algo_combo = QComboBox()
        for name, info in filters.SEARCH_ALGORITHMS.items():
            self.s_algo_combo.addItem(name)
        search_bar.addWidget(self.s_algo_combo)

        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.run_search)
        search_bar.addWidget(self.btn_search)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.clear_search)
        search_bar.addWidget(self.btn_clear)

        self.btn_composite = QPushButton("Composite Filter")
        self.btn_composite.clicked.connect(self.run_composite)
        search_bar.addWidget(self.btn_composite)
        search_bar.addStretch()
        layout.addLayout(search_bar)

        self.s_col_combo.currentIndexChanged.connect(self._on_search_col_changed)
        self._on_search_col_changed()

        self.search_label = QLabel("No search performed yet")
        layout.addWidget(self.search_label)

        # --- table ---
        self.model = BookTableModel(self.current_rows)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 170)
        layout.addWidget(self.table)

        # --- status line ---
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    # ---------- helpers ----------
    def _update_status(self, extra=""):
        text = f"Showing {len(self.current_rows)} of {len(self.all_rows)} books"
        if extra:
            text += "  |  " + extra
        self.status_label.setText(text)

    def _set_buttons(self, idle=False, running=False, paused=False):
        self.btn_start.setEnabled(idle)
        self.target_spin.setEnabled(idle)
        self.btn_url.setEnabled(idle)
        self.url_edit.setEnabled(idle)
        self.url_count.setEnabled(idle)
        self.btn_pause.setEnabled(running)
        self.btn_resume.setEnabled(paused)
        self.btn_stop.setEnabled(running or paused)

    def refresh_table(self, rows):
        """Show the given rows in the table."""
        self.current_rows = rows
        self.model.set_rows(rows)
        self._update_status()

    # ---------- scraping slots ----------
    def start_scraping(self):
        target = self.target_spin.value()
        self.worker = ScraperWorker(existing_rows=self.all_rows, target=target)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.progress_bar.setValue(min(100, int(len(self.all_rows) * 100 / target)))
        self.worker.start()
        self._set_buttons(running=True)
        self._update_status("Scraping started...")

    def start_url_scraping(self):
        try:
            query = query_from_url(self.url_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, "Scrape URL", str(e))
            return
        target = len(self.all_rows) + self.url_count.value()
        self.worker = ScraperWorker(existing_rows=self.all_rows, target=target,
                                    query=query, start_page=1)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.progress_bar.setValue(0)
        self.worker.start()
        self._set_buttons(running=True)
        self._update_status(f"Scraping URL query: {query}")

    def pause_scraping(self):
        if self.worker:
            self.worker.pause()
            self._set_buttons(paused=True)
            self._update_status("Paused")

    def resume_scraping(self):
        if self.worker:
            self.worker.resume()
            self._set_buttons(running=True)
            self._update_status("Scraping resumed...")

    def stop_scraping(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(False)
            self._update_status("Stopping and saving...")

    def on_progress(self, scraped, target):
        self.progress_bar.setValue(min(100, int(scraped * 100 / target)))
        self.status_label.setText(f"Scraped {scraped} / {target} books")

    def on_finished(self, rows):
        self.all_rows = rows
        self.refresh_table(rows)
        self._set_buttons(idle=True)
        self._update_status("Scraping finished, data saved to data/books.csv")

    def on_failed(self, message):
        QMessageBox.warning(self, "Scraping error", message)

    # ---------- sorting ----------
    def _confirm_slow(self, algo, count):
        """Ask before running an O(n^2) algorithm on a big dataset."""
        info = sorting.ALGORITHMS[algo]
        if info["slow"] and count > 3000:
            answer = QMessageBox.question(
                self, "Slow algorithm",
                f"{algo} is {info['complexity']} and {count} rows may take "
                "a very long time. Continue?",
                QMessageBox.Yes | QMessageBox.No)
            return answer == QMessageBox.Yes
        return True

    def run_sort(self):
        col = self.col_combo.currentIndex()
        algo = self.algo_combo.currentData()
        descending = self.order_combo.currentIndex() == 1
        full_scope = self.scope_combo.currentIndex() == 0
        rows = self.all_rows if full_scope else self.current_rows
        if not rows:
            return
        if not self._confirm_slow(algo, len(rows)):
            return

        info = sorting.ALGORITHMS[algo]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result, ms, stats = sorting.sort_rows(rows, col, algo, descending)
        finally:
            QApplication.restoreOverrideCursor()

        if full_scope:
            self.all_rows = result
        self.refresh_table(result)

        stable = "Yes" if info["stable"] else "No"
        self.sort_label.setText(
            f"{algo} on '{COLUMNS[col]}' ({len(rows)} rows)  |  "
            f"Time: {ms:.2f} ms  |  Comparisons: {stats.comparisons:,}  |  "
            f"Swaps: {stats.swaps:,}  |  Complexity: {info['complexity']}  |  "
            f"Stable: {stable}")

    def run_multi_sort(self):
        dialog = MultiSortDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        levels = dialog.get_levels()
        if not levels:
            QMessageBox.information(self, "Multi-Level Sort",
                                    "Please choose at least one column.")
            return
        algo = dialog.get_algo()
        full_scope = self.scope_combo.currentIndex() == 0
        rows = self.all_rows if full_scope else self.current_rows
        if not rows:
            return
        if not self._confirm_slow(algo, len(rows)):
            return

        info = sorting.ALGORITHMS[algo]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result, ms, stats = sorting.sort_rows_multi(rows, levels, algo)
        finally:
            QApplication.restoreOverrideCursor()

        if full_scope:
            self.all_rows = result
        self.refresh_table(result)

        desc = ", ".join(
            f"{COLUMNS[c]} {'DESC' if d else 'ASC'}" for c, d in levels)
        stable = "Yes" if info["stable"] else "No"
        self.sort_label.setText(
            f"Multi-level [{desc}] using {algo} ({len(rows)} rows)  |  "
            f"Time: {ms:.2f} ms  |  Comparisons: {stats.comparisons:,}  |  "
            f"Swaps: {stats.swaps:,}  |  Stable: {stable}")

    # ---------- benchmark ----------
    def run_benchmark(self):
        col = self.col_combo.currentIndex()
        full_scope = self.scope_combo.currentIndex() == 0
        rows = self.all_rows if full_scope else self.current_rows
        if not rows:
            return

        skip_slow = False
        if len(rows) > 3000:
            answer = QMessageBox.question(
                self, "Benchmark",
                f"{len(rows)} rows: the O(n^2) algorithms (Bubble, Selection, "
                "Insertion) may take several minutes.\n\n"
                "Yes = run all algorithms\nNo = skip the slow ones",
                QMessageBox.Yes | QMessageBox.No)
            skip_slow = answer == QMessageBox.No

        QApplication.setOverrideCursor(Qt.WaitCursor)
        results = []
        try:
            for name, info in sorting.ALGORITHMS.items():
                entry = {"name": name, "complexity": info["complexity"],
                         "stable": info["stable"], "time": None,
                         "comparisons": 0, "swaps": 0}
                if not (skip_slow and info["slow"]):
                    _, ms, stats = sorting.sort_rows(rows, col, name)
                    entry.update(time=ms, comparisons=stats.comparisons,
                                 swaps=stats.swaps)
                results.append(entry)
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

        dialog = BenchmarkDialog(results, COLUMNS[col], len(rows), self)
        dialog.exec_()

    # ---------- searching ----------
    def _on_search_col_changed(self):
        col = self.s_col_combo.currentIndex()
        self.s_op_combo.clear()
        if col in filters.NUMERIC_COLS:
            self.s_op_combo.addItems(filters.NUMERIC_OPS)
        else:
            self.s_op_combo.addItems(filters.STRING_OPS)

    def run_search(self):
        col = self.s_col_combo.currentIndex()
        op = self.s_op_combo.currentText()
        text = self.s_value.text()
        if not text.strip():
            QMessageBox.information(self, "Search", "Please type a value to search.")
            return
        try:
            value = filters.parse_value(col, text)
        except ValueError:
            QMessageBox.warning(self, "Search", "Please enter a valid number for this column.")
            return

        algo = self.s_algo_combo.currentText()
        exact = op in ("equals", "=")
        if exact:
            if algo == "Interpolation Search" and col not in filters.NUMERIC_COLS:
                QMessageBox.warning(
                    self, "Search",
                    "Interpolation Search works only on numeric columns.")
                return
            result, ms, comps = filters.exact_search(self.all_rows, col, value, algo)
            used = f"{algo} [{filters.SEARCH_ALGORITHMS[algo]['complexity']}]"
        else:
            result, ms, comps = filters.apply_filter(self.all_rows, col, op, value)
            used = "Linear scan filter [O(n)]"

        self.refresh_table(result)
        self.search_label.setText(
            f"{used} on '{COLUMNS[col]}' {op} '{text.strip()}'  |  "
            f"Matches: {len(result):,}  |  Time: {ms:.3f} ms  |  "
            f"Comparisons: {comps:,}")

    def clear_search(self):
        self.s_value.clear()
        self.refresh_table(self.all_rows)
        self.search_label.setText("Search cleared")

    def run_composite(self):
        dialog = CompositeDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        conditions = dialog.get_conditions()
        if not conditions:
            QMessageBox.information(self, "Composite Filter",
                                    "Please fill at least one condition.")
            return

        result, ms, evals = filters.apply_composite(self.all_rows, conditions)
        self.refresh_table(result)

        parts = []
        for i, (conn, neg, col, op, val) in enumerate(conditions):
            text = f"{'NOT ' if neg else ''}{COLUMNS[col]} {op} '{val}'"
            parts.append(text if i == 0 else f"{conn} {text}")
        self.search_label.setText(
            f"Composite filter: {' '.join(parts)}  |  "
            f"Matches: {len(result):,}  |  Time: {ms:.3f} ms  |  "
            f"Evaluations: {evals:,}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        event.accept()