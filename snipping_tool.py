from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtCore import QPointF, Qt, QRectF


class SnippingToolWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.painter       = QPainter(self)
        self.painter_pen   = QPen(QColor('black'),3)
        self.painter_brush = QColor(128,128,255,128)
        self.snip_start    = QPointF()
        self.snip_end      = self.snip_start
        self.setWindowOpacity(0.3)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        screens=QApplication.screens()
        combined_geometry=screens.pop(0).geometry()
        for screen in screens:
            combined_geometry=combined_geometry.united(screen.geometry())
        self.setGeometry(combined_geometry)


    def showEvent(self, event):
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)


    def paintEvent(self, event):
        self.painter.begin(self)
        self.painter.setPen(self.painter_pen)
        self.painter.setBrush(self.painter_brush)
        self.painter.drawRect(QRectF(self.snip_start, self.snip_end))
        self.painter.end()


    def mousePressEvent(self, event):
        self.snip_start = event.position()
        self.snip_end   = self.snip_start


    def mouseMoveEvent(self, event):
        self.snip_end = event.position()
        self.update()


    def mouseReleaseEvent(self, event):
        self.close()


    def closeEvent(self, event):
        QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)


    def get_snip_start(self):
        return self.snip_start


    def get_snip_end(self):
        return self.snip_end


if __name__=="__main__":
    app = QApplication([])
    snipping_tool_window = SnippingToolWindow()
    snipping_tool_window.show()
    app.exec()