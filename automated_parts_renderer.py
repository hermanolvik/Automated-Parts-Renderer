bl_info = {
    "name": "Automated Parts Renderer",
    "author": "Parttrap",
    "version": (1, 0),
    "blender": (2, 83, 0),
    "location": "Properties > Render",
    "description": "Render selected objects individually",
    "warning": "",
    "wiki_url": "",
    "category": "Render",
}


import math
import os
import bpy
from mathutils import Vector
import re

# Focus camera on object based on zoom factor
def focus_camera_on_object(obj, camera, zoom_factor):
    max_dim = max(obj.dimensions)
    distance = max_dim / (2.0 * (3.14159 / 180.0) * camera.data.angle)

    distance *= zoom_factor

    bbox_center = 0.125 * sum((Vector(b) for b in obj.bound_box), Vector())
    global_center = obj.matrix_world @ bbox_center

    direction = camera.location - global_center
    direction.normalize()
    camera.location = global_center + distance * direction
    camera.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = obj
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'


# The main rendering function
def render_images(obj, camera_obj, render_settings, views, progress_info):
    original_rotation = obj.rotation_euler.copy()

    # Render from selected views
    if (views["isometric"]):
        camera_obj.location = (74.82, -65.07, 53.43)
        focus_camera_on_object(obj, camera_obj, render_settings.zoom_factor)
        views["current_view"] = "iso"
        render_images_from_current_view(render_settings, obj, progress_info, views)
    if (views["side_view"]):
        camera_obj.location = (obj.location.x + 100, obj.location.y, obj.location.z)
        focus_camera_on_object(obj, camera_obj, render_settings.zoom_factor)
        views["current_view"] = "side"
        render_images_from_current_view(render_settings, obj, progress_info, views)
    if (views["top_view"]):
        camera_obj.location = (obj.location.x, obj.location.y, obj.location.z + 100)
        focus_camera_on_object(obj, camera_obj, render_settings.zoom_factor)
        views["current_view"] = "top"
        render_images_from_current_view(render_settings, obj, progress_info, views)
    
    # Restore original object rotation
    obj.rotation_euler = original_rotation


# Perform rotations and render for each angle
def render_images_from_current_view(render_settings, obj, progress_info, views):
    scene = bpy.context.scene
    output_dir = bpy.path.abspath(render_settings.output_directory)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    file_name = obj.name + views["current_view"] + "_{step}"

    for step in range(render_settings.rotation_steps):
        obj.rotation_euler.z += 2 * math.pi / render_settings.rotation_steps
        scene.render.filepath = os.path.join(output_dir, file_name.format(step=step))
        
        # Render image
        bpy.ops.render.render(write_still=True)

        # Update the progress bar
        progress_info["current_image_number"] += 1
        progress_info["wm"].progress_update(progress_info["current_image_number"])

        # Calculate and print percentage to the console
        percentage = (progress_info["current_image_number"] / progress_info["total_image_quantity"]) * 100
        print(f"Rendering progress: {percentage:.2f}%")


# Restore the world material
def restore_original_node_tree(world, original_node_tree):
    if not original_node_tree:
        return

    world.node_tree.nodes.clear()

    # Reconstruct the original node tree
    for original_node in original_node_tree.nodes:
        node = world.node_tree.nodes.new(original_node.bl_idname)
        node.location = original_node.location

        for i, input_socket in enumerate(original_node.inputs):
            if hasattr(input_socket, "default_value"):
                if isinstance(input_socket.default_value, float):
                    node.inputs[i].default_value = input_socket.default_value
                else:
                    node.inputs[i].default_value = input_socket.default_value[:]

        if original_node.bl_idname == "ShaderNodeTexEnvironment":
            node.image = original_node.image

    # Reconnect nodes
    for original_node in original_node_tree.nodes:
        node = world.node_tree.nodes[original_node.name]

        for output_socket in original_node.outputs:
            for original_link in output_socket.links:
                from_socket = node.outputs[original_link.from_socket.name]
                to_socket = world.node_tree.nodes[original_link.to_node.name].inputs[original_link.to_socket.name]
                world.node_tree.links.new(from_socket, to_socket)


# Apply white render background
def setup_white_background_compositor():
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree

    # Clear existing nodes
    for node in tree.nodes:
        tree.nodes.remove(node)

    # Set color management to Raw for pure white background
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'

    # Create nodes for white background compositor
    render_layers_node = tree.nodes.new('CompositorNodeRLayers')
    render_layers_node.location = 0, 300

    alpha_over_node = tree.nodes.new('CompositorNodeAlphaOver')
    alpha_over_node.location = 200, 300
    alpha_over_node.inputs[1].default_value = (1, 1, 1, 1)
    alpha_over_node.use_premultiply = True

    composite_node = tree.nodes.new('CompositorNodeComposite')
    composite_node.location = 400, 300

    # Connect nodes
    tree.links.new(render_layers_node.outputs[0], alpha_over_node.inputs[2])
    tree.links.new(alpha_over_node.outputs[0], composite_node.inputs[0])


# Apply transparent render background
def setup_transparent_background_compositor():
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree

    # Clear existing nodes
    for node in tree.nodes:
        tree.nodes.remove(node)

    # Create nodes for transparent background compositor
    render_layers_node = tree.nodes.new('CompositorNodeRLayers')
    render_layers_node.location = 0, 300

    composite_node = tree.nodes.new('CompositorNodeComposite')
    composite_node.location = 200, 300

    # Connect nodes
    tree.links.new(render_layers_node.outputs[0], composite_node.inputs[0])


def strip_number_suffix(name):
    # The regular expression pattern for ".xxx" where x's are digits
    pattern = r"\.\d+$"
    
    # Remove suffix
    stripped_name = re.sub(pattern, "", name)

    return stripped_name


# An operator for rendering images
class RENDER_OT_automated_object_renderer(bpy.types.Operator):
    bl_idname = "render.automated_object_renderer"
    bl_label = "Render Selected Objects"
    bl_description = "Render selected objects individually"

    def execute(self, context):
        scene = context.scene
        
        # Import settings from GUI
        render_settings = scene.automated_object_renderer
        
        # Store original assets
        original_camera = scene.camera
        original_film_transparent = scene.render.film_transparent
        world = scene.world
        original_use_nodes = world.use_nodes
        if world.node_tree:
            original_node_tree = world.node_tree.copy()
        else:
            original_node_tree = None

        # Create a temporary camera
        camera = bpy.data.cameras.new("TempCamera")
        camera_obj = bpy.data.objects.new("TempCamera", camera)
        bpy.context.collection.objects.link(camera_obj)
        scene.camera = camera_obj

        # Store original render settings
        original_output_path = scene.render.filepath
        original_resolution_x = scene.render.resolution_x
        original_resolution_y = scene.render.resolution_y
        original_percentage = scene.render.resolution_percentage

        # Store information about selected views
        views = {}
        views["isometric"] = render_settings.isometric_view
        views["side_view"] = render_settings.side_view
        views["top_view"] = render_settings.top_view
        views["current_view"] = ""
        
        # Create the list of objects to be rendered
        duplicate_filter = render_settings.duplicate_filter
        render_objects = [] 

        # Filter duplicate objects
        names_set = set()
        unique_meshes = []
        render_objects = []
        for obj in bpy.context.selected_objects:
            if obj.type == 'MESH':
                if (duplicate_filter == "NAME_SUFFIX"):
                    stripped_name = strip_number_suffix(obj.name)
                    if stripped_name not in names_set:
                        names_set.add(stripped_name)
                        render_objects.append(obj)
                elif (duplicate_filter == "MESH_DATA"):
                    if obj.data not in unique_meshes:
                        unique_meshes.append(obj.data)
                        render_objects.append(obj)
                elif (duplicate_filter == "NAME_SUFFIX_+_MESH_DATA"):
                    stripped_name = strip_number_suffix(obj.name)
                    if stripped_name not in names_set and obj.data not in unique_meshes:
                        names_set.add(stripped_name)
                        unique_meshes.append(obj.data)
                        render_objects.append(obj)
                else:
                    render_objects = [obj for obj in context.selected_objects if obj.type == 'MESH']

        # Progress bar setup
        progress_info = {}
        progress_info["wm"] = context.window_manager
        progress_info["total_image_quantity"] = len(render_objects) * render_settings.rotation_steps * sum([views["isometric"], views["side_view"], views["top_view"]])
        progress_info["current_image_number"] = 0
        
        progress_info["wm"].progress_begin(0, progress_info["total_image_quantity"])

        # Store original nodes and configure compositor
        original_use_scene_nodes = scene.use_nodes

        # Store the original color management settings
        original_view_transform = scene.view_settings.view_transform
        original_look = scene.view_settings.look

        scene.render.film_transparent = True
        if render_settings.background_option == "WHITE":
            setup_white_background_compositor()

        elif render_settings.background_option == "TRANSPARENT":
            setup_transparent_background_compositor()

        # Set render settings
        scene.render.image_settings.file_format = render_settings.file_format
        scene.render.resolution_x = render_settings.resolution_x
        scene.render.resolution_y = render_settings.resolution_y
        scene.render.resolution_percentage = render_settings.resolution_percentage

        # Main rendering loop
        for obj in render_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='BOUNDS')

            # Show current object and hide other mesh objects
            obj.hide_render = False
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            for other_obj in bpy.context.visible_objects:
                if other_obj != obj and other_obj.type == 'MESH':
                    other_obj.hide_render = True

            # Store original rotation
            original_rotation = obj.rotation_euler.copy()

            # Render images
            render_images(obj, camera_obj, render_settings, views, progress_info)
            
            # Restore original rotation
            obj.rotation_euler = original_rotation

            obj.hide_render = True
            for other_obj in bpy.context.visible_objects:
                if other_obj != obj and other_obj.type == 'MESH':
                    other_obj.hide_render = False

        scene.render.filepath = original_output_path
        scene.render.resolution_x = original_resolution_x
        scene.render.resolution_y = original_resolution_y
        scene.render.resolution_percentage = original_percentage

        bpy.data.objects.remove(camera_obj)
        bpy.data.cameras.remove(camera)
        scene.camera = original_camera

        scene.use_nodes = original_use_scene_nodes

        scene.render.film_transparent = original_film_transparent
        world.use_nodes = original_use_nodes

        restore_original_node_tree(world, original_node_tree)

        # Revert color management settings
        scene.view_settings.view_transform = original_view_transform
        scene.view_settings.look = original_look

        # End progress bar
        progress_info["wm"].progress_end()

        return {'FINISHED'}


class RENDER_PT_automated_object_renderer_panel(bpy.types.Panel):
    bl_label = "Automated Parts Renderer"
    bl_idname = "RENDER_PT_automated_object_renderer"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        render_settings = context.scene.automated_object_renderer

        layout.prop(render_settings, "output_directory")
        layout.prop(render_settings, "file_format")
        layout.prop(render_settings, "resolution_x")
        layout.prop(render_settings, "resolution_y")
        layout.prop(render_settings, "resolution_percentage")
        layout.prop(render_settings, "zoom_factor")
        layout.prop(render_settings, "background_option")
        layout.prop(render_settings, "isometric_view")
        layout.prop(render_settings, "side_view")
        layout.prop(render_settings, "top_view")
        layout.prop(render_settings, "rotation_steps")
        layout.prop(render_settings, "duplicate_filter")
        layout.operator(RENDER_OT_automated_object_renderer.bl_idname)


class AutomatedObjectRendererSettings(bpy.types.PropertyGroup):
    output_directory: bpy.props.StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        default="C:/",
    )
    file_format: bpy.props.EnumProperty(
        name="File Format",
        items=[
            ('PNG', "PNG", ""),
            ('JPEG', "JPEG", ""),
            ('TIFF', "TIFF", ""),
        ],
        default='PNG',
    )
    zoom_factor: bpy.props.FloatProperty(
        name="Zoom Factor",
        description="Adjust the zoom factor for the camera when rendering objects",
        default=0.1,
        min=0.01,
        max=0.3
    )
    background_option: bpy.props.EnumProperty(
        name="Background",
        description="Choose the background option for rendering",
        items=[
            ("WHITE", "White", "Render with a solid white background"),
            ("TRANSPARENT", "Transparent", "Render with a transparent background"),
        ],
        default="TRANSPARENT",
    )
    duplicate_filter: bpy.props.EnumProperty(
        name="Duplicate Filter(s)",
        description="Filtering method to exclude duplicate objects from rendering",
        items=[
            ("NAME_SUFFIX_+_MESH_DATA", "Name Suffix + Mesh Data", "Filter duplicates using name suffix and mesh data filters"),
            ("NAME_SUFFIX", "Name Suffix", "Filter duplicates using name suffix filter"),
            ("MESH_DATA", "Mesh Data", "Filter duplicates using mesh data filter"),
            ("NONE", "None", "No duplicate filtering"),
        ],
        default="NAME_SUFFIX",
    )
    rotation_steps: bpy.props.IntProperty(
        name="Rotation Steps",
        description="Number of rotation steps for each object",
        default=1,
        min=1,
        max=360
    )
    
    isometric_view: bpy.props.BoolProperty(name="Isometric View", description="Render images from an isometric viewpoint", default=True)
    side_view: bpy.props.BoolProperty(name="Side View", description="Render images from a side view", default=True)
    top_view: bpy.props.BoolProperty(name="Top View", description="Render images from a top view", default=True)

    resolution_x: bpy.props.IntProperty(name="Resolution X", default=1000, min=1)
    resolution_y: bpy.props.IntProperty(name="Resolution Y", default=1000, min=1)
    resolution_percentage: bpy.props.IntProperty(name="Percentage", default=100, min=1, max=100, subtype='PERCENTAGE')


def register():
    bpy.utils.register_class(AutomatedObjectRendererSettings)
    bpy.types.Scene.automated_object_renderer = bpy.props.PointerProperty(type=AutomatedObjectRendererSettings)
    bpy.utils.register_class(RENDER_OT_automated_object_renderer)
    bpy.utils.register_class(RENDER_PT_automated_object_renderer_panel)


def unregister():
    bpy.utils.unregister_class(AutomatedObjectRendererSettings)
    del bpy.types.Scene.automated_object_renderer
    bpy.utils.unregister_class(RENDER_OT_automated_object_renderer)
    bpy.utils.unregister_class(RENDER_PT_automated_object_renderer_panel)


if __name__ == "__main__":
    register()
