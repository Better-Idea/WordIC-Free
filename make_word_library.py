import sys
import json
from PyQt5.Qt import QIntValidator
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import                                 \
    QApplication, QMainWindow, QWidget, QTableWidget,       \
    QCheckBox, QTableWidgetItem, QLineEdit, QStackedLayout, \
    QPushButton, QHBoxLayout, QVBoxLayout, QHeaderView,     \
    QComboBox, QMessageBox, QLabel
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QFontMetrics, QFontDatabase

def generate(path, font_name, font_size, interval):
    w                   = font_size
    font                = QFont(font_name, font_size)
    app                 = QApplication(sys.argv)
    bmp                 = QPixmap(w * 256, w * 256)
    painter             = QPainter(bmp)
    bmp.fill()
    painter.setPen(Qt.black)
    painter.setFont(font)

    ary                 = bytearray('\x00\x00', 'utf-8')

    for i in range(interval[0], interval[1] + 1):
        ary[0]          = (i & 0xff)
        ary[1]          = (i >> 8)
        x               = (i & 0xff) << 4
        y               = (i >> 8) << 4

        try:
            v = ary.decode('utf-16')
        except Exception:
            continue

        painter.drawText(x, y, w, w, Qt.AlignHCenter | Qt.AlignLeft, v)
    bmp.save(path)

def main():
    app                 = QApplication(sys.argv)

    font                = QFont()
    font.setPixelSize(24)
    lab_font            = QLabel('font:')
    lab_font.setFont(font)

    font_list           = QComboBox()
    font_list.setFixedHeight(32)

    for font in QFontDatabase().families():
        font_list.addItem(font)

    # unicode list
    try:
        file_ini = 'unicode.json'
        with open(file_ini, 'r') as ini:
            tab = json.loads(ini.read())
    except Exception:
        box = QMessageBox()
        box.setText('file %s read failure!' % file_ini)
        box.show()
        app.exec()
        return

    font_size_rule      = QIntValidator(4, 100)
    qtab                = QTableWidget(len(tab), 5)
    qtab.setHorizontalHeaderLabels(['', 'range', 'type', '类型', 'font-size'])
    qtabh               = qtab.horizontalHeader()
    qtabh.setDefaultAlignment(Qt.AlignCenter)
    qtabh.setStretchLastSection(True)
    qtabh.sectionResizeMode(QHeaderView.Stretch)
    qtab.setColumnWidth(0, 32)
    qtab.setColumnWidth(2, 256)
    qtab.setColumnWidth(3, 160)

    for row, row_data in zip(range(0, len(tab)), tab):
        check           = QCheckBox()
        item_check      = QWidget()
        item_range      = QTableWidgetItem()
        item_type       = QTableWidgetItem()
        item_type_cn    = QTableWidgetItem()
        item_font_size  = QLineEdit()
        lyo_hbox        = QHBoxLayout(item_check)
        lyo_hbox.setAlignment(Qt.AlignCenter)
        lyo_hbox.addWidget(check)

        if  row_data[0] != '0':
            check.setCheckState(Qt.Checked)

        item_range.setText(row_data[1])
        item_type.setText(row_data[2])
        item_type_cn.setText(row_data[3])
        item_font_size.setText(row_data[4]) # default font size is 16 pixel
        item_font_size.setValidator(font_size_rule)

        item_range.setTextAlignment(Qt.AlignCenter)
        item_type.setTextAlignment(Qt.AlignCenter)
        item_type_cn.setTextAlignment(Qt.AlignCenter)

        qtab.setCellWidget(row, 0, item_check)
        qtab.setItem(row, 1, item_range)
        qtab.setItem(row, 2, item_type)
        qtab.setItem(row, 3, item_type_cn)
        qtab.setCellWidget(row, 4, item_font_size)

    btn_gen             = QPushButton('generate')
    btn_gen.setFixedHeight(64)

    main_layout         = QVBoxLayout()
    main_layout.addWidget(lab_font)
    main_layout.addWidget(font_list)
    main_layout.addWidget(qtab)
    main_layout.addWidget(btn_gen)

    widget              = QWidget()
    widget.setMinimumHeight(600)
    widget.setMinimumWidth(800)
    widget.setLayout(main_layout)
    widget.show()

    app.exec()

# call main
main()
