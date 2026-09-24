"""Interactive macroeconomics workspace with a world choropleth map."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from dataclasses import dataclass
from pathlib import Path

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from chartist.theme import BG, BORDER, DRAW, FG, MUTED


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    suffix: str
    low: float
    high: float
    decimals: int = 1


METRICS = (
    Metric("growth", "GDP growth", "%", -4.0, 9.0),
    Metric("inflation", "Inflation", "%", 0.0, 14.0),
    Metric("rate", "Interest rate", "%", 0.0, 12.0),
    Metric("unemployment", "Unemployment", "%", 1.0, 22.0),
    Metric("debt", "Government debt to GDP", "%", 10.0, 180.0),
    Metric("pmi", "Manufacturing PMI", "", 38.0, 62.0),
    Metric("gdp_pc", "GDP per capita", " USD", 500.0, 90_000.0, 0),
)
METRIC_BY_KEY = {metric.key: metric for metric in METRICS}


YEAR_START = 1914
YEAR_END = 2026


@dataclass
class Country:
    iso: str
    name: str
    continent: str
    population: int
    gdp_millions: float
    geometry: dict
    values: dict[str, float]
    path: QtGui.QPainterPath | None = None

    def valuesForYear(self, year: int) -> dict[str, float]:
        return _countryValuesForYear(
            self.iso, self.population, self.gdp_millions, year
        )


def _seedValue(iso: str, salt: str) -> float:
    digest = hashlib.sha256(f"{iso}:{salt}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 0xFFFFFFFF


def _blend(a: float, b: float, amount: float) -> float:
    return a + (b - a) * amount


def _countryValuesForYear(
    iso: str, population: int, gdp_millions: float, year: int
) -> dict[str, float]:
    """Simulated year-aware macro values for each country."""
    progress = max(0.0, min(1.0, (year - YEAR_START) / (YEAR_END - YEAR_START)))
    cycle = 0.5 + 0.5 * math.sin(
        (year - YEAR_START) * 0.19 + _seedValue(iso, "phase") * 6
    )
    inflation_base = 0.5 + _seedValue(iso, "inflation") * 11.5
    growth_base = -2.5 + _seedValue(iso, "growth") * 10.5
    rate_base = _seedValue(iso, "rate") * 10.5
    raw = {
        "growth": growth_base + (cycle - 0.5) * 3.2 + (progress - 0.5) * 1.4,
        "inflation": inflation_base
        + (cycle - 0.35) * 4.8
        + (0.55 - progress) * 2.5,
        "rate": rate_base + (cycle - 0.45) * 3.0 + progress * 1.2,
        "unemployment": 2.0
        + _seedValue(iso, "jobs") * 16.0
        + (0.5 - cycle) * 4.0
        + (0.4 - progress) * 2.0,
        "debt": 20.0
        + _seedValue(iso, "debt") * 140.0
        + progress * 35.0
        + (cycle - 0.5) * 18.0,
        "pmi": 41.0
        + _seedValue(iso, "pmi") * 18.0
        + (cycle - 0.5) * 8.0
        + progress * 1.5,
        "gdp_pc": gdp_millions
        * 1_000_000
        / max(1, population)
        * _blend(0.35, 1.25, progress)
        * (0.92 + cycle * 0.16),
    }
    return {
        key: max(METRIC_BY_KEY[key].low, min(METRIC_BY_KEY[key].high, value))
        for key, value in raw.items()
    }


def _countryValues(properties) -> dict[str, float]:
    iso = properties.get("ADM0_A3") or properties.get("ISO_A3") or "UNK"
    population = max(1, int(properties.get("POP_EST") or 1))
    gdp_millions = max(1.0, float(properties.get("GDP_MD") or 1.0))
    return _countryValuesForYear(iso, population, gdp_millions, YEAR_END)


def loadCountries() -> list[Country]:
    path = Path(__file__).parents[1] / "assets" / "world_countries.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    countries = []
    for feature in data["features"]:
        properties = feature["properties"]
        iso = properties.get("ADM0_A3") or properties.get("ISO_A3")
        if not iso:
            continue
        population = int(properties.get("POP_EST") or 0)
        gdp_millions = float(properties.get("GDP_MD") or 0)
        countries.append(
            Country(
                iso=iso,
                name=properties.get("NAME_EN") or properties.get("ADMIN") or iso,
                continent=properties.get("CONTINENT") or "Other",
                population=population,
                gdp_millions=gdp_millions,
                geometry=feature["geometry"],
                values=_countryValuesForYear(
                    iso, max(1, population), max(1.0, gdp_millions), YEAR_END
                ),
            )
        )
    return sorted(countries, key=lambda country: country.name)


def _metricText(metric: Metric, value: float) -> str:
    return f"{value:,.{metric.decimals}f}{metric.suffix}"


class WorldMapWidget(QtWidgets.QWidget):
    countryHovered = QtCore.pyqtSignal(str)

    def __init__(self, countries, parent=None):
        super().__init__(parent)
        self.countries = countries
        self.metric = METRICS[0]
        self.hoveredIso = None
        self.selectedIso = None
        self.zoom = 1.0
        self.pan = QtCore.QPointF()
        self._dragPosition = None
        self._dragged = False
        self._pathSize = QtCore.QSize()
        self.setMouseTracking(True)
        self.setMinimumSize(620, 390)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    def setMetric(self, metric):
        self.metric = metric
        self.update()

    def selectCountry(self, iso):
        self.selectedIso = iso
        self.update()

    def _project(self, longitude, latitude):
        margin = 18.0
        width = max(1.0, self.width() - margin * 2)
        height = max(1.0, self.height() - margin * 2)
        x = margin + (longitude + 180.0) / 360.0 * width
        y = margin + (90.0 - latitude) / 180.0 * height
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        point = QtCore.QPointF(x, y)
        return center + (point - center) * self.zoom + self.pan

    def _buildPaths(self):
        for country in self.countries:
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.FillRule.OddEvenFill)
            geometry = country.geometry
            polygons = (
                [geometry["coordinates"]]
                if geometry["type"] == "Polygon"
                else geometry["coordinates"]
            )
            for polygon in polygons:
                for ring in polygon:
                    previous_longitude = None
                    for longitude, latitude, *_ in ring:
                        point = self._project(longitude, latitude)
                        if (
                            previous_longitude is None
                            or abs(longitude - previous_longitude) > 180
                        ):
                            path.moveTo(point)
                        else:
                            path.lineTo(point)
                        previous_longitude = longitude
                    path.closeSubpath()
            country.path = path
        self._pathSize = self.size()

    def _clampPan(self):
        max_x = max(0.0, (self.width() - 36) * (self.zoom - 1.0) / 2)
        max_y = max(0.0, (self.height() - 36) * (self.zoom - 1.0) / 2)
        self.pan.setX(max(-max_x, min(max_x, self.pan.x())))
        self.pan.setY(max(-max_y, min(max_y, self.pan.y())))

    def _colorFor(self, value):
        metric = self.metric
        normalized = max(
            0.0, min(1.0, (value - metric.low) / (metric.high - metric.low))
        )
        low = QtGui.QColor("#3b1f62")
        middle = QtGui.QColor("#27406b")
        high = QtGui.QColor("#1db6a3")
        if normalized < 0.5:
            return self._mix(low, middle, normalized * 2)
        return self._mix(middle, high, (normalized - 0.5) * 2)

    @staticmethod
    def _mix(first, second, amount):
        return QtGui.QColor(
            round(first.red() + (second.red() - first.red()) * amount),
            round(first.green() + (second.green() - first.green()) * amount),
            round(first.blue() + (second.blue() - first.blue()) * amount),
        )

    def paintEvent(self, _event):
        if self._pathSize != self.size():
            self._buildPaths()
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor("#090c12"))

        for country in self.countries:
            if country.path is None:
                continue
            painter.setBrush(
                self._colorFor(country.values[self.metric.key])
            )
            if country.iso == self.selectedIso:
                pen = QtGui.QPen(QtGui.QColor("#ffffff"), 1.8)
            elif country.iso == self.hoveredIso:
                pen = QtGui.QPen(QtGui.QColor("#9db4ff"), 1.5)
            else:
                pen = QtGui.QPen(QtGui.QColor("#111827"), 0.65)
            painter.setPen(pen)
            painter.drawPath(country.path)
        painter.end()

    def mouseMoveEvent(self, event):
        if (
            self._dragPosition is not None
            and event.buttons()
            & (
                QtCore.Qt.MouseButton.LeftButton
                | QtCore.Qt.MouseButton.MiddleButton
                | QtCore.Qt.MouseButton.RightButton
            )
        ):
            delta = event.position() - self._dragPosition
            self._dragPosition = event.position()
            if abs(delta.x()) + abs(delta.y()) > 1:
                self._dragged = True
            if self.zoom > 1.0:
                self.pan += delta
                self._clampPan()
            self._pathSize = QtCore.QSize()
            self.update()
            return
        found = None
        position = event.position()
        for country in reversed(self.countries):
            if country.path is not None and country.path.contains(position):
                found = country
                break
        iso = found.iso if found else None
        if iso != self.hoveredIso:
            self.hoveredIso = iso
            self.countryHovered.emit(iso or "")
            self.update()
        if found:
            value = _metricText(
                self.metric, found.values[self.metric.key]
            )
            QtWidgets.QToolTip.showText(
                event.globalPosition().toPoint(),
                f"<b>{found.name}</b><br>{found.continent}<br>"
                f"{self.metric.label}: <b>{value}</b>",
                self,
            )
        else:
            QtWidgets.QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragPosition = event.position()
            self._dragged = False
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and not self._dragged
            and self.hoveredIso
        ):
            self.selectCountry(self.hoveredIso)
            self.countryHovered.emit(self.hoveredIso)
        self._dragPosition = None
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
            or abs(delta.x()) > abs(delta.y())
        ):
            amount = delta.x() or delta.y()
            self.pan += QtCore.QPointF(amount * 0.35, 0)
            self._clampPan()
        else:
            old_zoom = self.zoom
            factor = 1.15 if delta.y() > 0 else 1 / 1.15
            self.zoom = max(1.0, min(6.0, self.zoom * factor))
            cursor = event.position()
            center = QtCore.QPointF(self.width() / 2, self.height() / 2)
            relative = cursor - center - self.pan
            self.pan = cursor - center - relative * (self.zoom / old_zoom)
            if self.zoom == 1.0:
                self.pan = QtCore.QPointF()
            else:
                self._clampPan()
        self._pathSize = QtCore.QSize()
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.zoom = 1.0
        self.pan = QtCore.QPointF()
        self._pathSize = QtCore.QSize()
        self.update()
        event.accept()

    def leaveEvent(self, event):
        self.hoveredIso = None
        QtWidgets.QToolTip.hideText()
        self.update()
        super().leaveEvent(event)


class Macro3DWidget(QtWidgets.QWidget):
    """Painter-based interactive 3D choropleth with metric-driven elevation."""

    countryHovered = QtCore.pyqtSignal(str)

    def __init__(self, countries, parent=None):
        super().__init__(parent)
        self.countries = countries
        self.metric = METRICS[0]
        self.yaw = -0.08
        self.tilt = 0.52
        self.zoom = 1.0
        self.heightFactor = 1.0
        self.tileMode = False
        self.globeMode = False
        self.pan = QtCore.QPointF()
        self.hoveredIso = None
        self.selectedIso = "USA"
        self._dragPosition = None
        self._dragMode = None
        self._dragged = False
        self._screenPaths = {}
        self._surfaceValueCache = {}
        self._earthRgb = None
        self._globeBaseCache = None
        self._globeBaseKey = None
        self._centers = {
            country.iso: self._geometryCenter(country.geometry)
            for country in countries
        }
        self._countrySegments = {
            country.iso: [
                segment
                for ring in self._outerRings(country)
                for segment in self._segments(ring)
            ]
            for country in countries
        }
        self._fastCountrySegments = {
            iso: [
                (
                    segment[::3] + [segment[-1]]
                    if len(segment) > 8
                    else segment
                )
                for segment in segments
            ]
            for iso, segments in self._countrySegments.items()
        }
        self.setMouseTracking(True)
        self.setMinimumSize(650, 430)
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)

    @staticmethod
    def _geometryCenter(geometry):
        coordinates = []
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"]
        )
        for polygon in polygons:
            if polygon:
                coordinates.extend(polygon[0])
        if not coordinates:
            return 0.0, 0.0
        longitudes = [point[0] for point in coordinates]
        latitudes = [point[1] for point in coordinates]
        return (
            (min(longitudes) + max(longitudes)) / 2,
            (min(latitudes) + max(latitudes)) / 2,
        )

    def setMetric(self, metric):
        self.metric = metric
        self._surfaceValueCache.clear()
        self.update()

    def setTileMode(self, enabled):
        self.tileMode = bool(enabled)
        self.update()

    def setGlobeMode(self, enabled):
        self.globeMode = bool(enabled)
        self.resetView()

    def setHeightFactor(self, factor):
        self.heightFactor = factor
        self.update()

    def selectCountry(self, iso):
        self.selectedIso = iso
        self.update()

    def resetView(self):
        if self.globeMode:
            self.yaw = 0.55
            self.tilt = 0.28
            self.zoom = 1.08
        else:
            self.yaw = -0.08
            self.tilt = 0.52
            self.zoom = 1.0
        self.pan = QtCore.QPointF()
        self.update()

    def _normalized(self, country):
        value = country.values[self.metric.key]
        return max(
            0.02,
            min(
                1.0,
                (value - self.metric.low)
                / (self.metric.high - self.metric.low),
            ),
        )

    def _project(self, longitude, latitude, elevation=0.0):
        if self.globeMode:
            point, _depth = self._projectGlobe(longitude, latitude, elevation)
            return point
        x = longitude / 180.0
        y = -latitude / 180.0
        cosine = math.cos(self.yaw)
        sine = math.sin(self.yaw)
        rotated_x = x * cosine - y * sine
        rotated_y = x * sine + y * cosine
        scale = min(self.width() / 2.25, self.height() / 1.15) * self.zoom
        screen_x = self.width() / 2 + rotated_x * scale
        screen_y = (
            self.height() * 0.57
            + rotated_y * scale * math.sin(self.tilt)
            - elevation
        )
        return QtCore.QPointF(screen_x, screen_y) + self.pan

    def _globeRadius(self, elevation=0.0):
        # Map flat pixel heights into a subtle radial bump on the sphere.
        bump = 0.0
        if elevation:
            reference = max(1.0, min(150.0, self.height() * 0.25) * self.heightFactor)
            bump = 0.16 * (elevation / reference)
        return 1.0 + bump

    def _globeRotated(self, longitude, latitude, elevation=0.0):
        radius = self._globeRadius(elevation)
        lon = math.radians(longitude)
        lat = math.radians(latitude)
        x = radius * math.cos(lat) * math.sin(lon)
        y = radius * math.sin(lat)
        z = radius * math.cos(lat) * math.cos(lon)
        # Yaw around Y, then tilt around X — Earth from space.
        cos_y = math.cos(self.yaw)
        sin_y = math.sin(self.yaw)
        x1 = x * cos_y + z * sin_y
        z1 = -x * sin_y + z * cos_y
        cos_t = math.cos(self.tilt)
        sin_t = math.sin(self.tilt)
        y2 = y * cos_t - z1 * sin_t
        z2 = y * sin_t + z1 * cos_t
        return x1, y2, z2

    def _projectGlobe(self, longitude, latitude, elevation=0.0):
        x, y, z = self._globeRotated(longitude, latitude, elevation)
        scale = min(self.width(), self.height()) * 0.42 * self.zoom
        point = QtCore.QPointF(
            self.width() / 2 + x * scale,
            self.height() / 2 - y * scale,
        ) + self.pan
        return point, z

    def _globeFront(self, longitude, latitude, elevation=0.0):
        return self._globeRotated(longitude, latitude, elevation)[2] > -0.04

    def _loadEarthTexture(self):
        if self._earthRgb is not None:
            return self._earthRgb
        path = Path(__file__).parents[1] / "assets" / "earth_topo.jpg"
        image = QtGui.QImage(str(path))
        if image.isNull():
            self._earthRgb = np.zeros((2, 2, 3), dtype=np.uint8)
            return self._earthRgb
        image = image.convertToFormat(QtGui.QImage.Format.Format_RGBA8888)
        width = image.width()
        height = image.height()
        ptr = image.constBits()
        ptr.setsize(image.sizeInBytes())
        raw = np.frombuffer(ptr, dtype=np.uint8).reshape(
            height, image.bytesPerLine()
        )
        rgba = raw[:, : width * 4].reshape(height, width, 4)
        self._earthRgb = np.ascontiguousarray(rgba[:, :, :3])
        return self._earthRgb

    def _realisticGlobeImage(self):
        dragging = self._dragPosition is not None
        size = 300 if dragging else 640
        key = (
            round(self.yaw, 3),
            round(self.tilt, 3),
            size,
            dragging,
        )
        if self._globeBaseKey == key and self._globeBaseCache is not None:
            return self._globeBaseCache

        earth = self._loadEarthTexture()
        th, tw = earth.shape[0], earth.shape[1]
        ys, xs = np.mgrid[0:size, 0:size]
        vx = (xs + 0.5) / size * 2.0 - 1.0
        vy = 1.0 - (ys + 0.5) / size * 2.0
        r2 = vx * vx + vy * vy
        mask = r2 <= 1.0
        vz = np.zeros_like(vx)
        vz[mask] = np.sqrt(np.maximum(0.0, 1.0 - r2[mask]))

        cos_t = math.cos(self.tilt)
        sin_t = math.sin(self.tilt)
        y1 = vy * cos_t + vz * sin_t
        z1 = -vy * sin_t + vz * cos_t
        x1 = vx
        cos_y = math.cos(self.yaw)
        sin_y = math.sin(self.yaw)
        x = x1 * cos_y - z1 * sin_y
        z = x1 * sin_y + z1 * cos_y
        y = y1

        lat = np.arcsin(np.clip(y, -1.0, 1.0))
        lon = np.arctan2(x, z)
        u = ((lon + math.pi) / (2 * math.pi) * (tw - 1)).astype(np.int32) % tw
        v = ((0.5 * math.pi - lat) / math.pi * (th - 1)).astype(np.int32)
        np.clip(v, 0, th - 1, out=v)

        sampled = earth[v, u].astype(np.float32)
        # Daylight + soft night side, view-space sun over the left shoulder.
        lx, ly, lz = -0.42, 0.38, 0.82
        length = math.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / length, ly / length, lz / length
        ndotl = vx * lx + vy * ly + vz * lz
        light = 0.18 + 0.92 * np.clip(ndotl, 0.0, 1.0)
        # Ocean specular sparkle.
        specular = np.power(np.clip(ndotl, 0.0, 1.0), 28) * 55.0
        lit = sampled * light[..., None]
        lit[..., 0] += specular * 0.55
        lit[..., 1] += specular * 0.7
        lit[..., 2] += specular
        # Thin atmospheric rim near the limb.
        rim = np.clip((r2 - 0.78) / 0.22, 0.0, 1.0)
        lit[..., 0] = lit[..., 0] * (1 - rim * 0.15) + rim * 40
        lit[..., 1] = lit[..., 1] * (1 - rim * 0.1) + rim * 110
        lit[..., 2] = lit[..., 2] * (1 - rim * 0.05) + rim * 200
        lit = np.clip(lit, 0, 255).astype(np.uint8)

        rgba = np.zeros((size, size, 4), dtype=np.uint8)
        rgba[mask, :3] = lit[mask]
        rgba[mask, 3] = 255
        image = QtGui.QImage(
            rgba.data,
            size,
            size,
            size * 4,
            QtGui.QImage.Format.Format_RGBA8888,
        ).copy()
        self._globeBaseCache = image
        self._globeBaseKey = key
        return image

    def _drawRealisticEarth(self, painter):
        image = self._realisticGlobeImage()
        scale = min(self.width(), self.height()) * 0.42 * self.zoom
        center = QtCore.QPointF(
            self.width() / 2 + self.pan.x(),
            self.height() / 2 + self.pan.y(),
        )
        target = QtCore.QRectF(
            center.x() - scale,
            center.y() - scale,
            scale * 2,
            scale * 2,
        )
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform, True
        )
        painter.drawImage(target, image)

    def _drawGlobeCountries(self, painter):
        """Translucent metric choropleth over the realistic Earth."""
        ordered = sorted(
            (
                country
                for country in self.countries
                if country.continent != "Antarctica"
                and self._globeFront(*self._centers[country.iso])
            ),
            key=lambda country: self._globeRotated(*self._centers[country.iso])[2],
        )
        segments_by_country = (
            self._fastCountrySegments
            if self._dragPosition is not None
            else self._countrySegments
        )
        for country in ordered:
            path = QtGui.QPainterPath()
            path.setFillRule(QtCore.Qt.FillRule.OddEvenFill)
            for segment in segments_by_country[country.iso]:
                points = []
                for longitude, latitude in segment:
                    if not self._globeFront(longitude, latitude):
                        if len(points) >= 3:
                            path.moveTo(points[0])
                            for point in points[1:]:
                                path.lineTo(point)
                            path.closeSubpath()
                        points = []
                        continue
                    points.append(self._project(longitude, latitude))
                if len(points) >= 3:
                    path.moveTo(points[0])
                    for point in points[1:]:
                        path.lineTo(point)
                    path.closeSubpath()
            if path.isEmpty():
                continue
            fill = self._colorFor(country)
            if country.iso == self.selectedIso:
                fill.setAlpha(165)
            elif country.iso == self.hoveredIso:
                fill.setAlpha(145)
            else:
                fill.setAlpha(105)
            painter.setBrush(fill)
            if country.iso == self.selectedIso:
                painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 1.8))
            elif country.iso == self.hoveredIso:
                painter.setPen(QtGui.QPen(QtGui.QColor("#d7e0ff"), 1.3))
            else:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 35), 0.6))
            painter.drawPath(path)
            self._screenPaths[country.iso] = path

    def _height(self, country):
        return self._heightForNormalized(self._normalized(country))

    def _heightForNormalized(self, normalized):
        return (
            normalized
            * min(150.0, self.height() * 0.25)
            * self.heightFactor
        )

    def _colorFor(self, country):
        return self._colorForNormalized(self._normalized(country))

    def _colorForNormalized(self, normalized):
        low = QtGui.QColor("#412469")
        middle = QtGui.QColor("#31527e")
        high = QtGui.QColor("#20c4ad")
        if normalized < 0.5:
            return WorldMapWidget._mix(low, middle, normalized * 2)
        return WorldMapWidget._mix(
            middle, high, (normalized - 0.5) * 2
        )

    def _surfaceNormalized(self, longitude, latitude):
        key = (
            self.metric.key,
            round(longitude, 3),
            round(latitude, 3),
        )
        cached = self._surfaceValueCache.get(key)
        if cached is not None:
            return cached
        nearest = []
        latitude_scale = max(0.25, math.cos(math.radians(latitude)))
        for country in self.countries:
            if country.continent == "Antarctica":
                continue
            center_longitude, center_latitude = self._centers[country.iso]
            longitude_delta = abs(longitude - center_longitude)
            longitude_delta = min(longitude_delta, 360 - longitude_delta)
            distance = (
                (longitude_delta * latitude_scale) ** 2
                + (latitude - center_latitude) ** 2
            )
            nearest.append((distance, self._normalized(country)))
        nearest.sort(key=lambda item: item[0])
        weighted_total = 0.0
        total_weight = 0.0
        for distance, value in nearest[:6]:
            weight = 1.0 / (distance + 120.0)
            weighted_total += value * weight
            total_weight += weight
        result = weighted_total / total_weight if total_weight else 0.0
        self._surfaceValueCache[key] = result
        return result

    @staticmethod
    def _outerRings(country):
        geometry = country.geometry
        polygons = (
            [geometry["coordinates"]]
            if geometry["type"] == "Polygon"
            else geometry["coordinates"]
        )
        return [polygon[0] for polygon in polygons if polygon]

    def _segments(self, ring):
        segments = []
        current = []
        previous_longitude = None
        for longitude, latitude, *_ in ring:
            if (
                previous_longitude is not None
                and abs(longitude - previous_longitude) > 180
            ):
                if len(current) >= 3:
                    segments.append(current)
                current = []
            current.append((longitude, latitude))
            previous_longitude = longitude
        if len(current) >= 3:
            segments.append(current)
        return segments

    def _drawGround(self, painter):
        if self.globeMode:
            scale = min(self.width(), self.height()) * 0.42 * self.zoom
            center = QtCore.QPointF(
                self.width() / 2 + self.pan.x(),
                self.height() / 2 + self.pan.y(),
            )
            glow = QtGui.QRadialGradient(center, scale * 1.12)
            glow.setColorAt(0.84, QtGui.QColor(120, 170, 255, 0))
            glow.setColorAt(0.93, QtGui.QColor(140, 190, 255, 70))
            glow.setColorAt(1.0, QtGui.QColor(160, 200, 255, 0))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(center, scale * 1.12, scale * 1.12)
            return
        plane = QtGui.QPolygonF(
            (
                self._project(-180, -85),
                self._project(180, -85),
                self._project(180, 85),
                self._project(-180, 85),
            )
        )
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#090c12"))
        painter.drawPolygon(plane)

    def _drawSurface(self, painter):
        cells = []
        if self._dragPosition is not None:
            longitude_step = 15
            latitude_step = 10
        else:
            longitude_step = 10
            latitude_step = 5
        for latitude in range(-80, 80, latitude_step):
            for longitude in range(-180, 180, longitude_step):
                coordinates = (
                    (longitude, latitude),
                    (longitude + longitude_step, latitude),
                    (longitude + longitude_step, latitude + latitude_step),
                    (longitude, latitude + latitude_step),
                )
                mid_lon = longitude + longitude_step / 2
                mid_lat = latitude + latitude_step / 2
                if self.globeMode and not self._globeFront(mid_lon, mid_lat):
                    continue
                values = [
                    self._surfaceNormalized(point_longitude, point_latitude)
                    for point_longitude, point_latitude in coordinates
                ]
                projected = []
                depths = []
                for (point_longitude, point_latitude), value in zip(
                    coordinates, values
                ):
                    elevation = self._heightForNormalized(value)
                    if self.globeMode:
                        point, depth = self._projectGlobe(
                            point_longitude, point_latitude, elevation
                        )
                    else:
                        point = self._project(
                            point_longitude, point_latitude, elevation
                        )
                        depth = point.y()
                    projected.append(point)
                    depths.append(depth)
                cells.append(
                    (
                        sum(depths) / 4,
                        QtGui.QPolygonF(projected),
                        sum(values) / 4,
                    )
                )

        painter.save()
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, False
        )
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        for _depth, polygon, normalized in sorted(
            cells, key=lambda cell: cell[0]
        ):
            painter.setBrush(self._colorForNormalized(normalized))
            painter.drawPolygon(polygon)
        painter.restore()

        segments_by_country = self._fastCountrySegments
        for country in self.countries:
            if country.continent == "Antarctica":
                continue
            center_lon, center_lat = self._centers[country.iso]
            if self.globeMode and not self._globeFront(center_lon, center_lat):
                continue
            ground_outline = QtGui.QPainterPath()
            surface_outline = QtGui.QPainterPath()
            for segment in segments_by_country[country.iso]:
                if self.globeMode:
                    visible = [
                        (longitude, latitude)
                        for longitude, latitude in segment
                        if self._globeFront(longitude, latitude)
                    ]
                    if len(visible) < 3:
                        continue
                    ground_points = [
                        self._project(longitude, latitude)
                        for longitude, latitude in visible
                    ]
                    surface_points = [
                        self._project(
                            longitude,
                            latitude,
                            self._heightForNormalized(
                                self._surfaceNormalized(longitude, latitude)
                            )
                            + 1.0,
                        )
                        for longitude, latitude in visible
                    ]
                else:
                    ground_points = [
                        self._project(longitude, latitude)
                        for longitude, latitude in segment
                    ]
                    surface_points = [
                        self._project(
                            longitude,
                            latitude,
                            self._heightForNormalized(
                                self._surfaceNormalized(longitude, latitude)
                            )
                            + 1.0,
                        )
                        for longitude, latitude in segment
                    ]
                ground_outline.moveTo(ground_points[0])
                surface_outline.moveTo(surface_points[0])
                for point in ground_points[1:]:
                    ground_outline.lineTo(point)
                for point in surface_points[1:]:
                    surface_outline.lineTo(point)
                ground_outline.closeSubpath()
                surface_outline.closeSubpath()
            if ground_outline.isEmpty():
                continue
            if country.iso == self.selectedIso:
                ground_pen = QtGui.QPen(QtGui.QColor("#ffffff"), 1.8)
            else:
                ground_pen = QtGui.QPen(QtGui.QColor("#34445f"), 0.75)
            painter.setPen(ground_pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawPath(ground_outline)
            if country.iso == self.hoveredIso:
                surface_pen = QtGui.QPen(QtGui.QColor("#d7e0ff"), 2.0)
            elif country.iso == self.selectedIso:
                surface_pen = QtGui.QPen(QtGui.QColor("#9db4ff"), 1.4)
            else:
                surface_pen = QtGui.QPen(QtGui.QColor("#1a2942"), 0.75)
            painter.setPen(surface_pen)
            painter.drawPath(surface_outline)
            self._screenPaths[country.iso] = surface_outline

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing,
            self._dragPosition is None,
        )
        painter.fillRect(self.rect(), QtGui.QColor("#090c12"))
        self._drawGround(painter)
        self._screenPaths = {}
        if self.globeMode:
            self._drawRealisticEarth(painter)
            if self.tileMode:
                pass  # fall through to extruded tiles on top of Earth
            else:
                self._drawGlobeCountries(painter)
                painter.end()
                return
        elif not self.tileMode:
            self._drawSurface(painter)
            painter.end()
            return

        def _sort_key(country):
            lon, lat = self._centers[country.iso]
            if self.globeMode:
                return self._globeRotated(lon, lat)[2]
            return self._project(lon, lat).y()

        ordered = sorted(
            (
                country
                for country in self.countries
                if country.continent != "Antarctica"
                and (
                    not self.globeMode
                    or self._globeFront(*self._centers[country.iso])
                )
            ),
            key=_sort_key,
        )
        for country in ordered:
            height = self._height(country)
            roof_color = self._colorFor(country)
            side_color = roof_color.darker(190)
            side_color.setAlpha(205)
            roof_path = QtGui.QPainterPath()
            roof_path.setFillRule(QtCore.Qt.FillRule.OddEvenFill)
            wall_path = QtGui.QPainterPath()
            segments = (
                self._fastCountrySegments[country.iso]
                if self._dragPosition is not None
                else self._countrySegments[country.iso]
            )
            for segment in segments:
                if self.globeMode:
                    points = [
                        (longitude, latitude)
                        for longitude, latitude in segment
                        if self._globeFront(longitude, latitude, height * 0.2)
                    ]
                    if len(points) < 3:
                        continue
                    roof_points = [
                        self._project(longitude, latitude, height)
                        for longitude, latitude in points
                    ]
                    ground_points = [
                        self._project(longitude, latitude)
                        for longitude, latitude in points
                    ]
                    edge_count = len(points)
                else:
                    roof_points = [
                        self._project(longitude, latitude, height)
                        for longitude, latitude in segment
                    ]
                    ground_points = [
                        self._project(longitude, latitude)
                        for longitude, latitude in segment
                    ]
                    edge_count = len(segment)
                if self._dragPosition is None and not self.globeMode:
                    for index in range(edge_count - 1):
                        wall = QtGui.QPolygonF(
                            (
                                ground_points[index],
                                ground_points[index + 1],
                                roof_points[index + 1],
                                roof_points[index],
                            )
                        )
                        wall_path.addPolygon(wall)
                roof_path.moveTo(roof_points[0])
                for point in roof_points[1:]:
                    roof_path.lineTo(point)
                roof_path.closeSubpath()

            if not wall_path.isEmpty():
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(side_color)
                painter.drawPath(wall_path)

            if roof_path.isEmpty():
                continue
            if country.iso == self.selectedIso:
                pen = QtGui.QPen(QtGui.QColor("#ffffff"), 2.0)
            elif country.iso == self.hoveredIso:
                pen = QtGui.QPen(QtGui.QColor("#b8c8ff"), 1.6)
            else:
                pen = QtGui.QPen(QtGui.QColor("#101827"), 0.7)
            painter.setPen(pen)
            painter.setBrush(roof_color)
            painter.drawPath(roof_path)
            self._screenPaths[country.iso] = roof_path
        painter.end()

    def _countryAt(self, position):
        for country in reversed(self.countries):
            path = self._screenPaths.get(country.iso)
            if path is not None and path.contains(position):
                return country
        return None

    def mousePressEvent(self, event):
        if event.button() in {
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.MiddleButton,
            QtCore.Qt.MouseButton.RightButton,
        }:
            self._dragPosition = event.position()
            self._dragged = False
            self._dragMode = (
                "pan"
                if (
                    event.button()
                    in {
                        QtCore.Qt.MouseButton.MiddleButton,
                        QtCore.Qt.MouseButton.RightButton,
                    }
                    or event.modifiers()
                    & QtCore.Qt.KeyboardModifier.ShiftModifier
                )
                else "rotate"
            )
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._dragPosition is not None
            and event.buttons() & QtCore.Qt.MouseButton.LeftButton
        ):
            delta = event.position() - self._dragPosition
            self._dragPosition = event.position()
            if abs(delta.x()) + abs(delta.y()) > 1:
                self._dragged = True
            if self._dragMode == "pan":
                self.pan += delta
            elif self.globeMode:
                self.yaw -= delta.x() * 0.012
                self.tilt = max(
                    -1.25, min(1.25, self.tilt - delta.y() * 0.01)
                )
            else:
                self.yaw -= delta.x() * 0.008
                self.tilt = max(
                    0.16, min(1.15, self.tilt - delta.y() * 0.006)
                )
            self.update()
            return

        country = self._countryAt(event.position())
        iso = country.iso if country else None
        if iso != self.hoveredIso:
            self.hoveredIso = iso
            self.countryHovered.emit(iso or "")
            self.update()
        if country:
            QtWidgets.QToolTip.showText(
                event.globalPosition().toPoint(),
                f"<b>{country.name}</b><br>{self.metric.label}: "
                f"<b>{_metricText(self.metric, country.values[self.metric.key])}</b>",
                self,
            )
        else:
            QtWidgets.QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and not self._dragged
        ):
            country = self._countryAt(event.position())
            if country:
                self.selectCountry(country.iso)
                self.countryHovered.emit(country.iso)
        self._dragPosition = None
        self._dragMode = None
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.update()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta()
        if (
            event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier
            or abs(delta.x()) > abs(delta.y())
        ):
            amount = delta.x() or delta.y()
            self.pan += QtCore.QPointF(amount * 0.35, 0)
        else:
            factor = 1.12 if delta.y() > 0 else 1 / 1.12
            if self.globeMode:
                self.zoom = max(0.55, min(4.0, self.zoom * factor))
            else:
                self.zoom = max(0.65, min(3.2, self.zoom * factor))
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.resetView()
        event.accept()


class Macro3DTab(QtWidgets.QWidget):
    def __init__(self, countries, parent=None):
        super().__init__(parent)
        self.countries = countries
        self.byIso = {country.iso: country for country in countries}
        self.metric = METRICS[0]
        self._buildUi()
        self._showCountry(self.byIso.get("USA") or countries[0])

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("macroToolbar")
        controls = QtWidgets.QHBoxLayout(toolbar)
        controls.setContentsMargins(14, 9, 14, 9)
        title = QtWidgets.QLabel("3D MACRO VIEWER")
        title.setObjectName("macroTitle")
        controls.addWidget(title)
        badge = QtWidgets.QLabel("HEIGHT = METRIC VALUE")
        badge.setObjectName("demoBadge")
        controls.addWidget(badge)
        controls.addStretch()
        controls.addWidget(QtWidgets.QLabel("Metric"))
        self.metricSelector = QtWidgets.QComboBox()
        for metric in METRICS:
            self.metricSelector.addItem(metric.label, metric.key)
        self.metricSelector.currentIndexChanged.connect(self._metricChanged)
        controls.addWidget(self.metricSelector)
        controls.addWidget(QtWidgets.QLabel("Height"))
        self.heightSlider = QtWidgets.QSlider(
            QtCore.Qt.Orientation.Horizontal
        )
        self.heightSlider.setRange(35, 180)
        self.heightSlider.setValue(100)
        self.heightSlider.setFixedWidth(120)
        self.heightSlider.valueChanged.connect(
            lambda value: self.viewer.setHeightFactor(value / 100)
        )
        controls.addWidget(self.heightSlider)
        reset = QtWidgets.QPushButton("Reset view")
        reset.clicked.connect(self._reset)
        controls.addWidget(reset)
        root.addWidget(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        viewer_panel = QtWidgets.QWidget()
        viewer_layout = QtWidgets.QVBoxLayout(viewer_panel)
        viewer_layout.setContentsMargins(10, 10, 8, 8)
        self.viewer = Macro3DWidget(self.countries)
        self.viewer.countryHovered.connect(self._hoveredCountry)
        viewer_layout.addWidget(self.viewer, 1)
        hint = QtWidgets.QLabel(
            "Drag to rotate · Wheel to zoom · Click a country · Double-click to reset"
        )
        hint.setObjectName("legendText")
        viewer_layout.addWidget(hint)
        splitter.addWidget(viewer_panel)
        splitter.addWidget(self._detailPanel())
        splitter.setSizes([1040, 260])
        root.addWidget(splitter, 1)

    def _detailPanel(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("macroDetails")
        panel.setMinimumWidth(240)
        panel.setMaximumWidth(320)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        self.countryName = QtWidgets.QLabel()
        self.countryName.setObjectName("countryName")
        self.countryName.setWordWrap(True)
        layout.addWidget(self.countryName)
        self.region = QtWidgets.QLabel()
        self.region.setObjectName("countryRegion")
        layout.addWidget(self.region)
        layout.addSpacing(18)
        self.value = QtWidgets.QLabel()
        self.value.setObjectName("primaryValue")
        layout.addWidget(self.value)
        self.metricName = QtWidgets.QLabel()
        self.metricName.setObjectName("countryRegion")
        layout.addWidget(self.metricName)
        layout.addSpacing(14)
        explanation = QtWidgets.QLabel(
            "Country elevation represents the selected metric. "
            "Higher values rise farther above the map plane."
        )
        explanation.setObjectName("factName")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addStretch()
        return panel

    def _metricChanged(self, index):
        self.metric = METRIC_BY_KEY[self.metricSelector.itemData(index)]
        self.viewer.setMetric(self.metric)
        if self.viewer.selectedIso in self.byIso:
            self._showCountry(self.byIso[self.viewer.selectedIso])

    def _hoveredCountry(self, iso):
        if iso in self.byIso:
            self._showCountry(self.byIso[iso])

    def _showCountry(self, country):
        self.viewer.selectCountry(country.iso)
        self.countryName.setText(country.name)
        self.region.setText(country.continent)
        self.value.setText(
            _metricText(self.metric, country.values[self.metric.key])
        )
        self.metricName.setText(self.metric.label)

    def _reset(self):
        self.heightSlider.setValue(100)
        self.viewer.resetView()



class ColorScaleBar(QtWidgets.QWidget):
    """TradingView-style percentage color legend for the active metric."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.metric = METRICS[0]
        self.setFixedHeight(16)
        self.setFixedWidth(260)

    def setMetric(self, metric):
        self.metric = metric
        self.update()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        margin_x = 0
        bar_top = 1
        bar_height = 2
        width = max(1, self.width() - margin_x * 2)
        rect = QtCore.QRectF(margin_x, bar_top, width, bar_height)
        gradient = QtGui.QLinearGradient(rect.left(), 0, rect.right(), 0)
        gradient.setColorAt(0.0, QtGui.QColor("#3b1f62"))
        gradient.setColorAt(0.5, QtGui.QColor("#27406b"))
        gradient.setColorAt(1.0, QtGui.QColor("#1db6a3"))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 1.5, 1.5)

        ticks = 5
        painter.setPen(QtGui.QPen(QtGui.QColor("#8b949e")))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        for index in range(ticks):
            amount = index / (ticks - 1)
            value = self.metric.low + (
                self.metric.high - self.metric.low
            ) * amount
            label = _metricText(self.metric, value)
            x = margin_x + width * amount
            text_rect = QtCore.QRectF(x - 28, bar_top + bar_height + 1, 56, 12)
            align = QtCore.Qt.AlignmentFlag.AlignCenter
            if index == 0:
                align = (
                    QtCore.Qt.AlignmentFlag.AlignLeft
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                text_rect = QtCore.QRectF(x, bar_top + bar_height + 1, 56, 12)
            elif index == ticks - 1:
                align = (
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                text_rect = QtCore.QRectF(x - 56, bar_top + bar_height + 1, 56, 12)
            painter.drawText(text_rect, int(align), label)
        painter.end()


class YearTimeline(QtWidgets.QWidget):
    """Full-width year selector with major tick labels."""

    yearChanged = QtCore.pyqtSignal(int)

    def __init__(self, start=YEAR_START, end=YEAR_END, parent=None):
        super().__init__(parent)
        self.start = start
        self.end = end
        self.year = end
        self._dragging = False
        self.setFixedHeight(34)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def setYear(self, year):
        year = max(self.start, min(self.end, int(year)))
        if year == self.year:
            return
        self.year = year
        self.update()
        self.yearChanged.emit(self.year)

    def _xForYear(self, year):
        margin = 10
        width = max(1, self.width() - margin * 2)
        amount = (year - self.start) / max(1, self.end - self.start)
        return margin + width * amount

    def _yearForX(self, x):
        margin = 10
        width = max(1, self.width() - margin * 2)
        amount = max(0.0, min(1.0, (x - margin) / width))
        return int(round(self.start + amount * (self.end - self.start)))

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        margin = 10
        track_y = 12
        track = QtCore.QRectF(
            margin, track_y, max(1, self.width() - margin * 2), 3
        )
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor("#2a303b"))
        painter.drawRoundedRect(track, 2, 2)

        filled = QtCore.QRectF(
            track.left(),
            track.top(),
            max(0.0, self._xForYear(self.year) - track.left()),
            track.height(),
        )
        painter.setBrush(QtGui.QColor("#4d6dff"))
        painter.drawRoundedRect(filled, 2, 2)

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        span = self.end - self.start
        step = 28 if span > 80 else 14
        first_label = ((self.start + step - 1) // step) * step
        for year in range(first_label, self.end + 1, step):
            x = self._xForYear(year)
            painter.setPen(QtGui.QPen(QtGui.QColor("#3a4250")))
            painter.drawLine(
                QtCore.QPointF(x, track_y + 6),
                QtCore.QPointF(x, track_y + 11),
            )
            painter.setPen(QtGui.QPen(QtGui.QColor("#8b949e")))
            painter.drawText(
                QtCore.QRectF(x - 22, track_y + 12, 44, 14),
                int(QtCore.Qt.AlignmentFlag.AlignCenter),
                str(year),
            )

        handle_x = self._xForYear(self.year)
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#6f8cff"), 1.2))
        painter.drawEllipse(QtCore.QPointF(handle_x, track_y + 1.5), 5, 5)
        painter.setPen(QtGui.QPen(QtGui.QColor("#c9d1d9")))
        painter.drawText(
            QtCore.QRectF(handle_x - 28, 0, 56, 12),
            int(QtCore.Qt.AlignmentFlag.AlignCenter),
            str(self.year),
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setYear(self._yearForX(event.position().x()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.setYear(self._yearForX(event.position().x()))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        step = 1 if event.angleDelta().y() > 0 else -1
        self.setYear(self.year + step)
        event.accept()


class MacroMapTab(QtWidgets.QWidget):
    def __init__(self, countries=None, parent=None):
        super().__init__(parent)
        self.countries = countries or loadCountries()
        self.byIso = {country.iso: country for country in self.countries}
        self.metric = METRIC_BY_KEY["inflation"]
        self.year = YEAR_END
        self._buildUi()
        self._setMetric(self.metric.key)
        self._selectCountry(self.byIso.get("USA") or self.countries[0])
        self._updateRankings()

    def _buildUi(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QtWidgets.QWidget()
        toolbar.setObjectName("macroToolbar")
        controls = QtWidgets.QHBoxLayout(toolbar)
        controls.setContentsMargins(14, 9, 14, 9)
        controls.setSpacing(7)
        self.indicatorSearch = QtWidgets.QLineEdit()
        self.indicatorSearch.setObjectName("indicatorSearch")
        self.indicatorSearch.setPlaceholderText("⌕  Search indicators")
        self.indicatorSearch.setClearButtonEnabled(True)
        self.indicatorSearch.setMinimumWidth(165)
        self.indicatorSearch.setMaximumWidth(220)
        completer = QtWidgets.QCompleter(
            [metric.label for metric in METRICS], self.indicatorSearch
        )
        completer.setCaseSensitivity(
            QtCore.Qt.CaseSensitivity.CaseInsensitive
        )
        completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        completer.activated[str].connect(self._indicatorChosen)
        self.indicatorSearch.setCompleter(completer)
        self.indicatorSearch.returnPressed.connect(
            self._searchIndicator
        )
        controls.addWidget(self.indicatorSearch)

        self.metricGroup = QtWidgets.QButtonGroup(self)
        self.metricGroup.setExclusive(True)
        self.metricButtons = {}
        for key in ("inflation", "rate", "growth", "unemployment", "debt"):
            metric = METRIC_BY_KEY[key]
            button = QtWidgets.QPushButton(metric.label)
            button.setObjectName("metricChip")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _, metric_key=key: self._setMetric(metric_key)
            )
            self.metricGroup.addButton(button)
            self.metricButtons[key] = button
            controls.addWidget(button)
        controls.addStretch()

        mode_wrap = QtWidgets.QWidget()
        mode_wrap.setObjectName("viewModeGroup")
        mode_row = QtWidgets.QHBoxLayout(mode_wrap)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(0)
        self.modeGroup = QtWidgets.QButtonGroup(self)
        self.modeGroup.setExclusive(True)
        self.view2DButton = QtWidgets.QPushButton("2D")
        self.view2DButton.setObjectName("viewModeLeft")
        self.view2DButton.setCheckable(True)
        self.view2DButton.setChecked(True)
        self.view3DButton = QtWidgets.QPushButton("3D")
        self.view3DButton.setObjectName("viewModeRight")
        self.view3DButton.setCheckable(True)
        self.modeGroup.addButton(self.view2DButton)
        self.modeGroup.addButton(self.view3DButton)
        self.view2DButton.clicked.connect(lambda: self._toggle3D(False))
        self.view3DButton.clicked.connect(lambda: self._toggle3D(True))
        mode_row.addWidget(self.view2DButton)
        mode_row.addWidget(self.view3DButton)
        controls.addWidget(mode_wrap)

        self.projectionCombo = QtWidgets.QComboBox()
        self.projectionCombo.setObjectName("viewOptionCombo")
        self.projectionCombo.addItem("Flat 3D", "flat")
        self.projectionCombo.addItem("Globe", "globe")
        self.projectionCombo.setToolTip("3D projection")
        self.projectionCombo.setVisible(False)
        self.projectionCombo.currentIndexChanged.connect(self._projectionChanged)
        controls.addWidget(self.projectionCombo)

        self.surfaceCombo = QtWidgets.QComboBox()
        self.surfaceCombo.setObjectName("viewOptionCombo")
        self.surfaceCombo.addItem("Continuous surface", "continuous")
        self.surfaceCombo.addItem("Country tiles", "tiles")
        self.surfaceCombo.setToolTip("How metric values are drawn")
        self.surfaceCombo.setVisible(False)
        self.surfaceCombo.currentIndexChanged.connect(self._surfaceChanged)
        controls.addWidget(self.surfaceCombo)

        self.heightCombo = QtWidgets.QComboBox()
        self.heightCombo.setObjectName("viewOptionCombo")
        for label, value in (
            ("Height 50%", 50),
            ("Height 75%", 75),
            ("Height 100%", 100),
            ("Height 125%", 125),
            ("Height 150%", 150),
        ):
            self.heightCombo.addItem(label, value)
        self.heightCombo.setCurrentIndex(2)
        self.heightCombo.setToolTip("Metric elevation scale")
        self.heightCombo.setVisible(False)
        self.heightCombo.currentIndexChanged.connect(self._heightChanged)
        controls.addWidget(self.heightCombo)

        root.addWidget(toolbar)

        content = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        content.setChildrenCollapsible(False)
        map_panel = QtWidgets.QWidget()
        map_layout = QtWidgets.QVBoxLayout(map_panel)
        map_layout.setContentsMargins(12, 12, 8, 4)
        self.map = WorldMapWidget(self.countries)
        self.map.countryHovered.connect(self._hoveredCountry)
        self.map3d = Macro3DWidget(self.countries)
        self.map3d.countryHovered.connect(self._hoveredCountry)
        self.mapStack = QtWidgets.QStackedWidget()
        self.mapStack.addWidget(self.map)
        self.mapStack.addWidget(self.map3d)
        map_layout.addWidget(self.mapStack, 1)
        map_layout.addWidget(self._timelinePanel())
        content.addWidget(map_panel)
        content.addWidget(self._detailPanel())
        content.setHandleWidth(0)
        content.setSizes([980, 310])
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 0)
        root.addWidget(content, 1)

    def _timelinePanel(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("timelinePanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(1)
        scale_row = QtWidgets.QHBoxLayout()
        scale_row.setContentsMargins(0, 0, 0, 0)
        scale_row.setSpacing(0)
        self.colorScale = ColorScaleBar()
        scale_row.addWidget(self.colorScale)
        scale_row.addStretch(1)
        layout.addLayout(scale_row)
        self.yearTimeline = YearTimeline()
        self.yearTimeline.yearChanged.connect(self._yearChanged)
        layout.addWidget(self.yearTimeline)
        return panel

    def _detailPanel(self):
        panel = QtWidgets.QWidget()
        panel.setObjectName("macroDetails")
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(360)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(9)
        country_label = QtWidgets.QLabel("COUNTRY")
        country_label.setObjectName("sectionTitle")
        layout.addWidget(country_label)
        self.countrySelector = QtWidgets.QComboBox()
        self.countrySelector.setEditable(True)
        self.countrySelector.setInsertPolicy(
            QtWidgets.QComboBox.InsertPolicy.NoInsert
        )
        for country in self.countries:
            self.countrySelector.addItem(country.name, country.iso)
        self.countrySelector.setCurrentIndex(-1)
        self.countrySelector.currentIndexChanged.connect(
            self._countrySelected
        )
        layout.addWidget(self.countrySelector)
        layout.addSpacing(7)
        self.countryName = QtWidgets.QLabel()
        self.countryName.setObjectName("countryName")
        self.countryName.setWordWrap(True)
        layout.addWidget(self.countryName)
        self.countryRegion = QtWidgets.QLabel()
        self.countryRegion.setObjectName("countryRegion")
        layout.addWidget(self.countryRegion)
        layout.addSpacing(8)
        self.primaryValue = QtWidgets.QLabel()
        self.primaryValue.setObjectName("primaryValue")
        layout.addWidget(self.primaryValue)
        self.primaryLabel = QtWidgets.QLabel()
        self.primaryLabel.setObjectName("countryRegion")
        layout.addWidget(self.primaryLabel)
        layout.addSpacing(10)
        self.factLabels = {}
        for metric in METRICS:
            row = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(metric.label)
            label.setObjectName("factName")
            row.addWidget(label)
            row.addStretch()
            value = QtWidgets.QLabel()
            value.setObjectName("factValue")
            row.addWidget(value)
            layout.addLayout(row)
            self.factLabels[metric.key] = value
        layout.addSpacing(12)
        ranking_title = QtWidgets.QLabel("METRIC LEADERS")
        ranking_title.setObjectName("sectionTitle")
        layout.addWidget(ranking_title)
        self.rankings = QtWidgets.QListWidget()
        self.rankings.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.rankings.itemClicked.connect(self._rankingClicked)
        layout.addWidget(self.rankings, 1)
        return panel

    def _setMetric(self, key):
        if key not in METRIC_BY_KEY:
            return
        self.metric = METRIC_BY_KEY[key]
        for button_key, button in self.metricButtons.items():
            with QtCore.QSignalBlocker(button):
                button.setChecked(button_key == key)
        self.map.setMetric(self.metric)
        self.map3d.setMetric(self.metric)
        self.colorScale.setMetric(self.metric)
        self._updateRankings()
        if self.map.selectedIso:
            self._selectCountry(self.byIso[self.map.selectedIso])

    def _yearChanged(self, year):
        self.year = year
        for country in self.countries:
            country.values = country.valuesForYear(year)
        self.map3d._surfaceValueCache.clear()
        self.map.update()
        self.map3d.update()
        self._updateRankings()
        if self.map.selectedIso in self.byIso:
            self._selectCountry(
                self.byIso[self.map.selectedIso], update_combo=False
            )

    def _indicatorChosen(self, label):
        for metric in METRICS:
            if metric.label == label:
                self._setMetric(metric.key)
                self.indicatorSearch.clear()
                return

    def _searchIndicator(self):
        query = self.indicatorSearch.text().strip().lower()
        for metric in METRICS:
            if query in metric.label.lower():
                self._setMetric(metric.key)
                self.indicatorSearch.clear()
                return

    def _countrySelected(self, index):
        iso = self.countrySelector.itemData(index)
        if iso in self.byIso:
            self.map.selectCountry(iso)
            self.map3d.selectCountry(iso)
            self._selectCountry(self.byIso[iso], update_combo=False)

    def _hoveredCountry(self, iso):
        if iso in self.byIso:
            self._selectCountry(self.byIso[iso])

    def _selectCountry(self, country, update_combo=True):
        self.map.selectCountry(country.iso)
        self.map3d.selectCountry(country.iso)
        if update_combo:
            index = self.countrySelector.findData(country.iso)
            with QtCore.QSignalBlocker(self.countrySelector):
                self.countrySelector.setCurrentIndex(index)
        self.countryName.setText(country.name)
        population = (
            f"{country.population / 1_000_000:.1f}M"
            if country.population >= 1_000_000
            else f"{country.population / 1_000:.0f}K"
        )
        self.countryRegion.setText(
            f"{country.continent}  ·  Population {population}"
        )
        value = country.values[self.metric.key]
        self.primaryValue.setText(_metricText(self.metric, value))
        self.primaryLabel.setText(self.metric.label)
        for metric in METRICS:
            self.factLabels[metric.key].setText(
                _metricText(metric, country.values[metric.key])
            )

    def _toggle3D(self, enabled):
        self.mapStack.setCurrentWidget(self.map3d if enabled else self.map)
        with QtCore.QSignalBlocker(self.view2DButton):
            self.view2DButton.setChecked(not enabled)
        with QtCore.QSignalBlocker(self.view3DButton):
            self.view3DButton.setChecked(enabled)
        self.projectionCombo.setVisible(enabled)
        self.surfaceCombo.setVisible(enabled)
        self.heightCombo.setVisible(enabled)
        if not enabled:
            self.map3d.setGlobeMode(False)
            with QtCore.QSignalBlocker(self.projectionCombo):
                self.projectionCombo.setCurrentIndex(0)
        if enabled:
            self.map3d.setMetric(self.metric)
            self._projectionChanged(self.projectionCombo.currentIndex())
            self._surfaceChanged(self.surfaceCombo.currentIndex())
            self._heightChanged(self.heightCombo.currentIndex())

    def _projectionChanged(self, index):
        mode = self.projectionCombo.itemData(index)
        self.map3d.setGlobeMode(mode == "globe")

    def _surfaceChanged(self, index):
        mode = self.surfaceCombo.itemData(index)
        self.map3d.setTileMode(mode == "tiles")

    def _heightChanged(self, index):
        value = self.heightCombo.itemData(index)
        if value is None:
            return
        self.map3d.setHeightFactor(value / 100)

    def _updateRankings(self):
        self.rankings.clear()
        ordered = sorted(
            self.countries,
            key=lambda country: country.values[self.metric.key],
            reverse=True,
        )[:8]
        for rank, country in enumerate(ordered, 1):
            item = QtWidgets.QListWidgetItem(
                f"{rank:>2}.  {country.name}\n"
                f"      {_metricText(self.metric, country.values[self.metric.key])}"
            )
            item.setData(QtCore.Qt.ItemDataRole.UserRole, country.iso)
            self.rankings.addItem(item)

    def _rankingClicked(self, item):
        iso = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if iso in self.byIso:
            self._selectCountry(self.byIso[iso])


class MacroPlaceholder(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("placeholderTitle")
        layout.addWidget(heading)
        status = QtWidgets.QLabel("Macro module ready for implementation")
        status.setObjectName("placeholderStatus")
        layout.addWidget(status)


class MacroView(QtWidgets.QWidget):
    """Container for the growing collection of macro-analysis tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("macroView")
        self.setStyleSheet(f"""
            QWidget#macroView, QWidget#macroView QWidget {{
                color: {FG};
                background: #090c12;
            }}
            QWidget#macroView *:focus {{
                outline: none;
            }}
            QTabWidget#macroTabs {{
                border: 0px;
                background: #090c12;
                outline: none;
            }}
            QTabWidget#macroTabs::pane {{
                border: 0px;
                margin: 0px;
                padding: 0px;
                top: 0px;
                background: #090c12;
            }}
            QTabWidget#macroTabs > QTabBar {{
                border: 0px;
                outline: none;
                background: #090c12;
            }}
            QTabWidget#macroTabs > QTabBar::tab {{
                color: {MUTED};
                background: #090c12;
                border: 0px;
                outline: none;
                margin: 0px;
                padding: 9px 18px;
            }}
            QTabWidget#macroTabs > QTabBar::tab:selected {{
                color: #ffffff;
                background: #090c12;
                border: 0px;
                outline: none;
            }}
            QTabWidget#macroTabs > QTabBar::tab:hover {{
                color: #ffffff;
            }}
            QTabWidget#macroTabs > QTabBar::tab:focus {{
                border: 0px;
                outline: none;
                background: #090c12;
            }}
            QWidget#macroToolbar {{
                background: #090c12;
                border: 0px;
            }}
            QLabel#macroTitle {{
                color: #ffffff;
                font-size: 15px;
                font-weight: 700;
            }}
            QLabel#demoBadge {{
                color: #b99cff;
                background: #24183c;
                border: 1px solid #49336f;
                border-radius: 4px;
                padding: 3px 7px;
                font-size: 8pt;
                font-weight: 700;
            }}
            QComboBox {{
                color: {FG};
                background: #171c25;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 6px 9px;
                min-width: 145px;
            }}
            QComboBox QAbstractItemView {{
                color: {FG};
                background: #171c25;
                selection-background-color: {DRAW};
            }}
            QLineEdit#indicatorSearch {{
                color: {FG};
                background: #111720;
                border: 1px solid {BORDER};
                border-radius: 15px;
                padding: 6px 10px;
                selection-background-color: {DRAW};
            }}
            QLineEdit#indicatorSearch:focus {{
                border-color: #6f8cff;
            }}
            QPushButton {{
                color: {FG};
                background: #171c25;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                border-color: {DRAW};
            }}
            QPushButton#metricChip {{
                color: #aeb6c3;
                background: #171a20;
                border: 1px solid #272c35;
                border-radius: 14px;
                padding: 6px 11px;
                font-size: 8.5pt;
            }}
            QPushButton#metricChip:hover {{
                color: #ffffff;
                background: #222730;
            }}
            QPushButton#metricChip:checked {{
                color: #ffffff;
                background: #263b6d;
                border-color: #6f8cff;
            }}
            QWidget#viewModeGroup {{
                background: transparent;
                border: none;
            }}
            QPushButton#viewModeLeft,
            QPushButton#viewModeRight {{
                color: #aeb6c3;
                background: #171a20;
                border: 1px solid #272c35;
                padding: 6px 14px;
                min-width: 44px;
            }}
            QPushButton#viewModeLeft {{
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none;
            }}
            QPushButton#viewModeRight {{
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }}
            QPushButton#viewModeLeft:checked,
            QPushButton#viewModeRight:checked {{
                color: #ffffff;
                background: #263b6d;
                border-color: #6f8cff;
            }}
            QComboBox#viewOptionCombo {{
                color: {FG};
                background: #171c25;
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 5px 8px;
                min-width: 128px;
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: #252c39;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                margin: -5px 0;
                background: #7796ff;
                border-radius: 6px;
            }}
            QWidget#macroDetails {{
                background: #090c12;
                border: 0px;
            }}
            QLabel#countryName {{
                color: #ffffff;
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel#countryRegion, QLabel#factName, QLabel#legendText {{
                color: {MUTED};
                font-size: 8.5pt;
            }}
            QLabel#primaryValue {{
                color: #9db4ff;
                font-size: 29px;
                font-weight: 700;
            }}
            QLabel#factValue {{
                color: #e7ebf2;
                font-size: 9pt;
                font-weight: 600;
            }}
            QLabel#sectionTitle {{
                color: {MUTED};
                font-size: 8pt;
                font-weight: 700;
            }}
            QWidget#timelinePanel {{
                background: transparent;
                border: none;
            }}
            QListWidget {{
                color: {FG};
                background: transparent;
                border: 1px solid {BORDER};
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {BORDER};
            }}
            QListWidget::item:hover {{
                background: #171e2a;
            }}
            QLabel#placeholderTitle {{
                color: #ffffff;
                font-size: 22px;
                font-weight: 700;
            }}
            QLabel#placeholderStatus {{
                color: {MUTED};
                padding-top: 8px;
            }}
            QSplitter::handle {{
                background: transparent;
                width: 0px;
            }}
        """)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setObjectName("macroTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)
        bar.setExpanding(False)
        bar.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        bar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        countries = loadCountries()
        self.tabs.addTab(MacroMapTab(countries), "World Map")
        self.tabs.addTab(MacroPlaceholder("Economic Calendar"), "Calendar")
        self.tabs.addTab(MacroPlaceholder("Global Interest Rates"), "Rates")
        self.tabs.addTab(MacroPlaceholder("Growth & Inflation"), "Growth")
        layout.addWidget(self.tabs)


__all__ = [
    "ColorScaleBar",
    "Country",
    "Macro3DTab",
    "Macro3DWidget",
    "MacroMapTab",
    "MacroView",
    "Metric",
    "WorldMapWidget",
    "YearTimeline",
    "loadCountries",
]
