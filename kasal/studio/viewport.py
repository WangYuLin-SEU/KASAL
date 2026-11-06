"""Embedded VTK view with predictable mouse navigation and mesh materials."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import numpy as np
import trimesh
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
import vtkmodules.qt
vtkmodules.qt.PyQtImpl = 'PySide6'
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray, vtk_to_numpy
import vtkmodules.vtkRenderingOpenGL2  # register the OpenGL backend
import vtkmodules.vtkInteractionStyle
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkCellArray, vtkImageData
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals, vtkTubeFilter
from vtkmodules.vtkFiltersSources import vtkLineSource, vtkSphereSource
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkActor, vtkPolyDataMapper, vtkTexture, vtkCellPicker, vtkPointPicker, vtkWindowToImageFilter, vtkLight, vtkColorTransferFunction
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor, vtkScalarBarActor
from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkIOImage import vtkPNGWriter
from .geometry import scalar_fields, finite_range, symmetry_lines


@dataclass
class ScenePart:
    name: str
    actor: object
    texture: object
    fields: dict = field(default_factory=dict)
    color_domain: str = 'point'
    point_cloud: bool = False
    visible: bool = True
    opacity: float = 1.0


def mesh_actor(mesh, fields=None):
    poly = vtkPolyData()
    points = vtkPoints()
    points.SetData(numpy_to_vtk(np.ascontiguousarray(mesh.vertices, dtype=np.float64), deep=True))
    poly.SetPoints(points)
    cells = vtkCellArray()
    faces = getattr(mesh, 'faces', [])
    if len(faces):
        packed = np.column_stack((np.full(len(faces), 3), faces)).astype(np.int64)
        cells.SetCells(len(faces), numpy_to_vtkIdTypeArray(packed.ravel(), deep=True))
        poly.SetPolys(cells)
    else:
        packed = np.column_stack((np.ones(len(mesh.vertices)), np.arange(len(mesh.vertices)))).astype(np.int64)
        cells.SetCells(len(mesh.vertices), numpy_to_vtkIdTypeArray(packed.ravel(), deep=True))
        poly.SetVerts(cells)
    mapper = vtkPolyDataMapper()
    actor = vtkActor()
    actor.SetMapper(mapper)
    texture = None
    visual = mesh.visual
    if visual.kind == 'vertex' and len(visual.vertex_colors) == len(mesh.vertices):
        colors = numpy_to_vtk(np.ascontiguousarray(visual.vertex_colors, dtype=np.uint8), deep=True)
        colors.SetName('Colors')
        poly.GetPointData().SetScalars(colors)
        mapper.SetColorModeToDirectScalars()
    elif visual.kind == 'face':
        colors = numpy_to_vtk(np.ascontiguousarray(visual.face_colors, dtype=np.uint8), deep=True)
        poly.GetCellData().SetScalars(colors)
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
    elif visual.kind == 'texture' and visual.uv is not None:
        material = visual.material
        picture = getattr(material, 'image', None)
        if picture is None:
            picture = getattr(material, 'baseColorTexture', None)
        if picture is not None:
            pixels = np.asarray(picture.convert('RGB'))[::-1].copy()
            data = vtkImageData()
            data.SetDimensions(pixels.shape[1], pixels.shape[0], 1)
            data.GetPointData().SetScalars(numpy_to_vtk(pixels.reshape(-1, 3), deep=True))
            texture = vtkTexture()
            texture.SetInputData(data)
            texture.InterpolateOn()
            actor.SetTexture(texture)
            uv = numpy_to_vtk(np.ascontiguousarray(visual.uv, dtype=np.float32), deep=True)
            poly.GetPointData().SetTCoords(uv)
    for (domain, name), values in (fields or {}).items():
        array = numpy_to_vtk(np.ascontiguousarray(values), deep=True)
        array.SetName('scalar:' + name)
        (poly.GetPointData() if domain == 'point' else poly.GetCellData()).AddArray(array)
    if len(faces):
        normals = vtkPolyDataNormals()
        normals.SetInputData(poly)
        normals.SetFeatureAngle(35)
        normals.ConsistencyOn()
        normals.AutoOrientNormalsOn()
        mapper.SetInputConnection(normals.GetOutputPort())
    else:
        mapper.SetInputData(poly)
        actor.GetProperty().SetPointSize(4)
        actor.GetProperty().SetRenderPointsAsSpheres(True)
    actor.GetProperty().SetColor(0.66, 0.73, 0.84)
    if texture is not None:
        actor.GetProperty().SetColor(1, 1, 1)
    actor.GetProperty().SetAmbient(0.27)
    actor.GetProperty().SetDiffuse(0.72)
    actor.GetProperty().SetSpecular(0.18)
    actor.GetProperty().SetSpecularPower(35)
    actor.GetProperty().SetEdgeColor(0.25, 0.34, 0.47)
    return actor, texture


class MeshViewport(QVTKRenderWindowInteractor):
    cameraChanged = Signal()
    presetChanged = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.965, 0.975, 0.989)
        self.renderer.SetBackground2(0.995, 0.997, 1.0)
        self.renderer.GradientBackgroundOn()
        self.renderer.AutomaticLightCreationOff()
        self.lights = []
        for intensity in (.85, .55):
            light = vtkLight()
            light.SetLightTypeToSceneLight()
            light.SetIntensity(intensity)
            self.renderer.AddLight(light)
            self.lights.append(light)
        self.GetRenderWindow().AddRenderer(self.renderer)
        self.GetRenderWindow().SetMultiSamples(4)
        self.style = vtkInteractorStyleTrackballCamera()
        self.style.SetDefaultRenderer(self.renderer)
        self.style.AddObserver('StartInteractionEvent', lambda *_: self.presetChanged.emit('custom'))
        self.SetInteractorStyle(self.style)
        self.meshes = []
        self.parts = []
        self.result_meshes = []
        self.result_path = None
        self.result_stamp = None
        self.result_visible = False
        self.symmetry_actors = []
        self.grid_actors = []
        self.bounds = np.array([[-1., -1., -1.], [1., 1., 1.]])
        self.colors = True
        self.edges = False
        self.wireframe = False
        self.opacity = 1.0
        self.point_size = 4
        self.shading = 'smooth'
        self.light_strength = 1.0
        self.scalar_key = None
        self.scalar_palette = 'viridis'
        self.scalar_limits = None
        self.lookup = vtkColorTransferFunction()
        self.scalar_bar = vtkScalarBarActor()
        self.scalar_bar.SetLookupTable(self.lookup)
        self.scalar_bar.SetNumberOfLabels(4)
        self.scalar_bar.SetWidth(.12)
        self.scalar_bar.SetHeight(.33)
        self.scalar_bar.SetPosition(.86, .1)
        self.scalar_bar.GetLabelTextProperty().SetColor(.25, .32, .43)
        self.scalar_bar.GetLabelTextProperty().SetFontSize(12)
        self.scalar_bar.GetLabelTextProperty().BoldOff()
        self.scalar_bar.GetLabelTextProperty().ItalicOff()
        self.scalar_bar.GetLabelTextProperty().ShadowOff()
        self.scalar_bar.SetVisibility(False)
        self.renderer.AddViewProp(self.scalar_bar)
        self.symmetry_visible = True
        self.grid_visible = True
        self.coordinates = vtkAxesActor()
        self.coordinates_visible = False
        self.coordinates.SetVisibility(False)
        self.renderer.AddActor(self.coordinates)
        self.marker = vtkOrientationMarkerWidget()
        self.marker.SetOrientationMarker(vtkAxesActor())
        self.marker.SetInteractor(self.GetRenderWindow().GetInteractor())
        self.marker.SetViewport(0, 0, 0.17, 0.20)
        self.Initialize()
        self.marker.SetEnabled(1)
        self.marker.InteractiveOff()

    def load_mesh(self, path: Path) -> dict:
        scene = trimesh.load(str(path), force='scene', process=False)
        loaded = []
        parts = []
        bounds = []
        vertices = faces = 0
        for node in scene.graph.nodes_geometry:
            transform, name = scene.graph[node]
            source = scene.geometry[name]
            if not isinstance(source, (trimesh.Trimesh, trimesh.points.PointCloud)) or not len(source.vertices):
                continue
            mesh = source.copy()
            mesh.apply_transform(transform)
            if not np.isfinite(mesh.vertices).all():
                raise ValueError('Geometry contains non-finite coordinates.')
            fields = scalar_fields(source)
            actor, texture = mesh_actor(mesh, fields)
            loaded.append((actor, texture))
            face_count = len(getattr(mesh, 'faces', []))
            parts.append(ScenePart(str(node), actor, texture, fields,
                                   'cell' if mesh.visual.kind == 'face' else 'point', not face_count))
            bounds.append(mesh.bounds)
            vertices += len(mesh.vertices)
            faces += face_count
        if not loaded:
            raise ValueError('This file contains no mesh or point cloud.')
        self.set_visualization(None)
        for actor, _ in self.meshes:
            self.renderer.RemoveActor(actor)
        self.meshes = loaded
        self.parts = parts
        self.scalar_key = self.scalar_limits = None
        for actor, _ in loaded:
            self.renderer.AddActor(actor)
        all_bounds = np.concatenate(bounds)
        self.bounds = np.array([all_bounds.min(axis=0), all_bounds.max(axis=0)])
        extent = max(float(np.ptp(self.bounds, axis=0).max()), 1e-6)
        center = self.bounds.mean(axis=0)
        for light, direction in zip(self.lights, ((2, -3, 4), (-3, 1, 2))):
            light.SetPosition(*(center + np.asarray(direction) * extent))
            light.SetFocalPoint(*center)
        self.coordinates.SetPosition(*self.bounds.mean(axis=0))
        self.coordinates.SetVisibility(self.coordinates_visible)
        self.coordinates.SetTotalLength(extent * .8, extent * .8, extent * .8)
        self.set_result({})
        self._make_grid()
        self.apply_appearance()
        self.set_view('iso')
        return {'vertices': vertices, 'faces': faces, 'size': self.bounds[1] - self.bounds[0],
                'materials': len(loaded), 'textured': any(t is not None for _, t in loaded),
                'point_cloud': faces == 0}

    def clear(self):
        self.set_visualization(None)
        for actor, _ in self.meshes:
            self.renderer.RemoveActor(actor)
        self.meshes = []
        self.parts = []
        self.scalar_key = None
        self.scalar_limits = None
        self.scalar_bar.SetVisibility(False)
        self.coordinates.SetVisibility(False)
        for actor in self.grid_actors:
            self.renderer.RemoveActor(actor)
        self.grid_actors = []
        self.bounds = np.array([[-1., -1., -1.], [1., 1., 1.]])
        self.set_result({})

    def set_visualization(self, path: Path | None):
        stat = path.stat() if path is not None else None
        stamp = (stat.st_mtime_ns, stat.st_size) if stat is not None else None
        if path is not None and path == self.result_path and stamp == self.result_stamp:
            return bool(self.result_meshes)
        for actor, _ in self.result_meshes:
            self.renderer.RemoveActor(actor)
        self.result_meshes = []
        self.result_path = None
        self.result_stamp = None
        if path is not None:
            scene = trimesh.load(str(path), force='scene', process=False)
            for node in scene.graph.nodes_geometry:
                transform, name = scene.graph[node]
                mesh = scene.geometry[name].copy()
                if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
                    continue
                mesh.apply_transform(transform)
                actor, texture = mesh_actor(mesh)
                self.result_meshes.append((actor, texture))
                self.renderer.AddActor(actor)
            if not self.result_meshes:
                raise ValueError('The symmetry visualization contains no triangle mesh.')
            self.result_path = path
            self.result_stamp = stamp
        self.apply_appearance()
        return bool(self.result_meshes)

    def set_result_visible(self, enabled):
        self.result_visible = bool(enabled)
        self.apply_appearance()

    def set_coordinates_visible(self, enabled):
        self.coordinates_visible = bool(enabled)
        self.coordinates.SetVisibility(enabled and bool(self.parts))
        self.render()

    def _line(self, start, end, color, width=1.0, tube=False):
        line = vtkLineSource()
        line.SetPoint1(*start)
        line.SetPoint2(*end)
        mapper = vtkPolyDataMapper()
        if tube:
            filt = vtkTubeFilter()
            filt.SetInputConnection(line.GetOutputPort())
            filt.SetRadius(width)
            filt.SetNumberOfSides(12)
            filt.CappingOn()
            mapper.SetInputConnection(filt.GetOutputPort())
        else:
            mapper.SetInputConnection(line.GetOutputPort())
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetLineWidth(1)
        actor.PickableOff()
        self.renderer.AddActor(actor)
        return actor

    def _make_grid(self):
        for actor in self.grid_actors:
            self.renderer.RemoveActor(actor)
        self.grid_actors = []
        center = self.bounds.mean(axis=0)
        size = max(float(np.max(self.bounds[1] - self.bounds[0])), 1e-6)
        z = self.bounds[0, 2] - size * .035
        extent = size * 1.25
        for offset in np.linspace(-extent, extent, 21):
            for axis in (0, 1):
                a, b = center.copy(), center.copy()
                a[2] = b[2] = z
                a[axis], b[axis] = center[axis] - extent, center[axis] + extent
                a[1-axis] = b[1-axis] = center[1-axis] + offset
                actor = self._line(a, b, (.87, .90, .94))
                actor.SetVisibility(self.grid_visible)
                self.grid_actors.append(actor)

    def set_result(self, info: dict):
        for actor in self.symmetry_actors:
            self.renderer.RemoveActor(actor)
        self.symmetry_actors = []
        lines = symmetry_lines(info, self.bounds.mean(axis=0))
        size = max(float(np.max(self.bounds[1] - self.bounds[0])), 1e-6)
        for index, (axis, center) in enumerate(lines):
            color = (.17, .42, .84) if index == 0 else (.18, .65, .64)
            actor = self._line(center - axis * size * .72, center + axis * size * .72,
                               color, width=size * .0025, tube=True)
            actor.SetVisibility(self.symmetry_visible)
            self.symmetry_actors.append(actor)
        self.render()
        return len(lines)

    def available_scalars(self):
        return sorted({key for part in self.parts for key in part.fields})

    def scalar_range(self, key=None):
        key = self.scalar_key if key is None else key
        return finite_range(part.fields[key] for part in self.parts if key in part.fields)

    def set_scalar(self, key, *, palette='viridis', limits=None):
        if key is not None and key not in self.available_scalars():
            raise ValueError('This scalar field is not available.')
        if limits is not None and (not np.isfinite(limits).all() or limits[0] >= limits[1]):
            raise ValueError('The scalar range must have a finite minimum below its maximum.')
        self.scalar_key, self.scalar_palette, self.scalar_limits = key, palette, limits
        self.apply_appearance()

    def _update_lookup(self):
        span = self.scalar_limits or self.scalar_range()
        if span is None:
            return
        low, high = span
        if low == high:
            padding = max(abs(low) * .01, .5)
            low, high = low - padding, high + padding
        palettes = {
            'viridis': [(.267, .005, .329), (.23, .322, .546), (.128, .567, .551), (.369, .789, .383), (.993, .906, .144)],
            'diverging': [(.23, .30, .75), (.87, .87, .87), (.71, .016, .15)],
            'gray': [(.12, .12, .12), (.94, .94, .94)],
        }
        colors = palettes.get(self.scalar_palette, palettes['viridis'])
        self.lookup.RemoveAllPoints()
        self.lookup.SetColorSpaceToRGB()
        self.lookup.SetNanColor(.6, .6, .6)
        for value, rgb in zip(np.linspace(low, high, len(colors)), colors):
            self.lookup.AddRGBPoint(value, *rgb)

    def apply_appearance(self):
        show_result = self.result_visible and bool(self.result_meshes)
        self._update_lookup()
        legend = False
        for part in self.parts:
            actor, mapper = part.actor, part.actor.GetMapper()
            actor.SetVisibility(part.visible and not show_result)
            use_scalar = self.scalar_key is not None and self.scalar_key in part.fields
            if use_scalar:
                domain, name = self.scalar_key
                if domain == 'point':
                    mapper.SetScalarModeToUsePointFieldData()
                else:
                    mapper.SetScalarModeToUseCellFieldData()
                mapper.SelectColorArray('scalar:' + name)
                mapper.SetColorModeToMapScalars()
                mapper.SetLookupTable(self.lookup)
                mapper.UseLookupTableScalarRangeOn()
                mapper.SetScalarVisibility(True)
                actor.SetTexture(None)
                legend |= bool(actor.GetVisibility())
            else:
                colors = self.colors and self.scalar_key is None
                mapper.SetScalarModeToUsePointData() if part.color_domain == 'point' else mapper.SetScalarModeToUseCellData()
                mapper.SetColorModeToDirectScalars()
                mapper.SetScalarVisibility(colors)
                actor.SetTexture(part.texture if colors else None)
            actor.GetProperty().SetColor(*((1., 1., 1.) if part.texture is not None and self.colors and self.scalar_key is None else (.66, .73, .84)))
            self._actor_appearance(actor, self.opacity * part.opacity)
        for actor, _ in self.result_meshes:
            actor.SetVisibility(show_result)
            actor.GetMapper().SetScalarVisibility(True)
            self._actor_appearance(actor, self.opacity)
        self.scalar_bar.SetVisibility(legend)
        for light, intensity in zip(self.lights, (.85, .55)):
            light.SetIntensity(intensity * self.light_strength)
        self.renderer.ResetCameraClippingRange()
        self.render()

    def _actor_appearance(self, actor, opacity):
        prop = actor.GetProperty()
        prop.SetOpacity(opacity)
        prop.SetPointSize(self.point_size)
        prop.SetEdgeVisibility(self.edges)
        prop.SetLighting(self.shading != 'unlit')
        if self.shading == 'flat':
            prop.SetInterpolationToFlat()
        else:
            prop.SetInterpolationToPhong()
        if self.wireframe:
            prop.SetRepresentationToWireframe()
        else:
            prop.SetRepresentationToSurface()

    def set_part(self, index, *, visible=None, opacity=None):
        part = self.parts[index]
        if visible is not None:
            part.visible = bool(visible)
        if opacity is not None:
            part.opacity = float(np.clip(opacity, 0, 1))
        self.apply_appearance()

    def reset_parts(self):
        for part in self.parts:
            part.visible, part.opacity = True, 1.0
        self.apply_appearance()

    def set_symmetry_visible(self, enabled):
        self.symmetry_visible = bool(enabled)
        for actor in self.symmetry_actors:
            actor.SetVisibility(enabled)
        self.render()

    def set_grid_visible(self, enabled):
        self.grid_visible = bool(enabled)
        for actor in self.grid_actors:
            actor.SetVisibility(enabled)
        self.render()

    def fit(self):
        b = self.bounds
        self.renderer.ResetCamera(b[0, 0], b[1, 0], b[0, 1], b[1, 1], b[0, 2], b[1, 2])
        self.renderer.GetActiveCamera().Zoom(1.0)
        self.renderer.ResetCameraClippingRange()
        self.render()

    def set_view(self, view):
        direction, up = {'iso': ((1, -1.4, .9), (0, 0, 1)),
                         'front': ((0, -1, 0), (0, 0, 1)),
                         'right': ((1, 0, 0), (0, 0, 1)),
                         'top': ((0, 0, 1), (0, 1, 0))}[view]
        center = self.bounds.mean(axis=0)
        camera = self.renderer.GetActiveCamera()
        camera.SetFocalPoint(*center)
        camera.SetPosition(*(center + np.asarray(direction) * max(float(np.ptp(self.bounds, axis=0).max()), 1)))
        camera.SetViewUp(*up)
        self.fit()
        self.presetChanged.emit(view)

    def set_orthographic(self, enabled):
        self.renderer.GetActiveCamera().SetParallelProjection(enabled)
        self.render()
        self.cameraChanged.emit()

    def keyPressEvent(self, event):
        key = event.key()
        actions = {Qt.Key.Key_F: self.fit, Qt.Key.Key_1: lambda: self.set_view('front'),
                   Qt.Key.Key_3: lambda: self.set_view('right'), Qt.Key.Key_7: lambda: self.set_view('top'),
                   Qt.Key.Key_5: lambda: self.set_orthographic(not self.renderer.GetActiveCamera().GetParallelProjection())}
        if key in actions and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            actions[key]()
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        scale = self.devicePixelRatioF()
        picked = None
        for picker in (vtkCellPicker(), vtkPointPicker()):
            picker.PickFromListOn()
            picker.SetTolerance(.01)
            for actor, _ in self.meshes + self.result_meshes:
                if actor.GetVisibility() and actor.GetProperty().GetOpacity() > 0:
                    picker.AddPickList(actor)
            if picker.Pick(event.position().x() * scale, (self.height() - event.position().y() - 1) * scale, 0, self.renderer):
                picked = np.asarray(picker.GetPickPosition())
                break
        if picked is not None:
            camera = self.renderer.GetActiveCamera()
            offset = picked - np.asarray(camera.GetFocalPoint())
            camera.SetPosition(*(np.asarray(camera.GetPosition()) + offset))
            camera.SetFocalPoint(*picked)
            self.renderer.ResetCameraClippingRange()
            self.render()
        self.style.OnLeftButtonUp()
        event.accept()

    def render(self):
        self.GetRenderWindow().Render()

    def image(self) -> QImage:
        capture = vtkWindowToImageFilter()
        capture.SetInput(self.GetRenderWindow())
        capture.ReadFrontBufferOff()
        capture.Update()
        data = capture.GetOutput()
        w, h, _ = data.GetDimensions()
        pixels = vtk_to_numpy(data.GetPointData().GetScalars()).reshape(h, w, -1)[::-1].copy()
        return QImage(pixels.data, w, h, pixels.strides[0], QImage.Format.Format_RGB888).copy()

    def screenshot(self, path: Path):
        if not self.image().save(str(path), 'PNG'):
            raise OSError(f'Could not write screenshot: {path}')

    def shutdown(self):
        self.marker.SetEnabled(0)
        self.Finalize()
