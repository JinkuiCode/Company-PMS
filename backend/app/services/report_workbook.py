"""Row-streamed Excel files with explicit strings and automatic sheet rollover."""
from datetime import date, datetime
from decimal import Decimal
import xlsxwriter


class ReportWorkbook:
    def __init__(self, path, row_limit=1048576):
        self.book = xlsxwriter.Workbook(str(path), {'constant_memory': True,
            'strings_to_formulas': False, 'strings_to_urls': False})
        self.book.use_zip64()
        self.row_limit = row_limit
        self.header = self.book.add_format({'bold': True, 'bg_color': '#EEF0F6'})

    def sheet(self, name, fields):
        return ReportSheet(self, name, fields)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.book.close()


class ReportSheet:
    def __init__(self, owner, name, fields):
        self.owner, self.name, self.fields = owner, name, fields
        self.part = 0
        self._next()

    def _next(self):
        self.part += 1
        suffix = '' if self.part == 1 else f'-{self.part}'
        self.sheet = self.owner.book.add_worksheet(self.name[:31-len(suffix)] + suffix)
        self.sheet.freeze_panes(1, 0)
        self.sheet.set_column(0, len(self.fields)-1, 22)
        self.sheet.write_row(0, 0, [label for _, label in self.fields], self.owner.header)
        self.row = 1

    def append(self, values):
        if self.row >= self.owner.row_limit:
            self._next()
        for column, (key, _) in enumerate(self.fields):
            value = values.get(key)
            if value is None:
                continue
            if isinstance(value, (date, datetime)):
                value = value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                # Preserve long identifiers/decimal precision rather than Excel's 15-digit rounding.
                if len(str(value).replace('.', '').replace('-', '')) <= 15:
                    result = self.sheet.write_number(self.row, column, float(value))
                else:
                    result = self.sheet.write_string(self.row, column, str(value))
            else:
                result = self.sheet.write_string(self.row, column, str(value))
            if result != 0:
                raise ValueError('单元格内容超出Excel限制，未生成截断文件')
        self.row += 1
