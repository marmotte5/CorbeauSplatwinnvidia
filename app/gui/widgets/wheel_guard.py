"""wheel_guard.py — stop scroll wheel from accidentally changing form widgets.

Combo boxes, spin boxes and sliders live inside scrollable tabs (QScrollArea).
When the user scrolls the page, the wheel passes over those widgets and Qt would
change their value (e.g. the COLMAP matcher silently flips to another option).
This guard makes such widgets ignore the wheel unless they actually have focus
(the user clicked into them); the scroll area scrolls instead.
"""
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QAbstractSlider, QAbstractSpinBox, QComboBox


class _WheelGuard(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and not obj.hasFocus():
            event.ignore()
            return True  # consume: don't change the widget, let the page scroll
        return False


# Module-level singleton: installEventFilter does not take ownership, so the
# filter must outlive every widget it is installed on.
_guard = _WheelGuard()


def install_wheel_guard(root):
    """Guard every combo / spin box / slider under ``root`` against stray wheel."""
    for widget_type in (QComboBox, QAbstractSpinBox, QAbstractSlider):
        for w in root.findChildren(widget_type):
            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # drop WheelFocus
            w.installEventFilter(_guard)
