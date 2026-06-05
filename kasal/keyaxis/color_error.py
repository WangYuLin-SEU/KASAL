# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

import numpy as np 
from scipy import spatial

def rot_axis_color_error(pts, colors, mat,):
    ''' Use KDTree to find the nearest point pairs before and after  
        rotation around the axis, then compute the average distance  
        and color errors.  
    Parameters:  
        pts: Vertex coordinates of the object.  
        colors: Vertex colors of the object.  
        mat: Transformation matrix containing rotation and translation.  
    Returns:  
        distance_error: Distance error.  
        color_error: Color error.  
    '''
    ply_pts_m = np.dot(pts, mat[:3,:3])+mat[:3,3]
    nn_index = spatial.cKDTree(pts)
    d1, t1_index = nn_index.query(ply_pts_m, k=1)
    dc_ = colors - colors[t1_index, :]
    ndc_ = np.linalg.norm(dc_, axis=1)
    color_error = np.mean(ndc_)
    distance_error = np.mean(d1)
    return distance_error, color_error
