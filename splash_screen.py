from PyQt6.QtWidgets import QMainWindow, QLabel, QApplication
from PyQt6.QtGui import QMovie
from PyQt6.QtCore import Qt, QTimer


class SplashScreenWindow(QMainWindow):
    def __init__(self, desk_translate_gui_window):
        QMainWindow.__init__(self)
        self.desk_translate_gui_window = desk_translate_gui_window
        self.movie = QMovie("images/DeskTranslate.gif")
        label = QLabel()
        label.setMovie(self.movie)
        self.setCentralWidget(label)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(500,500)


    def showEvent(self, event):
        self.movie.start()
        QTimer.singleShot(2500, self.close)


    def closeEvent(self, event):
        self.desk_translate_gui_window.show()


if __name__=="__main__":
    app = QApplication([])
    main_window=QMainWindow() # To be replaced with the actual main window.
    splash_screen_window = SplashScreenWindow(main_window)
    splash_screen_window.show()
    app.exec()