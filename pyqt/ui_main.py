# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainxxLMPy.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(430, 300)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setGeometry(QRect(0, 0, 431, 251))
        self.tab_welcome = QWidget()
        self.tab_welcome.setObjectName(u"tab_welcome")
        self.home_label = QLabel(self.tab_welcome)
        self.home_label.setObjectName(u"home_label")
        self.home_label.setGeometry(QRect(30, 10, 371, 201))
        self.home_label.setAlignment(Qt.AlignCenter)
        self.tabWidget.addTab(self.tab_welcome, "")
        self.tab_translate = QWidget()
        self.tab_translate.setObjectName(u"tab_translate")
        self.frm_label = QLabel(self.tab_translate)
        self.frm_label.setObjectName(u"frm_label")
        self.frm_label.setGeometry(QRect(50, 70, 61, 21))
        font = QFont()
        font.setPointSize(16)
        self.frm_label.setFont(font)
        self.frm_dropdown = QComboBox(self.tab_translate)
        self.frm_dropdown.setObjectName(u"frm_dropdown")
        self.frm_dropdown.setGeometry(QRect(120, 70, 271, 31))
        self.to_label = QLabel(self.tab_translate)
        self.to_label.setObjectName(u"to_label")
        self.to_label.setGeometry(QRect(50, 130, 61, 21))
        self.to_label.setFont(font)
        self.translate_btn = QPushButton(self.tab_translate)
        self.translate_btn.setObjectName(u"translate_btn")
        self.translate_btn.setGeometry(QRect(230, 170, 161, 41))
        self.translate_btn.setAutoDefault(False)
        self.to_dropdown = QComboBox(self.tab_translate)
        self.to_dropdown.setObjectName(u"to_dropdown")
        self.to_dropdown.setGeometry(QRect(120, 120, 271, 31))
        self.select_borders_btn = QPushButton(self.tab_translate)
        self.select_borders_btn.setObjectName(u"select_borders_btn")
        self.select_borders_btn.setGeometry(QRect(60, 170, 161, 41))
        self.select_borders_btn.setAutoDefault(False)
        self.label = QLabel(self.tab_translate)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(120, 20, 211, 31))
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignCenter)
        self.tabWidget.addTab(self.tab_translate, "")
        self.tab_settings = QWidget()
        self.tab_settings.setObjectName(u"tab_settings")
        self.settings_font_label = QLabel(self.tab_settings)
        self.settings_font_label.setObjectName(u"settings_font_label")
        self.settings_font_label.setGeometry(QRect(10, 10, 61, 21))
        self.settings_font_label.setFont(font)
        self.size_label = QLabel(self.tab_settings)
        self.size_label.setObjectName(u"size_label")
        self.size_label.setGeometry(QRect(30, 50, 61, 31))
        font1 = QFont()
        font1.setPointSize(12)
        self.size_label.setFont(font1)
        self.size_dropdown = QComboBox(self.tab_settings)
        self.size_dropdown.setObjectName(u"size_dropdown")
        self.size_dropdown.setGeometry(QRect(120, 50, 69, 22))
        self.opacity_slider = QSlider(self.tab_settings)
        self.opacity_slider.setObjectName(u"opacity_slider")
        self.opacity_slider.setGeometry(QRect(120, 90, 181, 22))
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setOrientation(Qt.Horizontal)
        self.opacity_label = QLabel(self.tab_settings)
        self.opacity_label.setObjectName(u"opacity_label")
        self.opacity_label.setGeometry(QRect(30, 90, 61, 31))
        self.opacity_label.setFont(font1)
        self.opacity_2_label = QLabel(self.tab_settings)
        self.opacity_2_label.setObjectName(u"opacity_2_label")
        self.opacity_2_label.setGeometry(QRect(340, 80, 61, 31))
        self.opacity_2_label.setFont(font1)
        self.tabWidget.addTab(self.tab_settings, "")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 430, 22))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"DeskTranslator v1.0", None))
        self.home_label.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p align=\"center\"><a name=\"docs-internal-guid-25bb1131-7fff-63a2-64a4-c6962f5bb8c4\"/><span style=\" font-family:'Arial'; color:#000000; background-color:transparent;\">H</span><span style=\" font-family:'Arial'; color:#000000; background-color:transparent;\">ello there!</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">DeskTranslator is a live OCR translation tool for your desktop.\u00a0</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">To use tool, simply:</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">1. Click on the Translate tab</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">2. Select the language you want to translate from</span></p><p align=\"center\"><span style=\" fon"
                        "t-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">3. Select the language you want to translate to</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">4. Select the Borders of the screen area you want the translator to process</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">5. Click the Translate button to start the translation</span></p><p align=\"center\"><span style=\" font-family:'Arial'; font-size:7pt; color:#000000; background-color:transparent;\">Additionally, you can adjust the font size and color to your liking. </span></p><p align=\"center\"><span style=\" font-size:7pt;\"><br/></span></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_welcome), QCoreApplication.translate("MainWindow", u"Home", None))
        self.frm_label.setText(QCoreApplication.translate("MainWindow", u"From:", None))
        self.to_label.setText(QCoreApplication.translate("MainWindow", u"To:", None))
        self.translate_btn.setText(QCoreApplication.translate("MainWindow", u"Translate", None))
        self.select_borders_btn.setText(QCoreApplication.translate("MainWindow", u"Select borders", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Select language", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_translate), QCoreApplication.translate("MainWindow", u"Translate", None))
        self.settings_font_label.setText(QCoreApplication.translate("MainWindow", u"Font", None))
        self.size_label.setText(QCoreApplication.translate("MainWindow", u"Size", None))
        self.size_dropdown.setCurrentText("")
        self.opacity_label.setText(QCoreApplication.translate("MainWindow", u"Opacity", None))
        self.opacity_2_label.setText(QCoreApplication.translate("MainWindow", u"100", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tab_settings), QCoreApplication.translate("MainWindow", u"Settings", None))
    # retranslateUi

