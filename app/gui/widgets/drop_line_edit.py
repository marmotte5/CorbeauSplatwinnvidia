from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit


class DropLineEdit(QLineEdit):
    """
    A QLineEdit that accepts file drops.
    Emits fileDropped(str) signal when a valid path is dropped.
    If allowed_base_dirs is set, validates that the dropped path
    is contained within one of the specified directories (containment check).
    """
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._allowed_base_dirs: list[Path] | None = None

    def set_allowed_base_dirs(self, dirs: list[Path]):
        """Set allowed base directories for containment validation."""
        self._allowed_base_dirs = [Path(d).resolve() for d in dirs]

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def _validate_path(self, path: str) -> bool:
        try:
            p = Path(path).resolve()
            if not p.exists():
                return False
            # Containment check: if base dirs are configured, path must be inside one
            if self._allowed_base_dirs is not None:
                for base in self._allowed_base_dirs:
                    try:
                        p.relative_to(base)
                        return True
                    except ValueError:
                        continue
                return False
            return True
        except (TypeError, ValueError, OSError):
            return False

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                paths = []
                for url in urls:
                    path = url.toLocalFile()
                    if path and self._validate_path(path):
                        paths.append(path)

                if paths:
                    joined_paths = "|".join(paths)
                    self.setText(joined_paths)
                    self.fileDropped.emit(joined_paths)
                    event.acceptProposedAction()
        else:
            super().dropEvent(event)
