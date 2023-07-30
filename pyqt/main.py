# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '.\main.ui'
#
# Created by: PyQt5 UI code generator 5.15.2
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.

import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from translate import Ui_translateWindow
from PyQt5.QtWidgets import QColorDialog, QSizePolicy

with open("countries/language-codes-3b2.csv") as f:
    arr = [line.split() for line in f]

dict = {}

length = len(arr)

list_frm1 = []

for i in range(1, length):
    country = arr[i][0].replace(';', '').replace('"', '').split(',')
    name = country[2]
    list_frm1.append(name)
    threeLetterCode = country[0]
    dict[name] = threeLetterCode

with open("countries/tesseract_lang.csv") as file:
    arr1 = [line.split() for line in file]

dict1 = {}

length1 = len(arr1)

list_frm2 = []

for i in range(1, length1):
    country = arr1[i][0].replace(';', '').replace('"', '').split(',')
    name = country[1]
    list_frm2.append(name)
    twoLetterCode = country[0]
    dict1[name] = twoLetterCode


class Ui_MainWindow(object):

    def openTranslateWin(self):
        self.translateWindow = QtWidgets.QMainWindow()
        self.ui = Ui_translateWindow()
        self.ui.setupUi(self.translateWindow)
        self.translateWindow.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint |
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.translateWindow.setWindowOpacity(self.opacity_slider.value() / 100)
        self.translateWindow.show()

    def opacity_changed(self):
        new_opacity_value = self.opacity_slider.value()
        self.opacity_2_label.setText(str(new_opacity_value))

        try:
            self.translateWindow.setWindowOpacity(self.opacity_slider.value() / 100)
        except:
            print("Trying to edit opacity")

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(430, 275)
        MainWindow.setWindowIcon(QtGui.QIcon("./images/DeskTranslate.ico"))
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")

        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setGeometry(QtCore.QRect(0, 0, 431, 251))
        self.tabWidget.setObjectName("tabWidget")

        self.tab_welcome = QtWidgets.QWidget()
        self.tab_welcome.setObjectName("tab_welcome")

        self.gridLayout_2 = QtWidgets.QGridLayout(self.tab_welcome)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.home_label = QtWidgets.QLabel(self.tab_welcome)
        self.home_label.setGeometry(QtCore.QRect(30, 0, 371, 191))
        self.home_label.setAlignment(QtCore.Qt.AlignCenter)
        self.home_label.setObjectName("home_label")
        self.gridLayout_2.addWidget(self.home_label, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_welcome, "")

        self.tab_translate = QtWidgets.QWidget()
        self.tab_translate.setObjectName("tab_translate")
        self.gridLayout_8 = QtWidgets.QGridLayout(self.tab_translate)
        self.gridLayout_8.setObjectName("gridLayout_8")
        self.gridLayout_7 = QtWidgets.QGridLayout()
        self.gridLayout_7.setObjectName("gridLayout_7")
        self.label = QtWidgets.QLabel(self.tab_translate)
        self.label.setMinimumSize(QtCore.QSize(300, 0))
        self.label.setMaximumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        self.gridLayout_7.addWidget(self.label, 0, 0, 1, 1)
        self.gridLayout_6 = QtWidgets.QGridLayout()
        self.gridLayout_6.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.frm_label = QtWidgets.QLabel(self.tab_translate)
        self.frm_label.setMaximumSize(QtCore.QSize(67, 16777215))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.frm_label.setFont(font)
        self.frm_label.setObjectName("frm_label")

        self.gridLayout_6.addWidget(self.frm_label, 0, 0, 1, 1)

        self.frm_dropdown = QtWidgets.QComboBox(self.tab_translate)
        self.frm_dropdown.setMaximumSize(QtCore.QSize(407, 16777215))
        self.frm_dropdown.setObjectName("frm_dropdown")

        self.gridLayout_6.addWidget(self.frm_dropdown, 0, 1, 1, 1)

        self.to_label = QtWidgets.QLabel(self.tab_translate)
        self.to_label.setMaximumSize(QtCore.QSize(67, 16777215))

        # add language list for original text
        self.frm_dropdown.addItems(list_frm1)

        font = QtGui.QFont()
        font.setPointSize(16)
        self.to_label.setFont(font)
        self.to_label.setObjectName("to_label")

        self.gridLayout_6.addWidget(self.to_label, 1, 0, 1, 1)

        self.to_dropdown = QtWidgets.QComboBox(self.tab_translate)
        self.to_dropdown.setMaximumSize(QtCore.QSize(407, 16777215))
        self.to_dropdown.setObjectName("to_dropdown")

        self.gridLayout_6.addWidget(self.to_dropdown, 1, 1, 1, 1)
        self.gridLayout_6.setColumnStretch(0, 1)
        self.gridLayout_6.setColumnStretch(1, 2)
        self.gridLayout_7.addLayout(self.gridLayout_6, 1, 0, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setContentsMargins(6, -1, 6, -1)
        self.horizontalLayout.setObjectName("horizontalLayout")

        self.select_borders_btn = QtWidgets.QPushButton(self.tab_translate)
        self.select_borders_btn.setMaximumSize(QtCore.QSize(238, 16777215))
        font = QtGui.QFont()
        font.setPointSize(10)
        self.select_borders_btn.setFont(font)
        self.select_borders_btn.setAutoDefault(False)
        self.select_borders_btn.setObjectName("select_borders_btn")
        self.select_borders_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.label = QtWidgets.QLabel(self.tab_translate)
        self.label.setGeometry(QtCore.QRect(100, 20, 211, 31))
        self.label.setMaximumSize(QtCore.QSize(400, 40))

        self.translate_btn = QtWidgets.QPushButton(self.tab_translate)
        # self.translate_btn.setGeometry(QtCore.QRect(220, 170, 161, 41))
        font = QtGui.QFont()
        font.setPointSize(10)

        self.translate_btn.clicked.connect(self.openTranslateWin)
        self.translate_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.translate_btn.setFont(font)
        self.translate_btn.setAutoDefault(False)
        self.translate_btn.setObjectName("translate_btn")

        self.horizontalLayout.addWidget(self.translate_btn)
        self.horizontalLayout.setStretch(0, 1)
        self.horizontalLayout.setStretch(1, 1)
        self.gridLayout_7.addLayout(self.horizontalLayout, 2, 0, 1, 1)
        self.gridLayout_8.addLayout(self.gridLayout_7, 0, 0, 1, 1)

        # add language list for translation text
        self.to_dropdown.addItems(list_frm2)

        self.horizontalLayout.addWidget(self.select_borders_btn)
        self.translate_btn = QtWidgets.QPushButton(self.tab_translate)
        self.translate_btn.setMaximumSize(QtCore.QSize(237, 16777215))

        font = QtGui.QFont()
        font.setPointSize(16)
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        self.tabWidget.addTab(self.tab_translate, "")

        self.tab_settings = QtWidgets.QWidget()
        self.tab_settings.setObjectName("tab_settings")

        self.gridLayout_5 = QtWidgets.QGridLayout(self.tab_settings)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.gridLayout_4 = QtWidgets.QGridLayout()
        self.gridLayout_4.setObjectName("gridLayout_4")

        self.settings_font_label = QtWidgets.QLabel(self.tab_settings)
        self.settings_font_label.setMinimumSize(QtCore.QSize(0, 37))
        self.settings_font_label.setMaximumSize(QtCore.QSize(16777215, 37))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.settings_font_label.setFont(font)
        self.settings_font_label.setObjectName("settings_font_label")

        self.gridLayout_4.addWidget(self.settings_font_label, 0, 0, 1, 1)
        self.gridLayout_3 = QtWidgets.QGridLayout()
        self.gridLayout_3.setObjectName("gridLayout_3")

        self.size_label = QtWidgets.QLabel(self.tab_settings)
        self.size_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.size_label.setFont(font)
        self.size_label.setObjectName("size_label")
        self.gridLayout_3.addWidget(self.size_label, 0, 0, 1, 1)
        self.size_dropdown = QtWidgets.QComboBox(self.tab_settings)
        self.size_dropdown.setMaximumSize(QtCore.QSize(374, 16777215))
        self.size_dropdown.setCurrentText("")
        self.size_dropdown.setObjectName("size_dropdown")

        self.gridLayout_3.addWidget(self.size_dropdown, 0, 1, 1, 1)

        # dropdown for font size
        font_size_range = list(range(8, 45))
        self.size_dropdown.addItems(list(map(str, font_size_range)))

        self.opacity_label = QtWidgets.QLabel(self.tab_settings)
        self.opacity_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.opacity_label.setFont(font)
        self.opacity_label.setObjectName("opacity_label")

        self.gridLayout_3.addWidget(self.opacity_label, 1, 0, 1, 1)
        self.opacity_slider = QtWidgets.QSlider(self.tab_settings)
        self.opacity_slider.setMaximumSize(QtCore.QSize(374, 16777215))
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setProperty("value", 100)
        self.opacity_slider.setOrientation(QtCore.Qt.Horizontal)
        self.opacity_slider.setObjectName("opacity_slider")
        self.gridLayout_3.addWidget(self.opacity_slider, 1, 1, 1, 1)

        # opacity slider value changed
        self.opacity_slider.valueChanged.connect(self.opacity_changed)

        self.opacity_2_label = QtWidgets.QLabel(self.tab_settings)
        self.opacity_2_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.opacity_2_label.setFont(font)
        self.opacity_2_label.setObjectName("opacity_2_label")

        self.gridLayout_3.addWidget(self.opacity_2_label, 1, 2, 1, 1)

        self.opacity_label_2 = QtWidgets.QLabel(self.tab_settings)
        self.opacity_label_2.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.opacity_label_2.setFont(font)
        self.opacity_label_2.setObjectName("opacity_label_2")

        self.gridLayout_3.addWidget(self.opacity_label_2, 2, 0, 1, 1)
        self.select_color_btn = QtWidgets.QPushButton(self.tab_settings)
        self.select_color_btn.setMaximumSize(QtCore.QSize(374, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.select_color_btn.setFont(font)
        self.select_color_btn.setObjectName("select_color_btn")
        self.select_color_btn.setToolTip('Opens color dialog')
        self.select_color_btn.setAutoDefault(False)
        self.select_color_btn.clicked.connect(self.on_click_color_btn)
        self.select_borders_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.gridLayout_3.addWidget(self.select_color_btn, 2, 1, 1, 1)
        self.gridLayout_4.addLayout(self.gridLayout_3, 1, 0, 1, 1)
        self.gridLayout_4.setRowStretch(0, 1)
        self.gridLayout_4.setRowStretch(1, 5)
        self.gridLayout_5.addLayout(self.gridLayout_4, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_settings, "")
        self.gridLayout.addWidget(self.tabWidget, 1, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 438, 22))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(1)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def on_click_color_btn(self):
        openColorDialog(self)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "DeskTranslator v1.0"))
        self.home_label.setText(_translate("MainWindow", "<html><head/><body><p align=\"center\"><a name=\"docs-internal-guid-25bb1131-7fff-63a2-64a4-c6962f5bb8c4\"/><span style=\" font-family:\'Arial\'; font-size:12pt; color:white; background-color:transparent;\">H</span><span style=\" font-family:\'Arial\'; font-size:12pt; color:#FFFFFF; background-color:transparent;\">ello there!</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">DeskTranslator is a live OCR translation tool for your desktop. </span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">To use tool, simply:</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">1. Click on the Translate tab</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">2. Select the language you want to translate from</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">3. Select the language you want to translate to</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">4. Select the Borders of the screen area you want the translator to process</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">5. Click the Translate button to start the translation</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">Additionally, you can adjust the font size and color to your liking. </span></p></body></html>"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_welcome), _translate("MainWindow", "Home"))
        self.frm_label.setText(_translate("MainWindow", "From:"))
        self.to_label.setText(_translate("MainWindow", "To:"))
        self.translate_btn.setText(_translate("MainWindow", "Translate"))
        self.select_borders_btn.setText(_translate("MainWindow", "Select borders"))
        self.label.setText(_translate("MainWindow", "Select language"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_translate), _translate("MainWindow", "Translate"))
        self.settings_font_label.setText(_translate("MainWindow", "<html><head/><body><p><span style=\" font-size:14pt;\">Font</span></p></body></html>"))
        self.size_label.setText(_translate("MainWindow", "Size"))
        self.opacity_label.setText(_translate("MainWindow", "Opacity"))
        self.opacity_2_label.setText(_translate("MainWindow", "100"))
        self.select_color_btn.setText(_translate("MainWindow", "Select color"))
        self.opacity_label_2.setText(_translate("MainWindow", "Color"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_settings), _translate("MainWindow", "Settings"))

def openColorDialog(self):
    color = QColorDialog.getColor()

    if color.isValid():
        print(color.name())

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    file = open("./images/ManjaroMix.qss", "r")

    with file:
        qss = file.read()
        app.setStyleSheet(qss)

    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())