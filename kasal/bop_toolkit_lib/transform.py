# Author: Tomas Hodan (hodantom@cmp.felk.cvut.cz)
# Center for Machine Perception, Czech Technical University in Prague

"""Transformation helpers used by KASAL.

This is the project-used subset of the bundled BOP transformation module.
The original license remains in ``LICENSE.txt`` in this package.
"""

import math

import numpy


_NEXT_AXIS = [1, 2, 0, 1]
_AXES2TUPLE = {
    "sxyz": (0, 0, 0, 0),
    "sxyx": (0, 0, 1, 0),
    "sxzy": (0, 1, 0, 0),
    "sxzx": (0, 1, 1, 0),
    "syzx": (1, 0, 0, 0),
    "syzy": (1, 0, 1, 0),
    "syxz": (1, 1, 0, 0),
    "syxy": (1, 1, 1, 0),
    "szxy": (2, 0, 0, 0),
    "szxz": (2, 0, 1, 0),
    "szyx": (2, 1, 0, 0),
    "szyz": (2, 1, 1, 0),
    "rzyx": (0, 0, 0, 1),
    "rxyx": (0, 0, 1, 1),
    "ryzx": (0, 1, 0, 1),
    "rxzx": (0, 1, 1, 1),
    "rxzy": (1, 0, 0, 1),
    "ryzy": (1, 0, 1, 1),
    "rzxy": (1, 1, 0, 1),
    "ryxy": (1, 1, 1, 1),
    "ryxz": (2, 0, 0, 1),
    "rzxz": (2, 0, 1, 1),
    "rxyz": (2, 1, 0, 1),
    "rzyz": (2, 1, 1, 1),
}
_TUPLE2AXES = {value: key for key, value in _AXES2TUPLE.items()}


def euler_matrix(ai, aj, ak, axes="sxyz"):
    """Return a homogeneous rotation matrix for the Euler axis sequence."""

    try:
        firstaxis, parity, repetition, frame = _AXES2TUPLE[axes]
    except (AttributeError, KeyError):
        _TUPLE2AXES[axes]
        firstaxis, parity, repetition, frame = axes

    i = firstaxis
    j = _NEXT_AXIS[i + parity]
    k = _NEXT_AXIS[i - parity + 1]

    if frame:
        ai, ak = ak, ai
    if parity:
        ai, aj, ak = -ai, -aj, -ak

    si, sj, sk = math.sin(ai), math.sin(aj), math.sin(ak)
    ci, cj, ck = math.cos(ai), math.cos(aj), math.cos(ak)
    cc, cs = ci * ck, ci * sk
    sc, ss = si * ck, si * sk

    matrix = numpy.identity(4)
    if repetition:
        matrix[i, i] = cj
        matrix[i, j] = sj * si
        matrix[i, k] = sj * ci
        matrix[j, i] = sj * sk
        matrix[j, j] = -cj * ss + cc
        matrix[j, k] = -cj * cs - sc
        matrix[k, i] = -sj * ck
        matrix[k, j] = cj * sc + cs
        matrix[k, k] = cj * cc - ss
    else:
        matrix[i, i] = cj * ck
        matrix[i, j] = sj * sc - cs
        matrix[i, k] = sj * cc + ss
        matrix[j, i] = cj * sk
        matrix[j, j] = sj * ss + cc
        matrix[j, k] = sj * cs - sc
        matrix[k, i] = -sj
        matrix[k, j] = cj * si
        matrix[k, k] = cj * ci
    return matrix
