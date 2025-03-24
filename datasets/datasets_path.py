# Author: Yulin Wang (yulinwang@seu.edu.cn)
# School of Mechanical Engineering, Southeast University, China

import sys, os

sys.path.insert(0, os.getcwd())
current_directory = sys.argv[0]

arrow_path = os.path.join(os.path.join(os.path.dirname(current_directory), 'datasets'), 'arrow.ply')

arrow_xyz_path = os.path.join(os.path.join(os.path.dirname(current_directory), 'datasets'), 'arrow_xyz.ply')

icon_path = os.path.join(os.path.join(os.path.dirname(current_directory), 'datasets'), 'K4.ico')

shape_mesh_path = os.path.join(os.path.join(os.path.dirname(current_directory), 'datasets'), 'shape_meshes')

texture_mesh_path = os.path.join(os.path.join(os.path.dirname(current_directory), 'datasets'), 'texture_meshes')