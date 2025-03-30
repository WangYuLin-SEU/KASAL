# Author: Yulin Wang (yulinwang@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China

import sys, os

kasal_dir = os.path.dirname(os.path.abspath(__file__))  # 这个文件所在的目录，即 KASAL/datasets

kasal_dir = os.path.dirname(kasal_dir)

arrow_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'arrow.ply')

arrow_xyz_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'arrow_xyz.ply')

icon_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'K4.ico')

shape_mesh_path =  os.path.join(os.path.join(kasal_dir, 'datasets'), "shape_meshes")

texture_mesh_path = os.path.join(os.path.join(kasal_dir, 'datasets'), 'texture_meshes')
