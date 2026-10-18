from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QCheckBox,
    QLineEdit, QDialogButtonBox, QMessageBox,
)

import filters
from scraper import COLUMNS


class CompositeDialog(QDialog):
    """Build a filter from up to 4 conditions joined by AND / OR, with NOT."""

    ROWS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Composite Filter (AND / OR / NOT)")
        self.resize(780, 280)
        layout = QVBoxLayout(self)

        grid = QGridLayout()
        self.conn_boxes, self.not_boxes = [], []
        self.col_boxes, self.op_boxes, self.value_edits = [], [], []

        for i in range(self.ROWS):
            if i == 0:
                grid.addWidget(QLabel("Where"), i, 0)
                self.conn_boxes.append(None)
            else:
                conn = QComboBox()
                conn.addItems(["AND", "OR"])
                grid.addWidget(conn, i, 0)
                self.conn_boxes.append(conn)

            not_box = QCheckBox("NOT")
            col_box = QComboBox()
            col_box.addItems(COLUMNS)
            op_box = QComboBox()
            value_edit = QLineEdit()
            value_edit.setPlaceholderText("Leave empty to ignore this row")

            grid.addWidget(not_box, i, 1)
            grid.addWidget(col_box, i, 2)
            grid.addWidget(op_box, i, 3)
            grid.addWidget(value_edit, i, 4)

            self.not_boxes.append(not_box)
            self.col_boxes.append(col_box)
            self.op_boxes.append(op_box)
            self.value_edits.append(value_edit)

            col_box.currentIndexChanged.connect(
                lambda _=None, k=i: self._update_ops(k))
            self._update_ops(i)

        grid.setColumnStretch(4, 1)
        layout.addLayout(grid)

        layout.addWidget(QLabel(
            "Rules: AND is evaluated before OR.  Example: A OR B AND C = "
            "A OR (B AND C).  NOT reverses that one condition."))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_ops(self, i):
        col = self.col_boxes[i].currentIndex()
        self.op_boxes[i].clear()
        if col in filters.NUMERIC_COLS:
            self.op_boxes[i].addItems(filters.NUMERIC_OPS)
        else:
            self.op_boxes[i].addItems(filters.STRING_OPS)

    def _validate_and_accept(self):
        try:
            self.get_conditions()
        except ValueError:
            QMessageBox.warning(self, "Composite Filter",
                                "A numeric column needs a valid number.")
            return
        self.accept()

    def get_conditions(self):
        """Returns [(connector, negate, col, op, parsed_value), ...]."""
        conditions = []
        for i in range(self.ROWS):
            text = self.value_edits[i].text().strip()
            if not text:
                continue
            col = self.col_boxes[i].currentIndex()
            op = self.op_boxes[i].currentText()
            value = filters.parse_value(col, text)
            connector = "AND"
            if self.conn_boxes[i] is not None:
                connector = self.conn_boxes[i].currentText()
            conditions.append(
                (connector, self.not_boxes[i].isChecked(), col, op, value))
        return conditions