# Author: Tomas Hodan (hodantom@cmp.felk.cvut.cz)
# Center for Machine Perception, Czech Technical University in Prague

"""Sphere sampling helper used by KASAL.

This is the project-used subset of the bundled BOP view sampler.
The original license remains in ``LICENSE.txt`` in this package.
"""

import math


def fibonacci_sampling(n_pts, radius=1.0):
    """Sample an odd number of near-equidistant points on a sphere."""

    assert n_pts % 2 == 1
    n_pts_half = int(n_pts / 2)

    phi = (math.sqrt(5.0) + 1.0) / 2.0
    golden_angle = 2.0 * math.pi * (phi - 1.0)

    points = []
    for index in range(-n_pts_half, n_pts_half + 1):
        latitude = math.asin((2 * index) / float(2 * n_pts_half + 1))
        longitude = (golden_angle * index) % (2 * math.pi)
        scale = math.cos(latitude) * radius
        points.append(
            [
                math.cos(longitude) * scale,
                math.sin(longitude) * scale,
                math.tan(latitude) * scale,
            ]
        )
    return points
