"""Small, scalable illustrations used by the desktop interface."""

from math import cos, pi, sin

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget


_ACCENTS = {
    "learning": "#00A6DB",
    "mistakes": "#E77D91",
    "history": "#8B85C8",
    "achievements": "#D6A03D",
    "goals": "#4BAA97",
    "queue": "#61AEB5",
    "settings": "#7C92AA",
    "assessment": "#719ED1",
}
_TINTS = {
    "learning": "#E9F7FD",
    "mistakes": "#FFF0F3",
    "history": "#F2EFFB",
    "achievements": "#FFF7E5",
    "goals": "#ECF8F3",
    "queue": "#EDF8F9",
    "settings": "#F0F3F7",
    "assessment": "#EDF3FC",
}


def module_accent(key, theme):
    return theme.get("module_accents", {}).get(key, _ACCENTS.get(key, _ACCENTS["learning"]))


def module_tint(key, theme):
    return theme.get("module_tints", {}).get(key, _TINTS.get(key, _TINTS["learning"]))


def _pen(color, width=2.0):
    return QPen(QColor(color), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def _line(painter, x1, y1, x2, y2):
    painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _star(cx, cy, radius, inner=None, points=5):
    inner = radius * 0.47 if inner is None else inner
    vertices = []
    for index in range(points * 2):
        angle = -pi / 2 + index * pi / points
        distance = radius if index % 2 == 0 else inner
        vertices.append(QPointF(cx + cos(angle) * distance, cy + sin(angle) * distance))
    return QPolygonF(vertices)


class ModuleIcon(QWidget):
    """A colored line icon on a quiet rounded tile."""

    def __init__(self, key, theme, size=56, parent=None):
        super().__init__(parent)
        self.key = key
        self.theme = theme
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAccessibleName("")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / 56, self.height() / 56)
        accent = module_accent(self.key, self.theme)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(module_tint(self.key, self.theme)))
        p.drawRoundedRect(QRectF(0.5, 0.5, 55, 55), 16, 16)
        p.setPen(_pen(accent, 2.1))
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self.key == "learning":
            p.setPen(_pen(accent, 1.7))
            p.drawRoundedRect(QRectF(13, 13, 25, 29), 4, 4)
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(18, 17, 25, 29), 4, 4)
            p.setPen(_pen(accent, 2.1))
            _line(p, 25, 27, 36, 27)
            _line(p, 25, 32, 36, 32)
            _line(p, 25, 37, 31, 37)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.theme.get("pink", "#FB7299")))
            p.drawRoundedRect(QRectF(33, 13, 7, 10), 2, 2)
        elif self.key == "mistakes":
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(16, 13, 25, 31), 4, 4)
            _line(p, 22, 14, 22, 43)
            for y in (19, 27, 35):
                _line(p, 13, y, 18, y)
            p.setPen(_pen(accent, 2.7))
            _line(p, 32, 22, 32, 30)
            p.drawPoint(QPointF(32, 35))
        elif self.key == "history":
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QRectF(14, 14, 29, 29))
            p.setPen(_pen(accent, 2.4))
            _line(p, 29, 21, 29, 29)
            _line(p, 29, 29, 35, 32)
            p.setPen(_pen("#BAAFE9", 2.1))
            _line(p, 11, 19, 11, 27)
            _line(p, 11, 27, 19, 27)
        elif self.key == "achievements":
            p.setBrush(QColor("#FFFFFF"))
            cup = QPainterPath(QPointF(19, 15))
            cup.lineTo(38, 15)
            cup.lineTo(36, 28)
            cup.quadTo(34, 35, 28.5, 35)
            cup.quadTo(23, 35, 21, 28)
            cup.closeSubpath()
            p.drawPath(cup)
            p.setBrush(Qt.BrushStyle.NoBrush)
            handle = QPainterPath(QPointF(19, 18))
            handle.lineTo(13, 18)
            handle.quadTo(12, 28, 22, 28)
            p.drawPath(handle)
            handle = QPainterPath(QPointF(38, 18))
            handle.lineTo(44, 18)
            handle.quadTo(45, 28, 35, 28)
            p.drawPath(handle)
            _line(p, 28.5, 35, 28.5, 41)
            _line(p, 22, 42, 35, 42)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#F1C45D"))
            p.drawPolygon(_star(28.5, 24, 5))
        elif self.key == "goals":
            p.setBrush(QColor("#FFFFFF"))
            flag = QPainterPath(QPointF(21, 14))
            flag.cubicTo(29, 11, 32, 20, 41, 15)
            flag.lineTo(41, 29)
            flag.cubicTo(32, 34, 29, 25, 21, 28)
            p.drawPath(flag)
            _line(p, 21, 14, 21, 43)
            _line(p, 15, 43, 29, 43)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#F3C46B"))
            p.drawEllipse(QRectF(32, 37, 6, 6))
        elif self.key == "queue":
            p.setPen(_pen(accent, 1.8))
            _line(p, 16, 14, 38, 14)
            _line(p, 14, 19, 40, 19)
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(12, 24, 30, 20), 4, 4)
            p.setPen(_pen(accent, 2.2))
            _line(p, 21, 34, 33, 34)
            _line(p, 27, 28, 27, 40)
        elif self.key == "settings":
            for index, x in enumerate((18, 28, 38)):
                _line(p, x, 14, x, 42)
                p.setBrush(QColor("#FFFFFF"))
                p.drawRoundedRect(QRectF(x - 4, (21, 31, 23)[index] - 4, 8, 8), 3, 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self.theme.get("blue", "#00AEEC")))
            p.drawEllipse(QRectF(26, 29, 4, 4))
        else:
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(16, 14, 26, 31), 4, 4)
            p.setBrush(QColor(module_tint(self.key, self.theme)))
            p.drawRoundedRect(QRectF(22, 11, 14, 7), 2.5, 2.5)
            p.setBrush(Qt.BrushStyle.NoBrush)
            _line(p, 23, 28, 27, 32)
            _line(p, 27, 32, 35, 24)
            p.setPen(_pen("#A9B8D0", 1.8))
            _line(p, 23, 38, 35, 38)
        p.end()


class LearningIllustration(QWidget):
    """An open book and a word card, drawn at the available size."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(150, 100)
        self.setMaximumSize(290, 172)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def sizeHint(self):
        return QSize(260, 155)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        factor = min(self.width() / 260, self.height() / 155)
        p.translate((self.width() - 260 * factor) / 2, (self.height() - 155 * factor) / 2)
        p.scale(factor, factor)
        blue = self.theme.get("blue", "#00AEEC")
        pink = self.theme.get("pink", "#FB7299")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#DFF3FC"))
        p.drawRoundedRect(QRectF(34, 25, 197, 108), 42, 42)
        p.setBrush(QColor("#D8F0E9"))
        p.drawEllipse(QRectF(28, 85, 26, 26))
        p.setBrush(QColor("#EAC4D6"))
        p.drawEllipse(QRectF(215, 34, 8, 8))
        p.setBrush(QColor("#F3D78A"))
        p.drawEllipse(QRectF(51, 24, 6, 6))

        p.save()
        p.translate(145, 75)
        p.rotate(10)
        p.setBrush(QColor("#C6E6F2"))
        p.drawRoundedRect(QRectF(-39, -49, 89, 105), 10, 10)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(-42, -53, 89, 105), 10, 10)
        p.setBrush(QColor("#F1F9FD"))
        p.drawRoundedRect(QRectF(-31, -41, 67, 61), 6, 6)
        p.setPen(QColor("#008DBC"))
        font = QFont(self.theme.get("font_family", "Microsoft YaHei UI"))
        font.setPixelSize(36)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.drawText(QRectF(-31, -42, 67, 59), Qt.AlignmentFlag.AlignCenter, "Aa")
        p.setPen(_pen("#C9DDE7", 3))
        _line(p, -25, 32, 21, 32)
        _line(p, -25, 40, 4, 40)
        p.restore()

        p.setPen(_pen("#76C4E2", 1.4))
        p.setBrush(QColor("#A8DEEF"))
        cover = QPainterPath(QPointF(50, 85))
        cover.quadTo(78, 79, 111, 94)
        cover.quadTo(140, 78, 170, 86)
        cover.lineTo(174, 137)
        cover.quadTo(141, 130, 111, 143)
        cover.quadTo(78, 129, 47, 136)
        cover.closeSubpath()
        p.drawPath(cover)
        p.setPen(_pen("#D6E5EC", 1))
        p.setBrush(QColor("#FFFFFF"))
        pages = QPainterPath(QPointF(54, 80))
        pages.quadTo(80, 77, 111, 91)
        pages.quadTo(138, 78, 166, 81)
        pages.lineTo(168, 131)
        pages.quadTo(137, 127, 111, 138)
        pages.quadTo(80, 126, 51, 131)
        pages.closeSubpath()
        p.drawPath(pages)
        p.setPen(_pen("#D8E8EE", 1.3))
        _line(p, 111, 94, 111, 136)
        p.setPen(_pen("#BCD8E3", 2.2))
        for y in (96, 105, 114):
            _line(p, 64, y, 98, y + 4)
            _line(p, 123, y + 3, 156, y - 1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pink))
        bookmark = QPolygonF([QPointF(139, 82), QPointF(147, 81), QPointF(148, 105), QPointF(144, 101), QPointF(140, 105)])
        p.drawPolygon(bookmark)

        p.save()
        p.translate(214, 106)
        p.rotate(-10)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(-19, -17, 38, 34), 10, 10)
        p.setPen(_pen("#51B7A0", 3.2))
        _line(p, -8, 0, -2, 6)
        _line(p, -2, 6, 9, -6)
        p.restore()
        p.setPen(_pen(pink, 2.2))
        _line(p, 83, 20, 83, 28)
        _line(p, 79, 24, 87, 24)
        p.setPen(_pen(blue, 2))
        _line(p, 25, 57, 31, 55)
        p.end()


class BadgeIcon(QWidget):
    """A small medal whose material changes with its milestone."""

    def __init__(self, earned, tier, theme, size=52, parent=None):
        super().__init__(parent)
        self.earned = earned
        self.tier = tier
        self.theme = theme
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / 52, self.height() / 52)
        palette = [
            ("#D6A03D", "#FFF3D7", "#F0C365"),
            ("#61A997", "#E8F6EE", "#9AD7BE"),
            ("#5AA1C4", "#E7F5FC", "#9ACDE7"),
            ("#9B87C8", "#F2EDFB", "#C2AFE8"),
            ("#CF88A0", "#FFF0F6", "#F1B4CA"),
            ("#C5903A", "#FFF5DE", "#F4CB6D"),
            ("#A47BB4", "#F8EDFC", "#D5ACE1"),
            ("#C79234", "#FFF0CA", "#EDBD56"),
        ]
        outline, fill, ribbon = palette[min(max(self.tier, 0), len(palette) - 1)] if self.earned else ("#B6BFCB", "#F3F5F8", "#DCE1E8")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ribbon))
        p.drawPolygon(QPolygonF([QPointF(16, 29), QPointF(25, 31), QPointF(20, 48), QPointF(15, 42), QPointF(10, 44)]))
        p.drawPolygon(QPolygonF([QPointF(27, 31), QPointF(36, 29), QPointF(42, 44), QPointF(36, 42), QPointF(32, 48)]))
        p.setPen(_pen(outline, 1.8))
        p.setBrush(QColor(fill))
        p.drawEllipse(QRectF(9, 5, 34, 34))
        p.setPen(_pen(outline, 0.8))
        p.drawEllipse(QRectF(13, 9, 26, 26))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(outline))
        p.drawPolygon(_star(26, 22, 9))
        if self.earned and self.tier >= 4:
            p.setPen(_pen(ribbon, 1.6))
            _line(p, 46, 10, 46, 15)
            _line(p, 43.5, 12.5, 48.5, 12.5)
        p.end()
