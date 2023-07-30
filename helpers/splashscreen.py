from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QMovie


class SplashScreenWindow(QtWidgets.QMainWindow):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setObjectName("MainWindow")
        self.resize(500, 500)
        self.centralwidget = QtWidgets.QWidget(self)
        self.centralwidget.setObjectName("centralwidget")

        # create label
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 0, 500, 500))
        self.label.setObjectName("label")

        # add label to main window
        self.setCentralWidget(self.centralwidget)

        # set qmovie as label
        self.movie = QMovie("images/DeskTranslate.gif")
        self.label.setMovie(self.movie)
        self.movie.start()

    def closeEvent(self, event):
        self.main_window.show()

# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     window = QtWidgets.QMainWindow()
#     ui = SplashScreenUi()
#     ui.setupUi(window)
#     window.show()
#     sys.exit(app.exec_())
