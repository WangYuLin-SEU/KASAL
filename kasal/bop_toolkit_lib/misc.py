# Author: Tomas Hodan (hodantom@cmp.felk.cvut.cz)
# Center for Machine Perception, Czech Technical University in Prague

"""Point-cloud helper used by KASAL.

This is the project-used subset of the bundled BOP miscellaneous utilities.
The original license remains in ``LICENSE.txt`` in this package.
"""

import math

import numpy as np


def calc_pts_diameter(pts):
    """Calculate the maximum Euclidean distance between any two points."""

    diameter = -1.0
    for point_id in range(pts.shape[0]):
        duplicated = np.tile(np.array([pts[point_id, :]]), [pts.shape[0] - point_id, 1])
        differences = duplicated - pts[point_id:, :]
        max_distance = math.sqrt((differences * differences).sum(axis=1).max())
        if max_distance > diameter:
            diameter = max_distance
    return diameter
