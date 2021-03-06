from bpy.props import PointerProperty, IntProperty, CollectionProperty

from ...rman_utils import filepath_utils
from ...rman_utils import property_utils
from ...rfb_logger import rfb_log 
from ...rman_config import RmanBasePropertyGroup
from ..rman_properties_misc import RendermanMeshPrimVar 

import bpy

class RendermanMeshGeometrySettings(RmanBasePropertyGroup, bpy.types.PropertyGroup):
    prim_vars: CollectionProperty(
        type=RendermanMeshPrimVar, name="Primitive Variables")
    prim_vars_index: IntProperty(min=-1, default=-1)

classes = [         
    RendermanMeshGeometrySettings
]           

def register():

    for cls in classes:
        cls._add_properties(cls, 'rman_properties_mesh')
        bpy.utils.register_class(cls)  

    bpy.types.Mesh.renderman = PointerProperty(
        type=RendermanMeshGeometrySettings,
        name="Renderman Mesh Geometry Settings")

def unregister():

    for cls in classes:
        bpy.utils.unregister_class(cls)