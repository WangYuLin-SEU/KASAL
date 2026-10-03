# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

"""Read polygonal STEP faces and infer their candidate symmetry axes."""

import chardet
import numpy as np
from scipy import spatial
from kasal.geometry.transforms import rotation_about_axis


def _extract_vertex_points(vertex_fields):
    points = []
    for point_entity in vertex_fields:
        if not isinstance(point_entity, dict):
            continue
        for coordinates in point_entity.values():
            points.append([float(coordinates[1]), float(coordinates[2]), float(coordinates[3])])
    return points


def _extract_edge_points(edge):
    points = []
    for fields in edge.values():
        for entity in fields:
            if not isinstance(entity, dict):
                continue
            for entity_type, vertex_fields in entity.items():
                if 'VERTEX_POINT' in entity_type:
                    points.extend(_extract_vertex_points(vertex_fields))
    return points


def _extract_face_edges(face):
    edges = []
    for oriented_edge in face:
        if not isinstance(oriented_edge, dict):
            continue
        for fields in oriented_edge.values():
            for edge in fields:
                if isinstance(edge, dict):
                    edges.append(_extract_edge_points(edge))
    return edges


def load_step_faces(step_path):
    """Read STEP edge loops as endpoint pairs; supports closed planar polyhedra."""

    def resolve_entity(entity_id, entities):
        """Expand references in the STEP entity table."""

        resolved_entity = {}
        entity_text = entities[entity_id]
        cut_position = entity_text.find("(")
        entity_type, values = entity_text[:cut_position], entity_text[cut_position+1:-2].split(",")
        for i, value in enumerate(values):
            values[i] = value.replace('(','').replace(')','').strip()
            if values[i].startswith("#"):
                values[i] = resolve_entity(values[i], entities)
        resolved_entity[entity_type] = values
        return resolved_entity
    with open(step_path,'rb') as f:
        raw_bytes = f.read()
    file_encoding = chardet.detect(raw_bytes)['encoding']
    step_text = raw_bytes.decode(file_encoding or 'utf-8').replace('\r\n', '\n').replace('\r', '\n')
    print('stp: ', file_encoding)
    step_text = step_text.replace('ISO-10303-21\n','').replace('"END-ISO-10303-21\n"','')
    data = step_text[step_text.index('DATA') + len('DATA') + 2:]
    data_root = {}
    data_lines = {}
    data_list = data.split('\n')
    for line in data_list:
        cut_position = line.find("=")
        if cut_position != -1:
            key = line[0:cut_position].strip()
            value = line[cut_position + 2:].strip()
            data_lines[key] = value.strip()
    for key in data_lines.keys():
        line = data_lines[key]
        cut_position1 = line.find("(")
        cut_position2 = line.find(";") - 1
        references = []
        if line.find('#') == -1:continue
        entity_type = line[0:cut_position1].strip()
        if entity_type != 'EDGE_LOOP' : continue
        key = key + ' ' + entity_type
        reference_text = line[cut_position1 + 1:cut_position2]
        references = reference_text.split(',')
        resolved_references = reference_text.split(',')
        for i in range(len(references)):
            reference = references[i].replace('(','').replace(')','').strip()
            if reference[0] == "#":
                resolved_entity = resolve_entity(reference.strip(), data_lines)
                resolved_references[i] = resolved_entity
        data_root[key] = resolved_references

    return [_extract_face_edges(face) for face in data_root.values()]

def infer_step_symmetry_axes(face_edges):
    """Return normalized symmetry axes and non-identity rotation counts."""

    def edge_midpoint(edge):

        l1, l2 = edge
        return [(l1[0] + l2[0])/2, (l1[1] + l2[1])/2, (l1[2] + l2[2])/2, ]
    def segment_length(edge):

        return np.linalg.norm(np.array(edge[0])-np.array(edge[1]))
    def contains_nearby_point(points, point, tolerance):

        for candidate in points:
            if segment_length([point, candidate]) < tolerance:
                return 1
        return 0
    def max_rotation_distance(points, transform):

        transformed_points = np.dot(points, transform[:3,:3])+transform[:3,3]
        point_tree = spatial.cKDTree(points)
        distances, nearest_indices = point_tree.query(transformed_points, k=1)
        return np.max(distances)

    tolerance_divisor = 1e+3

    unique_edges = []
    edge_midpoints = []
    for face in face_edges:
        for edge in face:
            midpoint = edge_midpoint(edge)
            edge_length = segment_length(edge)
            if contains_nearby_point(edge_midpoints, midpoint, edge_length/tolerance_divisor) == 0:
                unique_edges.append(edge)
                edge_midpoints.append(midpoint)
    edge_midpoints = np.array(edge_midpoints)
    edge_rotation_counts = np.ones((edge_midpoints.shape[0]))

    mean_edge_length = []
    for edge in unique_edges:
        mean_edge_length.append(segment_length(edge))
    mean_edge_length = np.mean(mean_edge_length)

    unique_vertices = []
    for face in face_edges:
        for edge in face:
            for points in edge:
                if contains_nearby_point(unique_vertices, points, mean_edge_length/tolerance_divisor) == 0:
                    unique_vertices.append(points)
    unique_vertices = np.array(unique_vertices)
    vertex_directions = unique_vertices
    vertex_rotation_counts = []
    for point in unique_vertices:
        incident_edge_count = 0
        for line in unique_edges:
            if contains_nearby_point(line, point, mean_edge_length/tolerance_divisor) == 1:
                incident_edge_count += 1
        vertex_rotation_counts.append(incident_edge_count - 1)
    vertex_rotation_counts = np.array(vertex_rotation_counts)

    face_centers = []
    face_rotation_counts = []
    for face in face_edges:
        face_rotation_counts.append(len(face) - 1)
        face_vertices = []
        for edge in face:
            for points in edge:
                face_vertices.append(points)
        face_centers.append(np.mean(np.array(face_vertices), axis = 0))
    face_centers = np.array(face_centers)
    face_rotation_counts = np.array(face_rotation_counts)

    center = np.mean(unique_vertices, axis = 0)

    vertex_directions = vertex_directions - center
    vertex_axes = vertex_directions / np.linalg.norm(vertex_directions, axis=1, keepdims=True)
    vertex_rotation_counts = np.array(vertex_rotation_counts)

    edge_midpoints = edge_midpoints - center
    edge_axes = edge_midpoints / np.linalg.norm(edge_midpoints, axis=1, keepdims=True)
    edge_rotation_counts = np.array(edge_rotation_counts)

    face_centers = face_centers - center
    face_axes = face_centers / np.linalg.norm(face_centers, axis=1, keepdims=True)
    face_rotation_counts = np.array(face_rotation_counts)

    reference_points = np.concatenate([vertex_directions, edge_midpoints, face_centers], axis = 0)
    candidate_axes = np.concatenate([vertex_axes, edge_axes, face_axes], axis = 0)
    candidate_rotation_counts = np.concatenate([vertex_rotation_counts, edge_rotation_counts, face_rotation_counts], axis = 0).astype('int')

    symmetry_axes = []
    symmetry_rotation_counts = []
    for (candidate_axis, rotation_count) in zip(candidate_axes, candidate_rotation_counts):
        valid_rotation_count = 0
        rotation_step_deg = 360 / (rotation_count + 1)
        for i in range(rotation_count):
            rotation_transform = rotation_about_axis(candidate_axis, rotation_step_deg*(i+1), np.zeros((3)))
            max_distance = max_rotation_distance(reference_points, rotation_transform)
            if max_distance < mean_edge_length/tolerance_divisor:
                valid_rotation_count += 1

        if contains_nearby_point(symmetry_axes, candidate_axis, 1/1000) + contains_nearby_point(symmetry_axes, -candidate_axis, 1/1000) == 0:
            if valid_rotation_count > 0:
                symmetry_axes.append(candidate_axis)
                symmetry_rotation_counts.append(valid_rotation_count)
            continue
        for j, existing_axis in enumerate(symmetry_axes):
            matches = (
                segment_length([existing_axis, candidate_axis]) < 1/1000
                or segment_length([existing_axis, -candidate_axis]) < 1/1000
            )
            if matches and symmetry_rotation_counts[j] < valid_rotation_count:
                symmetry_rotation_counts[j] = valid_rotation_count

    return np.array(symmetry_axes), np.array(symmetry_rotation_counts)
