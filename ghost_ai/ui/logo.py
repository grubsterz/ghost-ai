"""The GHOST AI logo, painted in code (no SVG plugin needed)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap


def logo_pixmap(size: int = 256, background: bool = True) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256.0
    if background:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#14151a"))
        p.drawRoundedRect(QRectF(0, 0, size, size), 56 * s, 56 * s)
    grad = QLinearGradient(QPointF(40 * s, 40 * s), QPointF(216 * s, 216 * s))
    grad.setColorAt(0, QColor("#8b5cf6"))
    grad.setColorAt(1, QColor("#22d3ee"))
    body = QPainterPath()
    body.moveTo(56 * s, 116 * s)
    body.cubicTo(56 * s, 66 * s, 88 * s, 40 * s, 128 * s, 40 * s)
    body.cubicTo(168 * s, 40 * s, 200 * s, 66 * s, 200 * s, 116 * s)
    body.lineTo(200 * s, 212 * s)
    # wavy bottom edge
    xs = [200, 176, 152, 128, 104, 80, 56]
    for i in range(1, len(xs)):
        y = 196 if i % 2 else 212
        body.lineTo(xs[i] * s, y * s)
    body.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPath(body)
    p.setBrush(QColor("#14151a"))
    p.drawEllipse(QRectF(91 * s, 100 * s, 26 * s, 36 * s))
    p.drawEllipse(QRectF(139 * s, 100 * s, 26 * s, 36 * s))
    p.end()
    return pm


def logo_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(sz))
    return icon
