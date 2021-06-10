
import sys
from threading import Thread

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QColorDialog, QSizePolicy, QMessageBox, QLabel
# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dictionaryGeneratedCJYtuQ.ui'
##
## Created by: Qt User Interface Compiler version 5.14.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QMetaObject, QObject, QPoint,
    QRect, QSize, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QLinearGradient, QPalette, QPainter, QPixmap,
    QRadialGradient)
from PySide2.QtWidgets import *


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if MainWindow.objectName():
            MainWindow.setObjectName("MainWindow")
        MainWindow.resize(421, 288)
        self.centralwidget_dict = QWidget(MainWindow)
        self.centralwidget_dict.setObjectName(u"centralwidget_dict")
        self.gridLayout = QGridLayout(self.centralwidget_dict)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout_dictionary = QGridLayout()
        self.gridLayout_dictionary.setObjectName(u"gridLayout_dictionary")
        self.lineEdit_dictsearch = QLineEdit(self.centralwidget_dict)
        self.lineEdit_dictsearch.setObjectName(u"lineEdit_dictsearch")
        font = QFont()
        font.setPointSize(10)
        self.lineEdit_dictsearch.setFont(font)
        self.lineEdit_dictsearch.setDragEnabled(True)

        self.gridLayout_dictionary.addWidget(self.lineEdit_dictsearch, 1, 1, 1, 1)

        self.label_lookup = QLabel(self.centralwidget_dict)
        self.label_lookup.setObjectName(u"label_lookup")
        self.label_lookup.setFont(font)
        self.label_lookup.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout_dictionary.addWidget(self.label_lookup, 0, 0, 1, 1)

        self.textBrowser_dictresult = QTextBrowser(self.centralwidget_dict)
        self.textBrowser_dictresult.setObjectName(u"textBrowser_dictresult")
        self.textBrowser_dictresult.setFont(font)

        self.gridLayout_dictionary.addWidget(self.textBrowser_dictresult, 3, 1, 1, 1)

        self.comboBox_lookup = QComboBox(self.centralwidget_dict)
        self.comboBox_lookup.setObjectName(u"comboBox_lookup")

        self.gridLayout_dictionary.addWidget(self.comboBox_lookup, 0, 1, 1, 1)

        self.label_searchtern = QLabel(self.centralwidget_dict)
        self.label_searchtern.setObjectName(u"label_searchtern")
        self.label_searchtern.setFont(font)
        self.label_searchtern.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout_dictionary.addWidget(self.label_searchtern, 1, 0, 1, 1)

        self.label_result = QLabel(self.centralwidget_dict)
        self.label_result.setObjectName(u"label_result")
        self.label_result.setFont(font)
        self.label_result.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.gridLayout_dictionary.addWidget(self.label_result, 3, 0, 1, 1)

        self.verticalSpacer_dict = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.gridLayout_dictionary.addItem(self.verticalSpacer_dict, 2, 1, 1, 1)


        self.gridLayout.addLayout(self.gridLayout_dictionary, 1, 0, 1, 1)

        MainWindow.setCentralWidget(self.centralwidget_dict)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
#if QT_CONFIG(tooltip)
        self.lineEdit_dictsearch.setToolTip(QCoreApplication.translate("MainWindow", u"enter word here", None))
#endif // QT_CONFIG(tooltip)
        self.lineEdit_dictsearch.setText("")
        self.label_lookup.setText(QCoreApplication.translate("MainWindow", u"Look up", None))
        self.textBrowser_dictresult.setHtml(QCoreApplication.translate("MainWindow", u"<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                                                                                     "<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
                                                                                     "p,"
                                                                                     "li { white-space: pre-wrap; }\n"
                                                                                     "</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:10pt; font-weight:400; font-style:normal;\">\n"
                                                                                     "<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><br /></p></body></html>", None))
        self.label_searchtern.setText(QCoreApplication.translate("MainWindow", u"Search term", None))
        self.label_result.setText(QCoreApplication.translate("MainWindow", u"result", None))
    # retranslateUi



if __name__ == "__main__":
    # Main window
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)

    # SplashScreenWindow
    # splash_screen_window = SplashScreenWindow(MainWindow)
    # splash_screen_window.show()
    # QTimer.singleShot(2500, splash_screen_window.close)
    app = QApplication(sys.argv)
    # Run the application!
    sys.exit(app.exec_())
