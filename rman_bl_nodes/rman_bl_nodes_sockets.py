import bpy
from bpy.props import *

group_nodes = ['ShaderNodeGroup', 'NodeGroupInput', 'NodeGroupOutput']
# Default Types

# update node during ipr for a socket default_value


def update_func(self, context):
    # check if this prop is set on an input
    node = self.node if hasattr(self, 'node') else self

# socket name corresponds to the param on the node


class RendermanSocket:
    ui_open: BoolProperty(name='UI Open', default=True)

    def get_pretty_name(self, node):
        if node.bl_idname in group_nodes:
            return self.name
        else:
            return self.identifier

    def get_value(self, node):
        if node.bl_idname in group_nodes or not hasattr(node, self.name):
            return self.default_value
        else:
            return getattr(node, self.name)

    def draw_color(self, context, node):
        return (0.25, 1.0, 0.25, 1.0)

    def draw_value(self, context, layout, node):
        layout.prop(node, self.identifier)

    def draw(self, context, layout, node, text):
        if self.is_linked or self.is_output or self.hide_value or not hasattr(self, 'default_value'):
            layout.label(text=self.get_pretty_name(node))
        elif node.bl_idname in group_nodes or node.bl_idname == "PxrOSLPatternNode":
            layout.prop(self, 'default_value',
                        text=self.get_pretty_name(node), slider=True)
        else:
            layout.prop(node, self.name,
                        text=self.get_pretty_name(node), slider=True)


class RendermanSocketInterface:

    def draw_color(self, context):
        return (0.25, 1.0, 0.25, 1.0)

    def draw(self, context, layout):
        layout.label(text=self.name)

    def from_socket(self, node, socket):
        if hasattr(self, 'default_value'):
            self.default_value = socket.get_value(node)
        self.name = socket.name

    def init_socket(self, node, socket, data_path):
        sleep(.01)
        socket.name = self.name
        if hasattr(self, 'default_value'):
            socket.default_value = self.default_value


# socket types (need this just for the ui_open)
class RendermanNodeSocketFloat(bpy.types.NodeSocketFloat, RendermanSocket):
    '''RenderMan float input/output'''
    bl_idname = 'RendermanNodeSocketFloat'
    bl_label = 'RenderMan Float Socket'

    default_value: FloatProperty(update=update_func)
    renderman_type: StringProperty(default='float')

    def draw_color(self, context, node):
        return (0.5, 0.5, 0.5, 1.0)


class RendermanNodeSocketInterfaceFloat(bpy.types.NodeSocketInterfaceFloat, RendermanSocketInterface):
    '''RenderMan float input/output'''
    bl_idname = 'RendermanNodeSocketInterfaceFloat'
    bl_label = 'RenderMan Float Socket'
    bl_socket_idname = 'RendermanNodeSocketFloat'

    default_value: FloatProperty()

    def draw_color(self, context):
        return (0.5, 0.5, 0.5, 1.0)


class RendermanNodeSocketInt(bpy.types.NodeSocketInt, RendermanSocket):
    '''RenderMan int input/output'''
    bl_idname = 'RendermanNodeSocketInt'
    bl_label = 'RenderMan Int Socket'

    default_value: IntProperty(update=update_func)
    renderman_type: StringProperty(default='int')

    def draw_color(self, context, node):
        return (1.0, 1.0, 1.0, 1.0)


class RendermanNodeSocketInterfaceInt(bpy.types.NodeSocketInterfaceInt, RendermanSocketInterface):
    '''RenderMan float input/output'''
    bl_idname = 'RendermanNodeSocketInterfaceInt'
    bl_label = 'RenderMan Int Socket'
    bl_socket_idname = 'RendermanNodeSocketInt'

    default_value: IntProperty()

    def draw_color(self, context):
        return (1.0, 1.0, 1.0, 1.0)


class RendermanNodeSocketString(bpy.types.NodeSocketString, RendermanSocket):
    '''RenderMan string input/output'''
    bl_idname = 'RendermanNodeSocketString'
    bl_label = 'RenderMan String Socket'
    default_value: StringProperty(update=update_func)
    is_texture: BoolProperty(default=False)
    renderman_type: StringProperty(default='string')


class RendermanNodeSocketStruct(bpy.types.NodeSocketString, RendermanSocket):
    '''RenderMan struct input/output'''
    bl_idname = 'RendermanNodeSocketStruct'
    bl_label = 'RenderMan Struct Socket'
    hide_value = True
    renderman_type = 'string'
    default_value = ''


class RendermanNodeSocketInterfaceStruct(bpy.types.NodeSocketInterfaceString, RendermanSocketInterface):
    '''RenderMan struct input/output'''
    bl_idname = 'RendermanNodeSocketInterfaceStruct'
    bl_label = 'RenderMan Struct Socket'
    bl_socket_idname = 'RendermanNodeSocketStruct'
    hide_value = True


class RendermanNodeSocketColor(bpy.types.NodeSocketColor, RendermanSocket):
    '''RenderMan color input/output'''
    bl_idname = 'RendermanNodeSocketColor'
    bl_label = 'RenderMan Color Socket'

    default_value: FloatVectorProperty(size=3,
                                        subtype="COLOR", update=update_func)
    renderman_type: StringProperty(default='color')

    def draw_color(self, context, node):
        return (1.0, 1.0, .5, 1.0)


class RendermanNodeSocketInterfaceColor(bpy.types.NodeSocketInterfaceColor, RendermanSocketInterface):
    '''RenderMan color input/output'''
    bl_idname = 'RendermanNodeSocketInterfaceColor'
    bl_label = 'RenderMan Color Socket'
    bl_socket_idname = 'RendermanNodeSocketColor'

    default_value: FloatVectorProperty(size=3,
                                        subtype="COLOR")

    def draw_color(self, context):
        return (1.0, 1.0, .5, 1.0)


class RendermanNodeSocketVector(RendermanSocket, bpy.types.NodeSocketVector):
    '''RenderMan vector input/output'''
    bl_idname = 'RendermanNodeSocketVector'
    bl_label = 'RenderMan Vector Socket'
    hide_value = True

    default_value: FloatVectorProperty(size=3,
                                        subtype="EULER", update=update_func)
    renderman_type: StringProperty(default='vector')

    def draw_color(self, context, node):
        return (.25, .25, .75, 1.0)


class RendermanNodeSocketInterfaceVector(bpy.types.NodeSocketInterfaceVector, RendermanSocketInterface):
    '''RenderMan color input/output'''
    bl_idname = 'RendermanNodeSocketInterfaceVector'
    bl_label = 'RenderMan Vector Socket'
    bl_socket_idname = 'RendermanNodeSocketVector'
    hide_value = True

    default_value: FloatVectorProperty(size=3,
                                        subtype="EULER")

    def draw_color(self, context):
        return (.25, .25, .75, 1.0)

# Custom socket type for connecting shaders


class RendermanShaderSocket(bpy.types.NodeSocketShader, RendermanSocket):
    '''RenderMan shader input/output'''
    bl_idname = 'RendermanShaderSocket'
    bl_label = 'RenderMan Shader Socket'
    hide_value = True

# Custom socket type for connecting shaders


class RendermanShaderSocketInterface(bpy.types.NodeSocketInterfaceShader, RendermanSocketInterface):
    '''RenderMan shader input/output'''
    bl_idname = 'RendermanShaderInterfaceSocket'
    bl_label = 'RenderMan Shader Socket'
    bl_socket_idname = 'RendermanShaderSocket'
    hide_value = True

classes = [
    RendermanShaderSocket,
    RendermanNodeSocketColor,
    RendermanNodeSocketFloat,
    RendermanNodeSocketInt,
    RendermanNodeSocketString,
    RendermanNodeSocketVector,
    RendermanNodeSocketStruct,

    RendermanNodeSocketInterfaceFloat,
    RendermanNodeSocketInterfaceInt,
    RendermanNodeSocketInterfaceStruct,
    RendermanNodeSocketInterfaceColor,
    RendermanNodeSocketInterfaceVector,
    RendermanShaderSocketInterface
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)    