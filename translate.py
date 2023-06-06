# -*- coding: utf-8 -*-

import pyperclip
from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_translateWindow(QtWidgets.QMainWindow):
    dragPos = QtCore.QPoint()

    def copy_clipboard(self, event):
        text = self.translated_text_label.text().strip()
        print(f"Clipboard copy: [{text}]")
        pyperclip.copy(text)

    def __init__(self, opacity_slider, window_opacity_slider):
        super().__init__()
        self.setObjectName("translateWindow")
        self.resize(800, 161)

        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")

        self.translated_text_label = QtWidgets.QLabel(self.centralwidget)
        self.translated_text_label.setStyleSheet("background-color: transparent;")
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")
        self.translated_text_label.setAlignment(QtCore.Qt.AlignCenter)

        self.opacity_effect_text_label = QtWidgets.QGraphicsOpacityEffect()
        self.opacity_effect_text_label.setOpacity(opacity_slider.value() / 100)
        self.translated_text_label.setGraphicsEffect(self.opacity_effect_text_label)

        self.gridLayout.addWidget(self.translated_text_label, 0, 0, 1, 1)

        font = QtGui.QFont()
        font.setPointSize(12)

        self.translated_text_label.setFont(font)
        self.translated_text_label.setAlignment(QtCore.Qt.AlignCenter)
        self.translated_text_label.setObjectName("translated_text_label")
        self.translated_text_label.setWordWrap(True)
        #self.translated_text_label.mousePressEvent = self.copy_clipboard

        self.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(self)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")

        self.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)

        self.retranslateUi()
        QtCore.QMetaObject.connectSlotsByName(self)

        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        #self.setWindowOpacity(opacity_slider.value() / 100)
        self.setStyleSheet("background-color: rgba(0, 0, 0, " + str(window_opacity_slider.value() / 100) + ");")
        #self.setAttribute(QtCore.Qt.WA_NoSystemBackground)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        for w in self.findChildren(QtWidgets.QWidget) + [self]:
            w.installEventFilter(self)

    def set_worker(self, worker):
        self.worker = worker

    def retranslateUi(self):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate("translateWindow", "DeskTranslator - Translating"))
        self.translated_text_label.setText(_translate("translateWindow", "Translated text here"))

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.copy_clipboard(event)
            self.dragPos = event.globalPos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self.dragPos)
            self.dragPos = event.globalPos()
            event.accept()

    def closeEvent(self, event):
        self.worker.stop_running()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    translateWindow = QtWidgets.QMainWindow()
    ui = Ui_translateWindow()
    ui.setupUi(translateWindow)
    translateWindow.show()
    sys.exit(app.exec_())
