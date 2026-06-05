# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

import numpy as np

def rotate_translate(axis, theta, t):
    """ Compute the transformation matrix based on the direction  
        of the symmetry/key axis, rotation angle, and translation component.  
    Parameters:  
        axis: Direction vector of the symmetry/key axis.  
        theta: Rotation angle.  
        t: Translation vector.  
    Returns:  
        M: Transformation matrix containing rotation and translation.  
    """

    theta = np.deg2rad(theta)
    axis = np.asarray(axis)
    axis /= np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]],
                [axis[2], 0, -axis[0]],
                [-axis[1], axis[0], 0]])
    R = np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * np.dot(K, K)
    M = np.eye(4)
    M[:3, :3] = R
    t_ = np.dot(R, t.reshape((3)), )
    dt_ = t - t_ 
    M[:3, 3] = dt_
    return M

