# KASAL project & GitHub: Yulin Wang (王宇林, yulinwang@seu.edu.cn)
# KASAL 项目与 GitHub：王宇林 Yulin Wang (yulinwang@seu.edu.cn)
# KASALv2 algorithm: Mengxin Zhang (张梦欣, mx.zhang@seu.edu.cn)
# KASALv2 算法主要设计：张梦欣 Mengxin Zhang (mx.zhang@seu.edu.cn)
# Maintenance & pip packaging: Hu Mengting (胡梦婷, 220240361@seu.edu.cn)
# 维护与 pip 打包：胡梦婷 Hu Mengting (220240361@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China
# 东南大学机械工程学院

import sys, os

kasal_dir = os.path.dirname(os.path.abspath(__file__))  # 这个文件所在的目录，即 KASAL/datasets

kasal_dir = os.path.dirname(kasal_dir)

arrow_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'arrow.ply')

arrow_xyz_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'arrow_xyz.ply')

icon_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'K4.ico')

icon_png_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'K4.png')

shape_mesh_path =  os.path.join(os.path.join(kasal_dir, 'datasets'), "shape_meshes")

texture_mesh_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'texture_meshes')
