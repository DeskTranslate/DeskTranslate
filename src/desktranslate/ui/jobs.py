from collections.abc import Callable
from threading import Event, Thread

from PySide6.QtCore import QObject, Signal

from desktranslate.errors import DeskTranslateError


class Jobs(QObject):
    done = Signal(int, object, str)
    progress = Signal(str, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.serial = 0
        self.busy = False
        self.cancel = Event()

    def run(self, operation: Callable[[], object]) -> int:
        if self.busy:
            return 0
        self.busy = True
        self.serial += 1
        serial = self.serial
        self.cancel.clear()

        def worker() -> None:
            try:
                result = operation()
                self.done.emit(serial, result, "")
            except Exception as error:
                message = (
                    str(error)
                    if isinstance(error, DeskTranslateError)
                    else "The operation failed. Check your connection and try again."
                )
                self.done.emit(serial, None, message)

        Thread(target=worker, name="desktranslate-setup", daemon=True).start()
        return serial
