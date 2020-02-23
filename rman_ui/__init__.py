from . import rman_ui_txmanager
from . import rman_ui_aovs
from . import rman_ui_viewport
from . import rman_ui_light_handlers
from . import rman_ui_render_panels
from . import rman_ui_object_panels
from . import rman_ui_mesh_panels

def register():
    rman_ui_txmanager.register()
    rman_ui_aovs.register()
    rman_ui_viewport.register()
    rman_ui_light_handlers.register()
    rman_ui_render_panels.register()
    rman_ui_object_panels.register()
    rman_ui_mesh_panels.register()

def unregister():
    rman_ui_txmanager.unregister()
    rman_ui_aovs.unregister()
    rman_ui_viewport.unregister()
    rman_ui_light_handlers.unregister()
    rman_ui_render_panels.unregister()
    rman_ui_object_panels.unregister()
    rman_ui_mesh_panels.unregister()