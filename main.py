# -*- coding: utf-8 -*-

import sys
import ctypes
from threading import Thread

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QColorDialog, QSizePolicy, QMessageBox, QLabel, QApplication

from helpers import screen_reader, splashscreen, translate

with open("languageLists/fromLanguage.csv") as f:
    arr = [line.split(',') for line in f]

dict = {}

length = len(arr)

list_frm2 = []

for i in range(0, length):
    country = arr[i]
    name = country[0]
    list_frm2.append(name)
    threeLetterCode = country[1].replace('\n', '')
    dict[name] = threeLetterCode

with open("languageLists/toLanguage.csv") as file:
    arr1 = [line.split(',') for line in file]

dict1 = {}

length1 = len(arr1)

list_frm1 = []

for i in range(0, length1):
    country = arr1[i]
    name = country[0]
    list_frm1.append(name)
    twoLetterCode = country[1].replace('\n', '')
    dict1[name] = twoLetterCode


class Ui_MainWindow(object):
    translator_engine = "GoogleTranslator"

    def on_click_select_borders(self):
        global borders_selected
        borders_selected = True
        QtWidgets.QApplication.setOverrideCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.CrossCursor)
        )
        snip_window.show()

    def on_click_openTranslateWin(self):
        if not borders_selected:
            QMessageBox.information(None, "Please Select Borders",
                                    "<html><body><p style='color: black;'>Please select the borders first!</p></body></html>")
            return

        # Thread execution point
        print("Launching a worker thread...")
        if self.thread is not None:
            self.ui.close()
            self.thread.join()

        self.ui = translate.Ui_translateWindow(self.opacity_slider)
        self.ui.show()
        img_lang = self.frm_dropdown.currentText()
        trans_lang = self.to_dropdown.currentText()
        img_code = dict.get(img_lang)
        trans_code = dict1.get(trans_lang)
        print(img_code, trans_code)
        is_text2speech_enabled = self.checkBox.isChecked()
        self.worker = screen_reader.Worker(snip_window,
                             img_code, trans_code,
                             is_text2speech_enabled,
                             self.ui, self.translator_engine,
                             img_lang, trans_lang)
        self.ui.set_worker(self.worker)
        self.thread = Thread(target=self.worker.run)
        self.thread.start()
        print("Launched!")

    def on_click_font_size_changed(self, value):
        font = QtGui.QFont()
        font.setPointSize(int(value))
        try:
            self.ui.translated_text_label.setFont(font)
        except:
            print("Trying to edit text size")

    def on_click_opacity_changed(self):
        new_opacity_value = self.opacity_slider.value()
        self.opacity_2_label.setText(str(new_opacity_value))

        try:
            self.ui.setWindowOpacity(self.opacity_slider.value() / 100)
        except:
            print("Trying to edit opacity")

    def on_click_color_btn(self):
        newColor = QColorDialog.getColor()
        if newColor.isValid():
            print(newColor.name())
            self.color_changed(newColor)

    def color_changed(self, color):
        print(color.name())
        try:
            self.ui.translated_text_label.setStyleSheet("color: " + color.name() + ";")
        except:
            print("Trying to change color")

    def on_click_engine_changed(self, value):
        self.translator_engine = value

    def setupUi(self, MainWindow):
        self.thread = None
        self.worker = None

        myappid = u'DeskTranslate.version1.1'  # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(430, 275)
        MainWindow.setWindowIcon(QtGui.QIcon("./images/DeskTranslate.ico"))
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # create label
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(25, 25, 200, 200))
        self.label.setMinimumSize(QtCore.QSize(200, 200))
        self.label.setMaximumSize(QtCore.QSize(200, 200))
        self.label.setObjectName("label")

        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName("gridLayout")

        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        #        self.tabWidget.setGeometry(QtCore.QRect(0, 0, 431, 251))
        self.tabWidget.setObjectName("tabWidget")

        self.tab_translate = QtWidgets.QWidget()
        self.tab_translate.setObjectName("tab_translate")
        self.gridLayout_8 = QtWidgets.QGridLayout(self.tab_translate)
        self.gridLayout_8.setObjectName("gridLayout_8")
        self.gridLayout_7 = QtWidgets.QGridLayout()
        self.gridLayout_7.setObjectName("gridLayout_7")

        self.language_label = QtWidgets.QLabel(self.tab_translate)
        self.language_label.setMinimumSize(QtCore.QSize(476, 0))
        self.language_label.setMaximumSize(QtCore.QSize(0, 40))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.language_label.setFont(font)
        self.language_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.language_label.setObjectName("label")

        self.gridLayout_7.addWidget(self.language_label, 0, 0, 1, 1)
        self.gridLayout_6 = QtWidgets.QGridLayout()
        self.gridLayout_6.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetFixedSize)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.frm_label = QtWidgets.QLabel(self.tab_translate)
        self.frm_label.setMaximumSize(QtCore.QSize(67, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
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
        self.frm_dropdown.addItems(list_frm2)

        font = QtGui.QFont()
        font.setPointSize(12)
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
        self.select_borders_btn.setMaximumSize(QtCore.QSize(238, 115))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.select_borders_btn.setFont(font)
        self.select_borders_btn.setAutoDefault(False)
        self.select_borders_btn.setObjectName("select_borders_btn")
        self.select_borders_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.select_borders_btn.clicked.connect(self.on_click_select_borders)

        # add language list for translation text
        self.to_dropdown.addItems(list_frm1)

        self.horizontalLayout.addWidget(self.select_borders_btn)
        self.translate_btn = QtWidgets.QPushButton(self.tab_translate)
        self.translate_btn.setMaximumSize(QtCore.QSize(238, 115))
        font = QtGui.QFont()
        font.setPointSize(12)

        self.translate_btn.clicked.connect(self.on_click_openTranslateWin)
        self.translate_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.translate_btn.setFont(font)
        self.translate_btn.setAutoDefault(False)
        self.translate_btn.setObjectName("translate_btn")

        self.horizontalLayout.addWidget(self.translate_btn)
        self.horizontalLayout.setStretch(0, 1)
        self.horizontalLayout.setStretch(1, 1)
        self.gridLayout_7.addLayout(self.horizontalLayout, 2, 0, 1, 1)
        self.gridLayout_8.addLayout(self.gridLayout_7, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_translate, "")

        self.tab_settings = QtWidgets.QWidget()
        self.tab_settings.setObjectName("tab_settings")

        self.gridLayout_4 = QtWidgets.QGridLayout(self.tab_settings)
        self.gridLayout_4.setObjectName("gridLayout_4")

        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")

        self.settings_font_label = QtWidgets.QLabel(self.tab_settings)
        self.settings_font_label.setMinimumSize(QtCore.QSize(0, 37))
        self.settings_font_label.setMaximumSize(QtCore.QSize(16777215, 37))
        font = QtGui.QFont()
        font.setPointSize(16)
        self.settings_font_label.setFont(font)
        #        self.settings_font_label.setAlignment(QtCore.Qt.AlignCenter)
        self.settings_font_label.setObjectName("settings_font_label")

        self.verticalLayout.addWidget(self.settings_font_label)

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
        self.size_dropdown.currentTextChanged.connect(self.on_click_font_size_changed)

        self.opacity_label = QtWidgets.QLabel(self.tab_settings)
        self.opacity_label.setMaximumSize(QtCore.QSize(90, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.opacity_label.setFont(font)
        self.opacity_label.setObjectName("opacity_label")

        self.gridLayout_3.addWidget(self.opacity_label, 1, 0, 1, 1)
        self.opacity_slider = QtWidgets.QSlider(self.tab_settings)
        self.opacity_slider.setMaximumSize(QtCore.QSize(374, 16777215))
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setProperty("value", 100)
        self.opacity_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.opacity_slider.setObjectName("opacity_slider")
        self.gridLayout_3.addWidget(self.opacity_slider, 1, 1, 1, 1)

        # opacity slider value changed
        self.opacity_slider.valueChanged.connect(self.on_click_opacity_changed)

        self.opacity_2_label = QtWidgets.QLabel(self.tab_settings)
        self.opacity_2_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.opacity_2_label.setFont(font)
        self.opacity_2_label.setObjectName("opacity_2_label")

        self.gridLayout_3.addWidget(self.opacity_2_label, 1, 2, 1, 1)

        self.color_label = QtWidgets.QLabel(self.tab_settings)
        self.color_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.color_label.setFont(font)
        self.color_label.setObjectName("opacity_label_2")

        self.gridLayout_3.addWidget(self.color_label, 2, 0, 1, 1)
        self.select_color_btn = QtWidgets.QPushButton(self.tab_settings)
        self.select_color_btn.setMaximumSize(QtCore.QSize(374, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.select_color_btn.setFont(font)
        self.select_color_btn.setObjectName("select_color_btn")
        self.select_color_btn.setToolTip('Opens color dialog')
        self.select_color_btn.setAutoDefault(False)
        self.select_color_btn.clicked.connect(self.on_click_color_btn)
        self.select_borders_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.gridLayout_3.addWidget(self.select_color_btn, 2, 1, 1, 1)

        self.engine_label = QtWidgets.QLabel(self.tab_settings)
        self.engine_label.setMaximumSize(QtCore.QSize(74, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.engine_label.setFont(font)
        self.engine_label.setObjectName("engine_label")
        self.gridLayout_3.addWidget(self.engine_label, 3, 0, 1, 1)

        self.engine_dropdown = QtWidgets.QComboBox(self.tab_settings)
        self.engine_dropdown.setMaximumSize(QtCore.QSize(374, 16777215))
        self.engine_dropdown.setCurrentText("")
        self.engine_dropdown.setObjectName("engine_dropdown")
        self.gridLayout_3.addWidget(self.engine_dropdown, 3, 1, 1, 1)

        # dropdown for font size
        translator_engines = ["GoogleTranslator", "PonsTranslator", "LingueeTranslator", "MyMemoryTranslator"]
        self.engine_dropdown.addItems(list(map(str, translator_engines)))
        self.engine_dropdown.currentTextChanged.connect(self.on_click_engine_changed)

        self.text_to_speech_label = QtWidgets.QLabel(self.tab_settings)
        self.text_to_speech_label.setMaximumSize(QtCore.QSize(90, 16777215))
        font = QtGui.QFont()
        font.setPointSize(12)
        self.text_to_speech_label.setFont(font)
        self.text_to_speech_label.setObjectName("text_to_speech_label")
        self.gridLayout_3.addWidget(self.text_to_speech_label, 4, 0, 1, 1)

        self.checkBox = QtWidgets.QCheckBox(self.tab_settings)
        font = QtGui.QFont()
        font.setPointSize(12)
        self.checkBox.setFont(font)
        self.checkBox.setObjectName("checkBox")
        self.gridLayout_3.addWidget(self.checkBox, 4, 1, 1, 2)

        self.verticalLayout.addLayout(self.gridLayout_3)
        self.gridLayout_4.addLayout(self.verticalLayout, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_settings, "")
        self.gridLayout.addWidget(self.tabWidget, 1, 0, 1, 1)

        self.tab_welcome = QtWidgets.QWidget()
        self.tab_welcome.setObjectName("tab_welcome")

        self.gridLayout_2 = QtWidgets.QGridLayout(self.tab_welcome)
        self.gridLayout_2.setObjectName("gridLayout_2")

        self.guide_label = QtWidgets.QLabel(self.tab_welcome)
        #        self.home_label.setGeometry(QtCore.QRect(30, 0, 371, 191))
        self.guide_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.guide_label.setObjectName("guide_label")
        self.guide_label.setWordWrap(True)
        self.guide_label.setOpenExternalLinks(True)

        self.gridLayout_2.addWidget(self.guide_label, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_welcome, "")

        self.tab_about_us = QtWidgets.QWidget()
        self.tab_about_us.setObjectName("tab_about_us")

        self.gridLayout_us = QtWidgets.QGridLayout(self.tab_about_us)
        self.gridLayout_us.setObjectName("gridLayout_us")

        self.gridLayout_9 = QtWidgets.QGridLayout()
        self.gridLayout_9.setObjectName("gridLayout_9")

        self.picture_label = QLabel(self.tab_about_us)
        pixmap = QPixmap('images/DeskTranslate.png')
        # self.picture_label.setScaledContents(True)
        self.picture_label.setPixmap(pixmap.scaled(150, 150))
        self.picture_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.picture_label.adjustSize()

        self.gridLayout_us.addWidget(self.picture_label, 1, 0, 1, 1)

        # Optional, resize window to image size
        #        self.tab_about_us.resize(pixmap.width(), pixmap.height())

        self.about_us_label = QtWidgets.QLabel(self.tab_about_us)
        #        self.home_label.setGeometry(QtCore.QRect(30, 0, 371, 191))
        self.about_us_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.about_us_label.setObjectName("about_us_label")
        self.about_us_label.setWordWrap(True)
        self.about_us_label.setOpenExternalLinks(True)

        self.gridLayout_us.addWidget(self.about_us_label, 2, 0, 1, 1)
        self.gridLayout_9.addLayout(self.gridLayout_2, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tab_about_us, "")

        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 438, 22))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "DeskTranslate v1.1"))
        self.guide_label.setText(_translate("MainWindow",
                                            "<html><head/><body><p align=\"center\"><a "
                                            "name=\"docs-internal-guid-25bb1131-7fff-63a2-64a4-c6962f5bb8c4\"/><span "
                                            "style=\" font-family:\'Arial\'; font-size:12pt; color:white; "
                                            "background-color:transparent;\">How to guide</span></p><p align=\"left\"><span style=\" "
                                            "font-family:\'Arial\'; font-size:10pt; color:#FFFFFF; "
                                            "background-color:transparent;\">To use this tool, simply:</span></p><p "
                                            "align=\"left\"><span style=\" font-family:\'Arial\'; font-size:9pt; "
                                            "color:#FFFFFF; background-color:transparent;\">&nbsp;&nbsp;&nbsp;&nbsp;1. Click on the Translate "
                                            "tab</span></p><p align=\"left\"><span style=\" font-family:\'Arial\'; "
                                            "font-size:9pt; color:#FFFFFF; background-color:transparent;\">&nbsp;&nbsp;&nbsp;&nbsp;2. Select "
                                            "the language you want to translate from</span></p><p "
                                            "align=\"left\"><span style=\" font-family:\'Arial\'; font-size:9pt; "
                                            "color:#FFFFFF; background-color:transparent;\">&nbsp;&nbsp;&nbsp;&nbsp;3. Select the language "
                                            "you want to translate to</span></p><p align=\"left\"><span style=\" "
                                            "font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; "
                                            "background-color:transparent;\">&nbsp;&nbsp;&nbsp;&nbsp;4. Select the Borders of the screen area "
                                            "to translate</span></p><p align=\"left\"><span "
                                            "style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; "
                                            "background-color:transparent;\">&nbsp;&nbsp;&nbsp;&nbsp;5. Click the Translate button to start "
                                            "the translation</span></p><p align=\"left\"><span style=\" "
                                            "font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; "
                                            "background-color:transparent;\">Check out our <a href=\"https://desktranslate.github.io/DeskTranslator/UserGuide.html\" style=\" font-family:\'Arial\'; font-size:9pt; color:#dcca70; background-color:transparent;\">user guide</a> to learn more!</span></p></body></html>"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_welcome), _translate("MainWindow", "📙 Guide"))
        self.frm_label.setText(_translate("MainWindow", "From:"))
        self.to_label.setText(_translate("MainWindow", "To:"))
        self.translate_btn.setText(_translate("MainWindow", "Translate"))
        self.select_borders_btn.setText(_translate("MainWindow", "Select borders"))
        self.language_label.setText(_translate("MainWindow", "Select language"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_translate), _translate("MainWindow", "🌐 Translate"))
        self.settings_font_label.setText(
            _translate("MainWindow", "<html><head/><body><p><span style=\" font-size:14pt;\">"
                                     "General</span></p></body></html>"))
        self.size_label.setText(_translate("MainWindow", "Size"))
        self.opacity_label.setText(_translate("MainWindow", "Opacity"))
        self.opacity_2_label.setText(_translate("MainWindow", "100"))
        self.select_color_btn.setText(_translate("MainWindow", "Select color"))
        self.color_label.setText(_translate("MainWindow", "Color"))
        self.engine_label.setText(_translate("MainWindow", "Engine"))
        self.text_to_speech_label.setText(_translate("MainWindow", "Dictation"))
        self.checkBox.setText(_translate("MainWindow", "Enable text to speech"))
        self.about_us_label.setText(_translate("MainWindow",
                                               "<html><head/><body><p align=\"center\"><a "
                                               "name=\"docs-internal-guid-25bb1131-7fff-63a2-64a4-c6962f5bb8c4\"/><span style=\" font-family:\'Arial\'; font-size:12pt; color:#FFFFFF; background-color:transparent;\">What is DeskTranslate?</span></p><p align=\"center\"><span style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">DeskTranslator is a live OCR screen capture translation tool for your desktop</span></p><p align=\"center\" style=\" font-family:\'Arial\'; font-size:9pt; color:#FFFFFF; background-color:transparent;\">Check out our <a href=\"https://github.com/DeskTranslate/DeskTranslator\" style=\" font-family:\'Arial\'; font-size:9pt; color:#dcca70; background-color:transparent;\">source code</a> and <a href=\"https://devpost.com/software/desktranslate\" style=\" font-family:\'Arial\'; font-size:9pt; color:#dcca70; background-color:transparent;\">DevPost write-up</a> to find out more!</p></body></html>"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_about_us), _translate("MainWindow", "👪 About Us"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_settings), _translate("MainWindow", "⚙ Settings "))


app = QApplication(sys.argv)

if __name__ == "__main__":
    #logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    #app = QtWidgets.QApplication(sys.argv)
    with open("pyqt/ManjaroMix.qss", "r") as file:
        qss = file.read()
        app.setStyleSheet(qss)
        print("👋")

    # Snip window
    snip_window = screen_reader.MyWidget()
    snip_window.hide()
    borders_selected = False

    # Main window
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.hide()

    # SplashScreenWindow
    splash_screen_window = splashscreen.SplashScreenWindow(MainWindow)
    splash_screen_window.show()
    QTimer.singleShot(2500, splash_screen_window.close)

    # Run the application!
    #sys.exit(app.exec_())
    app.exec()
