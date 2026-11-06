"""Optional display controls for data inspection, kept out of the main workflow."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSlider, QSpinBox, QDoubleSpinBox
from .i18n import QLabel, QPushButton, QCheckBox, QComboBox, QFormLayout


class DisplayPanel(QWidget):
    def __init__(self, view, translate, parent=None):
        super().__init__(parent)
        self.view, self.t = view, translate
        self._updating = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setVerticalSpacing(10)
        self.part = QComboBox()
        form.addRow(self.t('原模型部件', 'Source part'), self.part)
        self.part_visible = QCheckBox(self.t('显示此部件', 'Show this part'))
        form.addRow(self.part_visible)
        self.part_opacity = QSlider(Qt.Orientation.Horizontal)
        self.part_opacity.setRange(0, 100)
        form.addRow(self.t('部件不透明度', 'Part opacity'), self.part_opacity)
        self.reset = QPushButton(self.t('恢复所有部件', 'Reset all parts'))
        form.addRow(self.reset)
        self.scalar = QComboBox()
        form.addRow(self.t('标量着色', 'Scalar coloring'), self.scalar)
        self.palette = QComboBox()
        for title, value in [(self.t('紫绿黄', 'Viridis'), 'viridis'), (self.t('蓝白红', 'Blue–red'), 'diverging'),
                             (self.t('灰度', 'Grayscale'), 'gray')]:
            self.palette.addItem(title, value)
        form.addRow(self.t('色图', 'Color map'), self.palette)
        self.auto_range = QCheckBox(self.t('自动数值范围', 'Automatic range'))
        self.auto_range.setChecked(True)
        form.addRow(self.auto_range)
        self.range_low, self.range_high = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.range_low, self.range_high):
            spin.setDecimals(8)
            spin.setRange(-1e100, 1e100)
            spin.setKeyboardTracking(False)
        form.addRow(self.t('最小值', 'Minimum'), self.range_low)
        form.addRow(self.t('最大值', 'Maximum'), self.range_high)
        self.range_note = QLabel('')
        self.range_note.setWordWrap(True)
        self.range_note.setObjectName('hint')
        form.addRow(self.range_note)
        self.point_size = QSpinBox()
        self.point_size.setRange(1, 20)
        self.point_size.setValue(4)
        form.addRow(self.t('点大小', 'Point size'), self.point_size)
        self.shading = QComboBox()
        for title, value in [(self.t('平滑光照', 'Smooth lighting'), 'smooth'), (self.t('平面光照', 'Flat lighting'), 'flat'),
                             (self.t('无光照（核对颜色）', 'Unlit (inspect colors)'), 'unlit')]:
            self.shading.addItem(title, value)
        form.addRow(self.t('表面显示', 'Shading'), self.shading)
        self.lighting = QSlider(Qt.Orientation.Horizontal)
        self.lighting.setRange(20, 200)
        self.lighting.setValue(100)
        form.addRow(self.t('光照强度', 'Light strength'), self.lighting)
        layout.addLayout(form)
        note = QLabel(self.t('部件和标量设置作用于原模型；缺失数值显示为灰色。',
                            'Parts and scalar coloring apply to the source; missing values appear gray.'))
        note.setWordWrap(True)
        note.setObjectName('hint')
        layout.addWidget(note)
        self.part.currentIndexChanged.connect(self._select_part)
        self.part_visible.toggled.connect(self._change_part)
        self.part_opacity.valueChanged.connect(self._change_part)
        self.reset.clicked.connect(self._reset_parts)
        self.scalar.currentIndexChanged.connect(self._select_scalar)
        self.palette.currentIndexChanged.connect(self._change_scalar)
        self.auto_range.toggled.connect(self._change_scalar)
        self.range_low.valueChanged.connect(self._change_scalar)
        self.range_high.valueChanged.connect(self._change_scalar)
        self.point_size.valueChanged.connect(self._appearance)
        self.shading.currentIndexChanged.connect(self._appearance)
        self.lighting.valueChanged.connect(self._appearance)
        self.refresh()

    def refresh(self):
        self._updating = True
        self.part.clear()
        for index, part in enumerate(self.view.parts):
            self.part.addItem(part.name, index)
        self.scalar.clear()
        self.scalar.addItem(self.t('关闭', 'Off'), None)
        for domain, name in self.view.available_scalars():
            self.scalar.addItem(self.t(f'{"顶点" if domain == "point" else "面"} · {name}',
                                      f'{"Vertex" if domain == "point" else "Face"} · {name}'), domain + ':' + name)
        selected = ':'.join(self.view.scalar_key) if self.view.scalar_key else None
        self.scalar.setCurrentIndex(max(0, self.scalar.findData(selected)))
        self.auto_range.setChecked(True)
        self.point_size.setEnabled(any(p.point_cloud for p in self.view.parts))
        self._updating = False
        self._select_part()
        self._select_scalar()

    def _select_part(self, *_):
        if self._updating:
            return
        self._updating = True
        index = self.part.currentIndex()
        valid = 0 <= index < len(self.view.parts)
        self.part_visible.setEnabled(valid)
        self.part_opacity.setEnabled(valid)
        if valid:
            part = self.view.parts[index]
            self.part_visible.setChecked(part.visible)
            self.part_opacity.setValue(round(part.opacity * 100))
        self._updating = False

    def _change_part(self, *_):
        if not self._updating and self.part.currentIndex() >= 0:
            self.view.set_part(self.part.currentIndex(), visible=self.part_visible.isChecked(),
                               opacity=self.part_opacity.value() / 100)

    def _reset_parts(self):
        self.view.reset_parts()
        self._select_part()

    def _select_scalar(self, *_):
        if self._updating:
            return
        self._updating = True
        key = self._scalar_key()
        span = self.view.scalar_range(key) if key else None
        self.auto_range.setChecked(True)
        if span:
            self.range_low.setValue(span[0])
            self.range_high.setValue(span[1] if span[1] > span[0] else span[0] + 1)
        self._updating = False
        self._change_scalar()

    def _change_scalar(self, *_):
        if self._updating:
            return
        key = self._scalar_key()
        for widget in (self.palette, self.auto_range):
            widget.setEnabled(key is not None)
        custom = key is not None and not self.auto_range.isChecked()
        self.range_low.setEnabled(custom)
        self.range_high.setEnabled(custom)
        span = self.view.scalar_range(key) if key else None
        if not custom and span:
            low, high = span
            if low == high:
                padding = max(abs(low) * .01, .5)
                low, high = low - padding, high + padding
            self._updating = True
            self.range_low.setValue(low)
            self.range_high.setValue(high)
            self._updating = False
        limits = (self.range_low.value(), self.range_high.value()) if custom else None
        if limits and limits[0] >= limits[1]:
            self.range_note.setText(self.t('最小值必须小于最大值；仍使用上一次有效范围。',
                                          'Minimum must be below maximum; keeping the last valid range.'))
            return
        self.view.set_scalar(key, palette=self.palette.currentData(), limits=limits)
        self.range_note.setText(self.t(f'数据范围：{span[0]:.6g} ～ {span[1]:.6g}',
                                      f'Data range: {span[0]:.6g} to {span[1]:.6g}') if span else '')

    def _appearance(self, *_):
        self.view.point_size = self.point_size.value()
        self.view.shading = self.shading.currentData()
        self.view.light_strength = self.lighting.value() / 100
        self.view.apply_appearance()

    def _scalar_key(self):
        value = self.scalar.currentData()
        return tuple(value.split(':', 1)) if value else None
