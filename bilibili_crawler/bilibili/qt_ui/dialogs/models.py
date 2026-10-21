"""表格数据模型和单元格绘制委托。"""

from PySide6.QtCore import (
    QAbstractTableModel,
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPalette,
)
from PySide6.QtWidgets import (
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidgetItem,
)

from qt_ui.formatting import (
    NUMBER_COLUMNS,
)


class PreviewTableModel(QAbstractTableModel):
    """按需向表格视图提供数据，支持筛选和排序。"""

    def __init__(
        self,
        headers,
        rows,
        parent=None,
        full_rows=None,
        sort_keys=None,
        raw_headers=None,
    ):
        super().__init__(parent)
        self.headers = headers
        self.raw_headers = raw_headers or headers
        self._display = rows
        self._full = full_rows or rows
        self._sort = sort_keys or [list(row) for row in rows]
        self._view = list(range(len(self._display)))
        self._sort_column = None
        self._sort_order = Qt.SortOrder.AscendingOrder
        self.numeric_columns = {
            index
            for index, header in enumerate(self.raw_headers)
            if header in NUMBER_COLUMNS
        }

    def rowCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return len(self._view)

    def columnCount(self, parent=None):
        if parent is not None and parent.isValid():
            return 0

        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = self._view[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display[row][column]

        if role == Qt.ItemDataRole.ToolTipRole:
            value = self._full[row][column]

            if self.raw_headers[column] == "cover_url":
                return f"点击打开封面\n{value}"

            return value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in self.numeric_columns:
                return int(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )

            return int(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            )

        return None

    def headerData(
        self,
        section,
        orientation,
        role=Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section]

        return section + 1

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if not self._view or column < 0 or column >= len(self.headers):
            return

        self._sort_column = column
        self._sort_order = order

        self.beginResetModel()
        self._apply_sort()
        self.endResetModel()

    def set_filter(self, text):
        """按关键字筛选，命中任意一列即保留。返回筛选后的行数。"""
        text = str(text or "").strip().casefold()

        self.beginResetModel()

        if not text:
            self._view = list(range(len(self._display)))
        else:
            self._view = [
                index
                for index, row in enumerate(self._display)
                if any(text in str(cell).casefold() for cell in row)
            ]

        self._apply_sort()
        self.endResetModel()
        return len(self._view)

    def _apply_sort(self):
        column = self._sort_column

        if column is None:
            return

        self._view.sort(
            key=lambda row: self._sort[row][column],
            reverse=self._sort_order == Qt.SortOrder.DescendingOrder,
        )

    def full_row(self, row):
        """返回视图第 `row` 行对应的完整内容（未经截断）。"""
        return self._full[self._view[row]]

    def full_value(self, row, column):
        return self._full[self._view[row]][column]


class SortableTableWidgetItem(QTableWidgetItem):
    """用显式排序键比较表格项，保证时间等字段按真实值排序。"""

    def __init__(self, text="", sort_key=None):
        super().__init__(text)
        self.sort_key = text.casefold() if sort_key is None else sort_key

    def __lt__(self, other):
        if not isinstance(other, SortableTableWidgetItem):
            return super().__lt__(other)

        return self.sort_key < other.sort_key


class LinkItemDelegate(QStyledItemDelegate):
    """给链接列增加颜色、下划线和悬浮反馈。"""

    link_column: int | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.link_column = None

    def paint(self, painter, option, index):
        if index.column() != self.link_column:
            super().paint(painter, option, index)
            return

        styled = QStyleOptionViewItem(option)
        font = styled.font
        font.setUnderline(True)
        styled.font = font
        hovered = bool(
            styled.state & QStyle.StateFlag.State_MouseOver
        )
        color = QColor("#e95482" if hovered else "#2f6feb")
        styled.palette.setColor(QPalette.ColorRole.Text, color)
        styled.palette.setColor(QPalette.ColorRole.HighlightedText, color)

        if hovered:
            styled.backgroundBrush = QBrush(QColor("#fff0f5"))

        super().paint(painter, styled, index)


