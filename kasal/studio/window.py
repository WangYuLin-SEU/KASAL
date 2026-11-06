"""KASAL Studio's independent, light desktop workbench."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import html
import hashlib
from PySide6.QtCore import Qt, QSize, QSettings, QTimer, QUrl, QPoint
from PySide6.QtGui import QDesktopServices, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSplitter, QListWidget, QListWidgetItem, QScrollArea,
    QSpinBox, QSlider, QProgressBar, QMessageBox, QDialogButtonBox, QPlainTextEdit,
)
from .model import ModelRecord, ResultStore, TYPES, discover
from .controller import JobRunner
from .viewport import MeshViewport
from .theme import STYLE, icon
from .display import DisplayPanel
from .i18n import Localizer, QLabel, QPushButton, QCheckBox, QLineEdit, QComboBox, QMenu, QFormLayout, QDialog, QFileDialog


def label(text='', name='', wrap=False):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text='', symbol=None, callback=None, name='', tooltip=''):
    widget = QPushButton(text)
    widget.setObjectName(name)
    if symbol:
        widget.setIcon(icon(symbol, '#ffffff' if name == 'primary' else '#657995'))
        widget.setIconSize(QSize(18, 18))
    if callback:
        widget.clicked.connect(callback)
    widget.setToolTip(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def frame(name, margin=18, spacing=12, horizontal=False):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QHBoxLayout(widget) if horizontal else QVBoxLayout(widget)
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(spacing)
    return widget, layout


class StudioWindow(QMainWindow):
    def __init__(self, initial: Path | None = None, *, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings('KASAL', 'StudioPreview')
        self.localizer = Localizer(str(self.settings.value('language', 'zh')))
        self.language = self.localizer.language
        self.policy = str(self.settings.value('policy', 'kasalv2_adaptive'))
        if self.policy not in ('kasalv2_adaptive', 'kasalv2_strict', 'kasalv1'):
            self.policy = 'kasalv2_adaptive'
        self.records = []
        self.current = None
        self.store = None
        self.root = None
        self._library_key = ''
        self.logs = []
        self._loading = False
        self._mesh_loaded = False
        self._axis_count = 0
        self._view_errors = []
        self._closing_after_cancel = False
        self.runner = JobRunner(self)
        self.runner.changed.connect(self._job_changed)
        self.runner.progress.connect(self._progress)
        self.runner.completed.connect(self._completed)
        self.setWindowTitle('KASAL Studio · Preview')
        self.setWindowIcon(icon('cube', '#326bd6', 32))
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)
        self.setAcceptDrops(True)
        self._build()
        self._shortcuts()
        if initial is None:
            recent = str(self.settings.value('last_path', ''))
            initial = Path(recent) if recent and Path(recent).exists() else Path(__file__).parents[1] / 'datasets/shape_meshes'
        QTimer.singleShot(0, lambda: self.open_path(initial))

    def t(self, zh, en):
        return self.localizer.text(zh, en)

    def set_language(self, language, *, persist=True):
        self.language = 'en' if language == 'en' else 'zh'
        self.localizer.set_language(self.language)
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        self.language_combo.blockSignals(False)
        # Update composed model/result text without loading meshes or touching the camera.
        self._populate(preserve_selection=True)
        self._sync_panel(update_view=False)
        if persist:
            self.settings.setValue('language', self.language)
            self.settings.sync()

    def _build(self):
        base = QWidget()
        outer = QVBoxLayout(base)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header, row = frame('header', 20, 12, True)
        header.setFixedHeight(78)
        mark = QLabel()
        mark.setPixmap(icon('cube', '#326bd6', 32).pixmap(32, 32))
        row.addWidget(mark)
        row.addWidget(label('KASAL', 'brand'))
        row.addWidget(label('STUDIO', 'eyebrow'))
        row.addSpacing(6)
        row.addWidget(label(self.t('预览版', 'PREVIEW'), 'badge'))
        row.addSpacing(25)
        self.breadcrumb = label(self.t('三维旋转对称分析', '3D rotational symmetry analysis'), 'muted')
        row.addWidget(self.breadcrumb, 1)
        self.open_button = button(self.t('打开模型库', 'Open library'), 'folder', self.choose_folder, tooltip='Ctrl+O')
        row.addWidget(self.open_button)
        self.language_combo = QComboBox()
        self.language_combo.addItem('中文', 'zh')
        self.language_combo.addItem('English', 'en')
        self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
        self.language_combo.setToolTip(self.t('界面语言 · 即时切换', 'Language · applies immediately'))
        self.language_combo.currentIndexChanged.connect(lambda: self.set_language(self.language_combo.currentData()))
        row.addWidget(self.language_combo)
        row.addWidget(button('', 'settings', self.show_settings, 'subtle', self.t('设置', 'Settings')))
        row.addWidget(button('', 'help', self.show_help, 'subtle', self.t('操作帮助', 'Navigation help')))
        outer.addWidget(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(1)
        sidebar, left = frame('sidebar', 16, 12)
        sidebar.setMinimumWidth(225)
        sidebar.setMaximumWidth(370)
        heading = QHBoxLayout()
        heading.addWidget(label(self.t('模型库', 'LIBRARY'), 'section'))
        heading.addStretch()
        self.count_label = label('0', 'badge')
        heading.addWidget(self.count_label)
        menu_button = button('', 'more', name='subtle', tooltip=self.t('模型库操作', 'Library actions'))
        menu = QMenu(menu_button)
        menu.addAction(self.t('打开模型文件…', 'Open a mesh file…'), self.choose_file)
        menu.addSeparator()
        menu.addAction(self.t('全部标为待处理', 'Mark all pending'), self.mark_all)
        menu.addAction(self.t('恢复已保存结果', 'Reload saved results'), self.restore_all)
        menu.addSeparator()
        menu.addAction(self.t('打开 Studio 结果目录', 'Open Studio results'), self.open_results)
        menu.addAction(self.t('清除 Studio 结果…', 'Clear Studio results…'), self.clear_results)
        menu_button.setMenu(menu)
        heading.addWidget(menu_button)
        left.addLayout(heading)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.t('搜索模型名称…', 'Search models…'))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._populate)
        left.addWidget(self.search)
        self.filter = QComboBox()
        for text, data in [(self.t('全部模型', 'All models'), 'all'), (self.t('待处理', 'Pending'), 'pending'),
                           (self.t('已有结果', 'With results'), 'saved'), (self.t('需要检查', 'Needs attention'), 'error')]:
            self.filter.addItem(text, data)
        self.filter.currentIndexChanged.connect(self._populate)
        left.addWidget(self.filter)
        self.list = QListWidget()
        self.list.setIconSize(QSize(22, 22))
        self.list.currentItemChanged.connect(self._selected)
        left.addWidget(self.list, 1)
        self.library_stats = label('', 'muted', True)
        left.addWidget(self.library_stats)
        left.addWidget(button(self.t('打开单个模型', 'Open a mesh'), 'cube', self.choose_file, 'subtle'))
        left.addWidget(label(self.t('也可拖放文件夹或模型到窗口', 'Drop a folder or mesh onto this window'), 'hint', True))
        split.addWidget(sidebar)

        middle, center = frame('center', 0, 0)
        middle.setMinimumWidth(420)
        titlebar, title_row = frame('viewportHeader', 18, 10, True)
        titlebar.setFixedHeight(70)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.mesh_title = label(self.t('选择一个模型', 'Choose a model'), 'title')
        self.mesh_meta = label('', 'muted')
        titles.addWidget(self.mesh_title)
        titles.addWidget(self.mesh_meta)
        title_row.addLayout(titles, 1)
        title_row.addWidget(button('', 'left', lambda: self.navigate(-1), 'subtle', 'PageUp'))
        title_row.addWidget(button('', 'right', lambda: self.navigate(1), 'subtle', 'PageDown'))
        center.addWidget(titlebar)
        tools, tool_row = frame('viewTools', 10, 7, True)
        tools.setFixedHeight(52)
        tool_row.addWidget(button(self.t('适应', 'Fit'), 'fit', lambda: self.view.fit(), tooltip='F'))
        self.view_combo = QComboBox()
        for text, value in [(self.t('等轴视图', 'Isometric'), 'iso'), (self.t('正面', 'Front'), 'front'),
                            (self.t('右侧', 'Right'), 'right'), (self.t('顶部', 'Top'), 'top')]:
            self.view_combo.addItem(text, value)
        self.view_combo.addItem(self.t('自由视角', 'Free view'), 'custom')
        self.view_combo.model().item(self.view_combo.count() - 1).setEnabled(False)
        self.view_combo.activated.connect(lambda: self.view.set_view(self.view_combo.currentData()))
        tool_row.addWidget(self.view_combo)
        self.ortho = button(self.t('正交', 'Ortho'), tooltip=self.t('切换正交 / 透视 · 5', 'Orthographic / perspective · 5'))
        self.ortho.setCheckable(True)
        self.ortho.toggled.connect(lambda enabled: self.view.set_orthographic(enabled))
        tool_row.addWidget(self.ortho)
        self.render_mode = QComboBox()
        for text, value in [(self.t('实体', 'Solid'), 'solid'), (self.t('边线', 'Edges'), 'edges'), (self.t('线框', 'Wireframe'), 'wireframe')]:
            self.render_mode.addItem(text, value)
        self.render_mode.currentIndexChanged.connect(self._appearance)
        tool_row.addWidget(self.render_mode)
        tool_row.addStretch()
        tool_row.addWidget(button('', 'settings', self.open_display_controls, 'subtle', self.t('图层、标量与光照', 'Parts, scalars & lighting')))
        tool_row.addWidget(button('', 'camera', self.save_screenshot, 'subtle', self.t('保存视口截图', 'Save viewport screenshot')))
        center.addWidget(tools)
        self.view = MeshViewport()
        self.view.cameraChanged.connect(self._sync_camera)
        self.view.presetChanged.connect(self._sync_preset)
        center.addWidget(self.view, 1)
        hint, hint_row = frame('viewTools', 10, 5, True)
        hint.setFixedHeight(36)
        hint_row.addWidget(label(self.t('左键 旋转  ·  Shift＋左键 平移  ·  滚轮 缩放  ·  双击 聚焦',
                                       'Drag to orbit  ·  Shift+drag to pan  ·  Scroll to zoom  ·  Double-click to focus'), 'hint'))
        hint_row.addStretch()
        center.addWidget(hint)
        split.addWidget(middle)

        inspector, right = frame('inspector', 0, 0)
        inspector.setMinimumWidth(300)
        inspector.setMaximumWidth(400)
        scroll = QScrollArea()
        self.inspector_scroll = scroll
        scroll.setWidgetResizable(True)
        content, panel = frame('inspector', 20, 13)
        panel.addWidget(label(self.t('分析工作台', 'ANALYSIS'), 'eyebrow'))
        panel.addWidget(label(self.t('旋转对称性', 'Rotational symmetry'), 'title'))
        self.state_label = label(self.t('等待模型', 'Waiting for a model'), 'badge')
        panel.addWidget(self.state_label)
        panel.addSpacing(5)
        panel.addWidget(label(self.t('分析方式', 'Workflow'), 'section'))
        self.mode = QComboBox()
        self.mode.addItem(self.t('自动识别类型与对称轴', 'Automatic classification'), 'kasalv2')
        self.mode.addItem(self.t('人工标注 / 已知类型', 'Manual label / known type'), 'kasalv1')
        panel.addWidget(self.mode)
        self.mode_hint = label('', 'hint', True)
        panel.addWidget(self.mode_hint)
        self.manual_fields = QWidget()
        form = QFormLayout(self.manual_fields)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(10)
        self.sym_type = QComboBox()
        for canonical, zh, en in TYPES:
            self.sym_type.addItem(self.t(zh, en), canonical)
        form.addRow(self.t('对称类型', 'Type'), self.sym_type)
        self.fold = QSpinBox()
        self.fold.setRange(2, 90)
        form.addRow(self.t('旋转阶数', 'Order'), self.fold)
        self.axis = QComboBox()
        for text, value in [(self.t('不约束', 'Unconstrained'), 'None'), ('X', 'axis X'), ('Y', 'axis Y'), ('Z', 'axis Z')]:
            self.axis.addItem(text, value)
        form.addRow(self.t('轴向约束', 'Axis constraint'), self.axis)
        panel.addWidget(self.manual_fields)
        self.texture = QCheckBox(self.t('同时分析纹理 / 颜色', 'Include texture / color'))
        self.texture.setToolTip(self.t('在几何分析结果之外，计算纹理对称性（ADI-C）', 'Evaluate appearance symmetry in addition to geometry (ADI-C)'))
        panel.addWidget(self.texture)
        self.device = QComboBox()
        self._devices()
        panel.addWidget(label(self.t('计算设备', 'Compute device'), 'section'))
        panel.addWidget(self.device)
        self.analyze_button = button(self.t('分析当前模型', 'Analyze model'), 'play', self.analyze_current, 'primary', 'Ctrl+Enter')
        panel.addWidget(self.analyze_button)
        self.save_label_button = button(self.t('保存人工标注（不计算）', 'Save label without analysis'),
                                        'export', self.save_manual_label, tooltip='Ctrl+S')
        panel.addWidget(self.save_label_button)
        self.batch_button = button(self.t('批量分析待处理模型', 'Analyze pending models'), 'batch', self.analyze_batch)
        self.batch_mode = QComboBox()
        self.batch_mode.addItem(self.t('批处理：沿用各模型设置', 'Batch: use each model’s settings'), 'per_model')
        self.batch_mode.addItem(self.t('批处理：全部自动识别（v2）', 'Batch: automatic (v2)'), 'kasalv2')
        self.batch_mode.addItem(self.t('批处理：全部已知类型（v1）', 'Batch: known type (v1)'), 'kasalv1')
        self.batch_mode.setToolTip(self.t('仅处理待处理模型；无效参数记为失败并继续下一项。', 'Only pending models; invalid parameters are reported and the batch continues.'))
        self.batch_mode.setCurrentIndex(max(0, self.batch_mode.findData(self.settings.value('batch_mode', 'per_model'))))
        panel.addWidget(self.batch_mode)
        panel.addWidget(self.batch_button)
        self.draft_label = label('', 'hint', True)
        panel.addWidget(self.draft_label)
        self.error_label = label('', 'error', True)
        self.error_label.hide()
        panel.addWidget(self.error_label)
        panel.addSpacing(8)
        panel.addWidget(label(self.t('分析结果', 'RESULT'), 'eyebrow'))
        self.result_title = label(self.t('尚无分析结果', 'No result yet'), 'section', True)
        panel.addWidget(self.result_title)
        self.result_meta = label(self.t('运行分析后，对称轴将显示在视图中。', 'Run an analysis to see the symmetry axes.'), 'muted', True)
        panel.addWidget(self.result_meta)
        result_actions = QHBoxLayout()
        self.export_button = button(self.t('导出结果', 'Export'), 'export', self.export_result)
        self.export_button.setToolTip(self.t('导出已保存的标注或计算结果；修改参数后请先保存或分析。',
                                           'Export saved labels or results; save or analyze parameter changes first.'))
        result_actions.addWidget(self.export_button)
        self.restore_button = button(self.t('恢复', 'Reload'), 'refresh', self.restore_current, tooltip=self.t('舍弃参数草稿并恢复已保存结果', 'Discard the parameter draft and reload saved results'))
        result_actions.addWidget(self.restore_button)
        panel.addLayout(result_actions)
        panel.addSpacing(8)
        panel.addWidget(label(self.t('视图显示', 'DISPLAY'), 'eyebrow'))
        self.display_source = QComboBox()
        self.display_source.addItem(self.t('原模型与对称轴', 'Source mesh and axes'), 'source')
        self.display_source.addItem(self.t('对称结果着色（PLY）', 'Symmetry visualization (PLY)'), 'result')
        self.display_source.setToolTip(self.t('结果 PLY 包含算法生成的着色和箭头；可与原模型切换对照。', 'The result PLY includes computed colors and arrows; switch to compare with the source.'))
        self.display_source.currentIndexChanged.connect(lambda: self.view.set_result_visible(self.display_source.currentData() == 'result'))
        panel.addWidget(self.display_source)
        checks = QGridLayout()
        self.show_axes = QCheckBox(self.t('对称轴', 'Symmetry axes'))
        self.show_axes.setChecked(True)
        self.show_axes.toggled.connect(self.view.set_symmetry_visible)
        self.show_grid = QCheckBox(self.t('参考网格', 'Grid'))
        self.show_grid.setChecked(True)
        self.show_grid.toggled.connect(self.view.set_grid_visible)
        self.show_colors = QCheckBox(self.t('纹理 / 颜色', 'Colors'))
        self.show_colors.setChecked(False)
        self.view.colors = False
        self.show_coordinates = QCheckBox(self.t('坐标轴', 'Coordinates'))
        self.show_colors.toggled.connect(self._appearance)
        self.show_coordinates.toggled.connect(self.view.set_coordinates_visible)
        checks.addWidget(self.show_axes, 0, 0)
        checks.addWidget(self.show_grid, 0, 1)
        checks.addWidget(self.show_colors, 1, 0)
        checks.addWidget(self.show_coordinates, 1, 1)
        panel.addLayout(checks)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(label(self.t('不透明度', 'Opacity'), 'muted'))
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(10, 100)
        self.opacity.setValue(100)
        self.opacity.valueChanged.connect(self._appearance)
        opacity_row.addWidget(self.opacity, 1)
        panel.addLayout(opacity_row)
        self.display_details = button(self.t('图层、标量与光照', 'Parts, scalars and lighting'), name='subtle')
        self.display_details.setCheckable(True)
        panel.addWidget(self.display_details)
        self.display_panel = DisplayPanel(self.view, self.t)
        self.display_panel.hide()
        self.display_details.toggled.connect(self.display_panel.setVisible)
        panel.addWidget(self.display_panel)
        panel.addStretch()
        panel.addSpacing(10)
        panel.addWidget(label(self.t('结果独立保存到 Studio 工作区', 'Results saved in the separate Studio workspace'), 'hint', True))
        scroll.setWidget(content)
        right.addWidget(scroll)
        split.addWidget(inspector)
        split.setSizes([250, 850, 330])
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)

        footer, bottom = frame('footer', 16, 8)
        footer.setFixedHeight(92)
        status_row = QHBoxLayout()
        self.status_label = label(self.t('就绪', 'Ready'), 'section')
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.counter_label = label('', 'muted')
        status_row.addWidget(self.counter_label)
        self.cancel_button = button(self.t('取消任务', 'Cancel'), 'stop', self.cancel_jobs)
        self.cancel_button.hide()
        status_row.addWidget(self.cancel_button)
        status_row.addWidget(button(self.t('任务记录', 'Activity'), callback=self.show_activity, name='subtle'))
        bottom.addLayout(status_row)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        bottom.addWidget(self.progress_bar)
        outer.addWidget(footer)
        self.setCentralWidget(base)
        for widget in (self.mode, self.sym_type, self.axis):
            widget.currentIndexChanged.connect(self._parameters_changed)
        self.fold.valueChanged.connect(self._parameters_changed)
        self.texture.toggled.connect(self._parameters_changed)
        self.device.currentIndexChanged.connect(self._save_preferences)
        self.batch_mode.currentIndexChanged.connect(self._save_preferences)
        self._enable_controls()

    def _save_preferences(self, *_):
        for key, value in [('device', self.device.currentData()), ('policy', self.policy),
                           ('batch_mode', self.batch_mode.currentData())]:
            self.settings.setValue(key, value)
            if self._library_key:
                self.settings.setValue(self._library_key + '/' + key, value)

    def _devices(self):
        import torch
        self.device.addItem('CPU', 'cpu')
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i).replace('NVIDIA GeForce ', '')
                self.device.addItem(f'{name} · CUDA', f'cuda:{i}')
        preferred = self.settings.value('device', 'cuda:0' if self.device.count() > 1 else 'cpu')
        self.device.setCurrentIndex(max(0, self.device.findData(preferred)))

    def _shortcuts(self):
        for key, callback in [('Ctrl+O', self.choose_folder), ('Ctrl+Shift+O', self.choose_file),
                              ('Ctrl+Return', self.analyze_current), ('Ctrl+S', self.save_manual_label), ('PageUp', lambda: self.navigate(-1)),
                              ('PageDown', lambda: self.navigate(1)), ('F1', self.show_help)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)

    def _status_name(self, record):
        if record.status in ('saved', 'legacy') and record.result_kind == 'manual_annotation':
            return self.t('已人工标注', 'Manually labeled')
        return {'pending': self.t('待处理', 'Pending'), 'running': self.t('分析中', 'Analyzing'),
                'saved': self.t('已完成', 'Complete'), 'legacy': self.t('旧版结果', 'Imported result'),
                'error': self.t('需要检查', 'Needs attention')}[record.status]

    def _populate(self, *_, preserve_selection=False):
        selected = self.current
        scroll_position = self.list.verticalScrollBar().value()
        self.list.blockSignals(True)
        self.list.clear()
        query, filter_value = self.search.text().casefold(), self.filter.currentData()
        selection = None
        for index, record in enumerate(self.records):
            if query not in record.relative.casefold():
                continue
            if filter_value == 'saved' and record.status not in ('saved', 'legacy'):
                continue
            if filter_value not in ('all', 'saved') and record.status != filter_value:
                continue
            item = QListWidgetItem(f'{record.path.stem}\n{record.path.suffix[1:].upper()}  ·  {self._status_name(record)}')
            item.setIcon(icon('cube', '#3b78d3' if record is selected else '#8a9bb1', 22))
            item.setToolTip(record.relative)
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setSizeHint(QSize(200, 66))
            self.list.addItem(item)
            if record is selected:
                selection = item
        if selection:
            self.list.setCurrentItem(selection)
        elif self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.count_label.setText(str(len(self.records)))
        saved = sum(not r.dirty and not r.error for r in self.records)
        self.library_stats.setText(self.t(f'{saved} 个已有结果  /  共 {len(self.records)} 个模型', f'{saved} with results  /  {len(self.records)} models'))
        self.batch_button.setText(self.t(f'批量分析待处理 · {len(self._batch_records())}',
                                         f'Analyze pending · {len(self._batch_records())}'))
        if preserve_selection:
            self.list.verticalScrollBar().setValue(scroll_position)
        if selection is None and self.list.currentItem() is not None:
            self._selected(self.list.currentItem(), None)
        elif not self.list.count():
            self._clear_selection()

    def _clear_selection(self):
        self.current = None
        self._mesh_loaded = False
        self._axis_count = 0
        self._view_errors = []
        self.view.clear()
        self.display_panel.refresh()
        self.display_source.setCurrentIndex(0)
        self.display_source.model().item(1).setEnabled(False)
        self.mesh_title.setText(self.t('没有匹配的模型', 'No matching models'))
        self.mesh_title.setToolTip('')
        self.mesh_meta.setText('')
        self.state_label.setText(self.t('等待模型', 'Waiting for a model'))
        self.result_title.setText(self.t('尚无分析结果', 'No result yet'))
        self.result_meta.setText(self.t('修改搜索或筛选条件以选择模型。', 'Change the search or filter to select a model.'))
        self.error_label.hide()
        self.draft_label.setText('')
        self._enable_controls()

    def _selected(self, item, previous=None):
        if item is None:
            return
        record = self.records[item.data(Qt.ItemDataRole.UserRole)]
        if record is self.current:
            return
        self.current = record
        self._view_errors = []
        if self._library_key:
            self.settings.setValue(self._library_key + '/model', record.relative)
        self.mesh_title.setText(record.path.stem)
        self.mesh_title.setToolTip(record.relative)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            stats = self.view.load_mesh(record.path)
            self._mesh_loaded = True
            if record.error_kind == 'geometry':
                record.error = record.error_kind = ''
            record.has_surface = not stats['point_cloud']
            if stats['point_cloud'] and record.source == 'new' and not record.edited:
                record.state.compute_engine = 'kasalv1'
            self.show_colors.setChecked(stats['textured'] or stats['point_cloud'])
            self.mesh_meta.setText(self.t(f'{stats["vertices"]:,} 点  ·  点云（可查看、标注）',
                                         f'{stats["vertices"]:,} points  ·  Point cloud (view and label)') if stats['point_cloud'] else
                                   self.t(f'{stats["vertices"]:,} 顶点  ·  {stats["faces"]:,} 三角面  ·  {record.path.suffix[1:].upper()}',
                                         f'{stats["vertices"]:,} vertices  ·  {stats["faces"]:,} triangles  ·  {record.path.suffix[1:].upper()}'))
        except Exception as exc:
            self._mesh_loaded = False
            self.view.clear()
            record.error = str(exc)
            record.error_kind = 'geometry'
            self.mesh_meta.setText(self.t('模型加载失败', 'Mesh could not be loaded'))
            self._log(f'{record.path.name}: {exc}')
        finally:
            QApplication.restoreOverrideCursor()
        self.display_panel.refresh()
        self._sync_panel()

    def _sync_panel(self, *, update_view=True):
        record = self.current
        if record is None:
            return
        self._loading = True
        state = record.state
        self.mode.setCurrentIndex(max(0, self.mode.findData(state.compute_engine)))
        self.sym_type.setCurrentIndex(max(0, self.sym_type.findData(state.sym_type)))
        self.fold.setValue(state.n_fold)
        self.axis.setCurrentIndex(max(0, self.axis.findData(state.axis_xyz)))
        self.texture.setChecked(state.adi_c)
        self._loading = False
        self.state_label.setText(self._status_name(record))
        self.draft_label.setText(self.t('参数草稿已自动保存，等待分析。', 'Parameter draft saved; awaiting analysis.') if record.edited and record.draft_saved else
                                 self.t('参数草稿尚未保存。', 'Parameter draft has not been saved.') if record.edited else '')
        baseline = record.baseline
        info = baseline.current_obj_info if baseline else {}
        if update_view:
            self._view_errors = []
            try:
                self._axis_count = self.view.set_result(info if self._mesh_loaded else {})
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                self._axis_count = self.view.set_result({})
                self._view_errors.append((f'轴系数据无法显示：{exc}', f'Could not display axes: {exc}'))
            try:
                available = self.view.set_visualization(self.store.visualization_path(record.path) if self._mesh_loaded else None)
                self.display_source.model().item(1).setEnabled(available)
                if not available:
                    self.display_source.setCurrentIndex(0)
            except Exception as exc:
                self.view.set_visualization(None)
                self.display_source.setCurrentIndex(0)
                self.display_source.model().item(1).setEnabled(False)
                self._view_errors.append((f'结果 PLY 无法显示：{exc}', f'Could not display result PLY: {exc}'))
        axis_count = self._axis_count
        if baseline:
            canonical = baseline.sym_type
            result_name = next((self.t(zh, en) for value, zh, en in TYPES if value == canonical), canonical)
            self.result_title.setText(result_name)
            fold = info.get('n_fold', baseline.n_fold)
            fold_text = ('—' if canonical == 'None' else
                         '∞' if str(fold) == 'inf' or canonical.startswith('C(') else str(fold))
            elapsed = f'  ·  {record.elapsed:.1f}s' if record.elapsed is not None else ''
            suffix = self.t('\n参数已修改；视图仍显示上次结果。', '\nParameters changed; showing the previous result.') if record.edited else ''
            axes_text = (self.t('任意轴向', 'Any axis direction') if canonical == 'C(>>1): Spherical Item' else
                         self.t(f'{axis_count} 条轴', f'{axis_count} axes'))
            self.result_meta.setText(self.t(f'阶数 {fold_text}  ·  {axes_text}  ·  {baseline.compute_engine}{elapsed}',
                                            f'Order {fold_text}  ·  {axes_text}  ·  {baseline.compute_engine}{elapsed}') + suffix)
            texture_info = info.get('texture_symmetry')
            if texture_info is not None and not isinstance(texture_info, dict):
                if update_view:
                    self._view_errors.append(('纹理结果格式无效。', 'Invalid texture result format.'))
                texture_info = None
            if texture_info:
                texture_type = texture_info.get('rot_sym_type')
                texture_name = next((self.t(zh, en) for value, zh, en in TYPES if value == texture_type), texture_type)
                if not texture_info.get('evaluated', True):
                    detail = self.t('纹理：未评估', 'Texture: not evaluated')
                elif not texture_info.get('has_rot_sym'):
                    detail = self.t('纹理：无旋转对称', 'Texture: no rotational symmetry')
                else:
                    order = texture_info.get('n_fold', '—')
                    detail = self.t(f'纹理：{texture_name} · 阶数 {order}', f'Texture: {texture_name} · order {order}')
                self.result_meta.setText(self.result_meta.text() + '\n' + detail)
        else:
            self.result_title.setText(self.t('尚无分析结果', 'No result yet'))
            self.result_meta.setText(self.t('运行分析后，对称轴将显示在视图中。', 'Run an analysis to see the symmetry axes.'))
        if baseline and record.result_kind == 'manual_annotation':
            self.result_meta.setText(self.t('人工标注已保存，可直接导出；尚未计算轴系。',
                                           'Manual annotation saved and ready to export; axes have not been computed.'))
            if record.edited:
                self.result_meta.setText(self.t('参数已修改；保存标注后才能导出新版本。',
                                               'Parameters changed; save the label to export the new version.'))
        errors = ([record.error[:500]] if record.error else []) + [self.t(zh, en) for zh, en in self._view_errors]
        self.error_label.setText('\n'.join(errors))
        self.error_label.setVisible(bool(errors))
        self._enable_controls()

    def _enable_controls(self):
        busy, exists = self.runner.busy, self.current is not None
        manual = self.mode.currentData() == 'kasalv1'
        self.manual_fields.setVisible(manual)
        self.mode_hint.setText(self.t('可直接保存标注，或计算指定类型的轴系。', 'Save a label directly, or locate axes for the specified type.') if manual
                               else self.t('从模型几何中自动推断类型、阶数与轴系。', 'Infer type, order and axes from the mesh geometry.'))
        if exists and self.current.has_surface is False:
            self.mode_hint.setText(self.t('点云支持查看和人工标注；对称计算需要三角网格。',
                                         'Point clouds support viewing and manual labels; analysis requires a triangle mesh.'))
        for widget in (self.mode, self.texture, self.device, self.batch_mode):
            widget.setEnabled(exists and not busy)
        for widget in (self.sym_type, self.axis):
            widget.setEnabled(exists and manual and not busy)
        self.fold.setEnabled(exists and manual and not busy and str(self.sym_type.currentData()).startswith('D('))
        self.analyze_button.setEnabled(exists and not busy and self.current.has_surface is not False and
                                       not (manual and self.sym_type.currentData() == 'None'))
        self.save_label_button.setVisible(manual)
        self.save_label_button.setEnabled(exists and manual and self._mesh_loaded and not busy)
        self.batch_button.setEnabled(not busy and bool(self._batch_records()))
        self.export_button.setEnabled(exists and self.current.source == 'studio' and not self.current.edited and not busy)
        self.restore_button.setEnabled(exists and not busy)
        self.open_button.setEnabled(not busy)
        self.cancel_button.setVisible(busy)

    def _parameters_changed(self, *_):
        if self._loading or self.current is None or self.runner.busy:
            return
        state = self.current.state
        state.compute_engine = self.mode.currentData()
        state.sym_type = self.sym_type.currentData()
        state.n_fold = self.fold.value()
        if state.compute_engine == 'kasalv1':
            state.n_fold = {'P(4): Tetrahedral Item': 3, 'P(8): Octahedral Item': 4,
                            'P(20): Icosahedral Item': 5}.get(state.sym_type, state.n_fold)
        state.axis_xyz = self.axis.currentData()
        state.adi_c = self.texture.isChecked()
        self.current.dirty = self.current.edited = True
        if self.current.error_kind in ('parameters', 'analysis'):
            self.current.error = self.current.error_kind = ''
        self.current.draft_saved = False
        try:
            self.store.save_draft(self.current)
        except (OSError, ValueError) as exc:
            self._error(self.t(f'参数草稿保存失败：{exc}', f'Could not save parameter draft: {exc}'))
        self._sync_panel()
        self._populate()

    def _appearance(self, *_):
        if not hasattr(self, 'show_colors'):
            return
        self.view.colors = self.show_colors.isChecked()
        self.view.edges = self.render_mode.currentData() == 'edges'
        self.view.wireframe = self.render_mode.currentData() == 'wireframe'
        self.view.opacity = self.opacity.value() / 100
        self.view.apply_appearance()

    def open_display_controls(self):
        self.display_details.setChecked(True)
        QTimer.singleShot(0, lambda: self.inspector_scroll.ensureWidgetVisible(self.display_panel))

    def _sync_camera(self):
        self.ortho.blockSignals(True)
        self.ortho.setChecked(bool(self.view.renderer.GetActiveCamera().GetParallelProjection()))
        self.ortho.blockSignals(False)

    def _sync_preset(self, name):
        self.view_combo.blockSignals(True)
        self.view_combo.setCurrentIndex(self.view_combo.findData(name))
        self.view_combo.blockSignals(False)

    def _discard_edits(self):
        if not any(record.edited and not record.draft_saved for record in self.records):
            return True
        return QMessageBox.question(self, self.t('未计算的参数', 'Unapplied parameters'),
            self.t('部分参数草稿未能保存。放弃这些修改并继续？', 'Some parameter drafts could not be saved. Discard them and continue?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def choose_folder(self):
        if self.runner.busy:
            return
        path = QFileDialog.getExistingDirectory(self, self.t('打开模型库', 'Open library'), str(self.root or ''))
        if path:
            self.open_path(Path(path))

    def choose_file(self):
        if self.runner.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, self.t('打开模型', 'Open mesh'), str(self.root or ''), '3D meshes (*.ply *.obj *.stl *.off *.glb *.gltf)')
        if path:
            self.open_path(Path(path))

    def open_path(self, path):
        if self.runner.busy or not self._discard_edits():
            return
        try:
            root, records = discover(Path(path))
        except Exception as exc:
            self._error(str(exc))
            return
        self.root, self.records, self.current = root, records, None
        self.store = ResultStore(root)
        self._library_key = 'libraries/' + hashlib.sha256(str(root).casefold().encode('utf-8')).hexdigest()[:24]
        remembered = self.settings.value(self._library_key + '/model', '')
        policy = self.settings.value(self._library_key + '/policy', self.settings.value('policy', 'kasalv2_adaptive'))
        if policy in ('kasalv1', 'kasalv2_adaptive', 'kasalv2_strict'):
            self.policy = policy
        for widget, key in [(self.device, 'device'), (self.batch_mode, 'batch_mode')]:
            widget.blockSignals(True)
            value = self.settings.value(self._library_key + '/' + key, self.settings.value(key, widget.currentData()))
            widget.setCurrentIndex(max(0, widget.findData(value)))
            widget.blockSignals(False)
        self.search.blockSignals(True)
        self.filter.blockSignals(True)
        self.search.clear()
        self.filter.setCurrentIndex(0)
        self.search.blockSignals(False)
        self.filter.blockSignals(False)
        self.breadcrumb.setText(root.name)
        self.breadcrumb.setToolTip(str(root))
        self.settings.setValue('last_path', str(path))
        self.status_label.setText(self.t('就绪', 'Ready'))
        self.progress_bar.setValue(0)
        self._populate()
        for row in range(self.list.count()):
            item = self.list.item(row)
            if self.records[item.data(Qt.ItemDataRole.UserRole)].relative == remembered:
                self.list.setCurrentRow(row)
                break
        self._log(self.t(f'打开模型库：{root}（{len(records)} 个模型）', f'Opened {root} ({len(records)} models)'))

    def navigate(self, offset):
        if self.list.count():
            row = max(0, min(self.list.count() - 1, self.list.currentRow() + offset))
            self.list.setCurrentRow(row)

    def analyze_current(self):
        if self.current is None or self.runner.busy:
            return
        if not self.analyze_button.isEnabled():
            return
        if self.current.error and QMessageBox.question(self, self.t('重新分析', 'Retry analysis'),
            self.t('此模型存在读取或结果错误。是否重新分析，并在成功后保存新的 Studio 结果？',
                   'This model has a loading or result error. Retry and save a new Studio result on success?')) != QMessageBox.StandardButton.Yes:
            return
        self._start([self.current])

    def save_manual_label(self):
        if not self.current or self.runner.busy or self.mode.currentData() != 'kasalv1' or not self._mesh_loaded:
            return
        try:
            record = self.current
            self.store.save_manual(record)
            self._populate(preserve_selection=True)
            self._sync_panel()
            self.status_label.setText(self.t('人工标注已保存，可导出 JSON。', 'Manual annotation saved; JSON export is ready.'))
            self._log(self.t(f'保存人工标注：{record.relative}', f'Saved manual annotation: {record.relative}'))
        except Exception as exc:
            self._error(str(exc))

    def analyze_batch(self):
        if not self.runner.busy:
            self._start(self._batch_records(), batch=True)

    def _batch_records(self):
        return [record for record in self.records if record.dirty and not record.error and record.has_surface is not False]

    def _start(self, records, *, batch=False):
        try:
            engine = self.batch_mode.currentData() if batch else None
            self.runner.start(records, self.store, self.policy, self.device.currentData(),
                              engine=None if engine == 'per_model' else engine, batch=batch)
            self._enable_controls()
        except Exception as exc:
            self._error(str(exc))

    def cancel_jobs(self):
        self.runner.cancel()
        self.status_label.setText(self.t('正在取消；保留已完成的结果…', 'Cancelling; completed results are preserved…'))
        self.cancel_button.setEnabled(False)

    def _progress(self, data):
        stage = {'init': self.t('启动计算', 'Starting'), 'preprocess': self.t('准备模型', 'Preparing mesh'),
                 'analyze': self.t('分析对称性', 'Analyzing symmetry'), 'axis_search': self.t('搜索对称轴', 'Searching axes'),
                 'classify': self.t('识别对称类型', 'Classifying'), 'texture': self.t('分析纹理', 'Analyzing texture'),
                 'cal_sym': self.t('定位对称轴', 'Locating axes'), 'export': self.t('生成结果', 'Preparing results')}.get(data.get('key'), self.t('处理中', 'Working'))
        index, total = data.get('index', 1), data.get('total', 1)
        self.status_label.setText(self.t(f'{stage.zh}  ·  {data.get("mesh_name", "")}', f'{stage.en}  ·  {data.get("mesh_name", "")}'))
        self.counter_label.setText(f'{index} / {total}')
        self.progress_bar.setValue(int(((index - 1 + float(data.get('fraction', 0))) / max(1, total)) * 1000))

    def _job_changed(self, record):
        self._populate()
        if record is self.current:
            self._sync_panel()
        if not record.running:
            self._log(f'{record.path.name}: {record.error or self._status_name(record)}')

    def _completed(self, successes, failures, cancelled):
        self._populate()
        self._enable_controls()
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(1000 if not cancelled else self.progress_bar.value())
        prefix_zh, prefix_en = ('已取消', 'Cancelled') if cancelled else ('分析完成', 'Analysis complete')
        self.status_label.setText(self.t(f'{prefix_zh}  ·  成功 {successes}  ·  失败 {failures}', f'{prefix_en}  ·  {successes} succeeded  ·  {failures} failed'))
        self.counter_label.setText('')
        self._log(self.status_label.text())
        if self._closing_after_cancel:
            self._closing_after_cancel = False
            self.close()

    def restore_current(self):
        if self.current and not self.runner.busy:
            self.store.load(self.current, discard_draft=True)
            self._populate()
            self._sync_panel()

    def mark_all(self):
        if self.runner.busy:
            return
        for record in self.records:
            record.dirty = True
        self._populate()
        self._sync_panel()

    def restore_all(self):
        if self.runner.busy or not self._discard_edits():
            return
        for record in self.records:
            self.store.load(record, discard_draft=True)
        self._populate()
        self._sync_panel()

    def clear_results(self):
        if not self.store or self.runner.busy:
            return
        if QMessageBox.question(self, self.t('清除 Studio 结果', 'Clear Studio results'),
            self.t('将此模型库的 Studio 结果移入工作区回收目录？原模型与旧版标注不会删除。',
                   'Move this library’s Studio results to the workspace trash? Source models and classic annotations are preserved.'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            for record in self.records:
                self.store.clear(record)
            self._populate()
            self._sync_panel()
        except Exception as exc:
            self._error(str(exc))

    def open_results(self):
        if not self.store:
            return
        path = self.store.directory
        try:
            if self.current:
                path = self.store.current_dir(self.current.path) or path
        except (OSError, ValueError):
            pass
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, 'KASAL Studio', self.t('完成首次分析后会创建结果目录。', 'The result folder is created after the first analysis.'))

    def export_result(self):
        if not self.current or self.runner.busy or self.current.edited:
            return
        path = QFileDialog.getExistingDirectory(self, self.t('选择导出目录', 'Choose an export folder'))
        if path:
            try:
                self.store.export(self.current, Path(path))
                self.status_label.setText(self.t('结果已导出', 'Results exported'))
            except Exception as exc:
                self._error(str(exc))

    def save_screenshot(self):
        path, _ = QFileDialog.getSaveFileName(self, self.t('保存截图', 'Save screenshot'),
                                             (self.current.path.stem if self.current else 'kasal') + '.png', 'PNG (*.png)')
        if path:
            try:
                self.view.screenshot(Path(path))
                self.status_label.setText(self.t('截图已保存', 'Screenshot saved'))
            except Exception as exc:
                self._error(str(exc))

    def show_settings(self):
        if self.runner.busy:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('Studio 设置', 'Studio settings'))
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        form.setVerticalSpacing(16)
        policy = QComboBox()
        for text, value in [(self.t('自适应预处理（推荐）', 'Adaptive (recommended)'), 'kasalv2_adaptive'),
                            (self.t('严格几何预处理', 'Strict geometry'), 'kasalv2_strict'),
                            (self.t('经典 PyMeshLab 预处理', 'Classic PyMeshLab'), 'kasalv1')]:
            policy.addItem(text, value)
        policy.setCurrentIndex(max(0, policy.findData(self.policy)))
        form.addRow(self.t('预处理', 'Preprocessing'), policy)
        language = QComboBox()
        language.addItem('简体中文', 'zh')
        language.addItem('English', 'en')
        language.setCurrentIndex(max(0, language.findData(self.language)))
        original_language = self.language
        language.currentIndexChanged.connect(lambda: self.set_language(language.currentData(), persist=False))
        form.addRow(self.t('界面语言', 'Language'), language)
        font_size = QSpinBox()
        font_size.setRange(11, 16)
        font_size.setValue(int(self.settings.value('font_size', 13)))
        form.addRow(self.t('文字大小', 'Text size'), font_size)
        layout.addLayout(form)
        from kasal.device import list_hardware_device_rows
        layout.addWidget(label(self.t('检测到的硬件', 'Detected hardware'), 'section'))
        statuses = {'Selected': ('已选择', 'Selected'), 'Available': ('可用', 'Available'),
                    'Not selectable (CPU-only PyTorch)': ('CUDA 不可用，无法选择', 'CUDA unavailable; cannot select')}
        for hardware in list_hardware_device_rows(self.device.currentData()):
            zh, en = statuses.get(hardware.status, (hardware.status, hardware.status))
            name_zh, name_en = {'(none detected)': ('未检测到', 'None detected'),
                    '(none detected by PyTorch CUDA)': ('PyTorch 未检测到 CUDA 设备', 'No CUDA device detected by PyTorch')}.get(hardware.model_name, (hardware.model_name, hardware.model_name))
            layout.addWidget(label(self.t(f'{hardware.device_type} · {name_zh} · {zh}', f'{hardware.device_type} · {name_en} · {en}'), 'muted', True))
        layout.addWidget(label(self.t('语言即时预览；取消将恢复原设置。', 'Language previews immediately; Cancel restores the previous setting.'), 'muted', True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.policy = policy.currentData()
            self._save_preferences()
            self.settings.setValue('language', language.currentData())
            self.settings.setValue('font_size', font_size.value())
            QApplication.instance().setStyleSheet(STYLE.replace('font-size: 13px;', f'font-size: {font_size.value()}px;'))
            self.settings.sync()
        else:
            self.set_language(original_language, persist=False)
        dialog.deleteLater()

    def show_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('视图与操作', 'Navigation & shortcuts'))
        dialog.resize(540, 440)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label(self.t('让模型停在你想看的位置', 'Navigate with confidence'), 'title'))
        pairs = [(self.t('左键拖动', 'Left drag'), self.t('旋转视角', 'Orbit')),
                 (self.t('中键 / Shift＋左键', 'Middle / Shift+left drag'), self.t('平移', 'Pan')),
                 (self.t('滚轮 / 右键拖动', 'Wheel / right drag'), self.t('缩放', 'Zoom')),
                 (self.t('双击模型', 'Double-click mesh'), self.t('聚焦到点击位置', 'Focus at clicked point')),
                 ('F', self.t('适应模型', 'Frame mesh')), ('1 / 3 / 7', self.t('正面 / 右侧 / 顶部', 'Front / right / top')),
                 ('5', self.t('正交 / 透视', 'Orthographic / perspective')), ('Ctrl+Enter', self.t('分析当前模型', 'Analyze model')),
                 ('Ctrl+S', self.t('保存人工标注（人工模式）', 'Save manual label (manual mode)')),
                 ('PageUp / PageDown', self.t('切换模型', 'Previous / next model'))]
        text = '<table cellspacing="12">' + ''.join(f'<tr><td><b>{html.escape(a)}</b></td><td>{html.escape(b)}</td></tr>' for a, b in pairs) + '</table>'
        layout.addWidget(QLabel(text))
        layout.addWidget(label(self.t('视图快捷键在三维区域获得焦点时生效。', 'View shortcuts are active when the viewport has focus.'), 'muted', True))
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()
        dialog.deleteLater()

    def show_activity(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('任务记录', 'Activity'))
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit('\n'.join(self.logs))
        text.setReadOnly(True)
        layout.addWidget(text)
        dialog.exec()
        dialog.deleteLater()

    def _log(self, message):
        self.logs.append(f'{datetime.now():%H:%M:%S}  {message}')
        self.logs = self.logs[-200:]

    def _error(self, message):
        self._log(message)
        QMessageBox.warning(self, 'KASAL Studio', message)

    def dragEnterEvent(self, event):
        if not self.runner.busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.open_path(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    def capture_preview(self, path: Path):
        # Qt's grab excludes the native VTK child: capture its actual framebuffer too.
        QApplication.processEvents()
        pixmap = self.grab()
        painter = QPainter(pixmap)
        painter.drawImage(self.view.mapTo(self, QPoint(0, 0)), self.view.image().scaled(self.view.size(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        painter.end()
        pixmap.save(str(path), 'PNG')

    def closeEvent(self, event):
        if self.runner.busy:
            if QMessageBox.question(self, self.t('计算仍在进行', 'Analysis in progress'),
                self.t('取消当前任务并关闭？已完成的结果会保留。', 'Cancel the active job and close? Completed results are preserved.')) == QMessageBox.StandardButton.Yes:
                self._closing_after_cancel = True
                self.cancel_jobs()
            event.ignore()
            return
        if not self._discard_edits():
            event.ignore()
            return
        self.settings.sync()
        self.view.shutdown()
        event.accept()
