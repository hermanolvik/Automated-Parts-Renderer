bl_info = {
    "name": "Automated Parts Images",
    "author": "Parttrap",
    "version": (1, 0),
    "blender": (2, 83, 0),
    "location": "Properties > Render",
    "description": "Render selected objects individually and select the best image",
    "warning": "",
    "wiki_url": "",
    "category": "Render",
}

import bpy

from . import automated_parts_renderer
from . import image_selector

def register():
    automated_parts_renderer.register()
    image_selector.register()

def unregister():
    automated_parts_renderer.unregister()
    image_selector.unregister()

if __name__ == "__main__":
    register()