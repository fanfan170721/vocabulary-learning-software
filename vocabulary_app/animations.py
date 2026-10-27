"""Non-blocking completion effects drawn over the desktop window."""

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def notebook_icon(theme=None):
    theme = theme or {}
    pixmap = QPixmap(38, 38)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(theme.get("blue_dark", "#007CA8")), 1.8))
    painter.setBrush(QColor(theme.get("surface", "#FFFFFF")))
    painter.drawRoundedRect(QRectF(7, 7, 24, 26), 3, 3)
    painter.drawLine(12, 9, 12, 31)
    for y in (13, 19, 25):
        painter.drawLine(4, y, 9, y)
    painter.drawLine(17, 22, 24, 15)
    painter.drawLine(24, 15, 24, 20)
    painter.drawLine(24, 15, 19, 15)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(theme.get("error", "#D54151")))
    painter.drawEllipse(QRectF(25, 0, 13, 13))
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(QRectF(25, 0, 13, 13), Qt.AlignmentFlag.AlignCenter, "!")
    painter.end()
    return QIcon(pixmap)


class CelebrationOverlay(QWidget):
    def __init__(self, parent, theme=None):
        super().__init__(parent)
        self.theme = theme or {}
        self.duration = max(1.0, min(10.0, float(self.theme.get("animation_duration", 5.0))))
        self.particle_count = max(0, min(250, int(self.theme.get("confetti_count", 100))))
        self.gravity = max(100.0, min(1500.0, float(self.theme.get("confetti_gravity", 540))))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.particles = []
        self.flying_words = []
        self.started = 0.0
        self.last_tick = 0.0
        self.target = QPointF()
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.hide()

    def start(self, words=(), target=None, reduced=False):
        self.stop()
        if reduced:
            return
        self.setGeometry(self.parentWidget().rect())
        self.target = target or QPointF(self.width() - 90, 95)
        self.started = self.last_tick = time.monotonic()
        colors = self.theme.get("confetti_colors") or [self.theme.get("blue", "#00AEEC"), self.theme.get("pink", "#FB7299")]
        for _ in range(self.particle_count):
            self.particles.append({
                "x": self.width() * random.uniform(.25, .75),
                "y": random.uniform(-80, 5),
                "vx": random.uniform(-440, 440),
                "vy": random.uniform(50, 240),
                "w": random.uniform(4, 8),
                "h": random.uniform(8, 16),
                "angle": random.uniform(0, 360),
                "spin": random.uniform(-220, 220),
                "color": random.choice(colors),
                "floor_at": None,
            })
        self.flying_words = [
            {"text": word, "delay": i * .055, "x": random.uniform(.30, .64) * self.width(),
             "y": random.uniform(.35, .65) * self.height()}
            for i, word in enumerate(words)
        ]
        self.show()
        self.raise_()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.particles = []
        self.flying_words = []
        self.hide()

    def _tick(self):
        now = time.monotonic()
        dt = min(.04, now - self.last_tick)
        self.last_tick = now
        age = now - self.started
        for p in self.particles:
            p["vy"] += self.gravity * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["angle"] += p["spin"] * dt
            if p["x"] < 5:
                p["x"] = 5
                p["vx"] = abs(p["vx"]) * .75
            elif p["x"] > self.width() - 5:
                p["x"] = self.width() - 5
                p["vx"] = -abs(p["vx"]) * .75
            if p["y"] > self.height() - 9:
                p["y"] = self.height() - 9
                p["vy"] = -abs(p["vy"]) * .35
                p["vx"] *= .83
                if p["floor_at"] is None:
                    p["floor_at"] = age
        if age > self.duration:
            self.stop()
        else:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        age = time.monotonic() - self.started
        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.particles:
            floor_age = age - p["floor_at"] if p["floor_at"] is not None else 0
            alpha = min(1.0, max(0.0, (self.duration - age) / min(1.1, self.duration / 3)), max(0.0, 1.0 - floor_age / max(.4, self.duration * .34)))
            color = QColor(p["color"])
            color.setAlphaF(alpha)
            painter.save()
            painter.translate(p["x"], p["y"])
            painter.rotate(p["angle"])
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(-p["w"] / 2, -p["h"] / 2, p["w"], p["h"]), 1, 1)
            painter.restore()
        for word in self.flying_words:
            progress = (age - word["delay"] - .15) / 1.5
            if not 0 <= progress <= 1:
                continue
            t = 1 - (1 - progress) ** 2
            start = QPointF(word["x"], word["y"])
            control = QPointF((start.x() + self.target.x()) / 2, min(start.y(), self.target.y()) - 120)
            x = (1-t)**2 * start.x() + 2*(1-t)*t*control.x() + t*t*self.target.x()
            y = (1-t)**2 * start.y() + 2*(1-t)*t*control.y() + t*t*self.target.y()
            painter.save()
            painter.setOpacity(1 - max(0.0, (progress - .7) / .3))
            painter.setPen(QColor(self.theme.get("blue_dark", "#007CA8")))
            painter.translate(x, y)
            painter.scale(1 - .65 * t, 1 - .65 * t)
            painter.drawText(QRectF(-80, -15, 160, 30), Qt.AlignmentFlag.AlignCenter, word["text"])
            painter.restore()
        painter.end()
