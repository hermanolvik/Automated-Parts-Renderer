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

import bpy
import os
from mathutils import Vector
import math

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


def setup_white_background_compositor():
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree

    # Clear existing nodes
    for node in tree.nodes:
        tree.nodes.remove(node)

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


class RENDER_OT_automated_object_renderer(bpy.types.Operator):
    bl_idname = "render.automated_object_renderer"
    bl_label = "Render Selected Objects"
    bl_description = "Render selected objects individually"

    def execute(self, context):
        scene = context.scene
        render_settings = scene.automated_object_renderer
        original_camera = scene.camera
        original_film_transparent = scene.render.film_transparent
        world = scene.world
        original_use_nodes = world.use_nodes
        if world.node_tree:
            original_node_tree = world.node_tree.copy()
        else:
            original_node_tree = None

        camera = bpy.data.cameras.new("TempCamera")
        camera_obj = bpy.data.objects.new("TempCamera", camera)
        bpy.context.collection.objects.link(camera_obj)
        scene.camera = camera_obj

        original_output_path = scene.render.filepath
        original_resolution_x = scene.render.resolution_x
        original_resolution_y = scene.render.resolution_y
        original_percentage = scene.render.resolution_percentage

        selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

        # Progress bar
        wm = context.window_manager
        total_steps = len(selected_objects) * render_settings.rotation_steps
        wm.progress_begin(0, total_steps)
        current_step = 0

        # Main rendering loop
        for obj in selected_objects:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='BOUNDS')

            obj.hide_render = False
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)

            output_dir = bpy.path.abspath(render_settings.output_directory)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            file_name = obj.name + "_{step}"
            scene.render.filepath = os.path.join(output_dir, file_name)
            scene.render.image_settings.file_format = render_settings.file_format
            scene.render.resolution_x = render_settings.resolution_x
            scene.render.resolution_y = render_settings.resolution_y
            scene.render.resolution_percentage = render_settings.resolution_percentage

            for other_obj in bpy.context.visible_objects:
                if other_obj != obj and other_obj.type == 'MESH':
                    other_obj.hide_render = True

            # Setting the camera angle by giving it a specific position before focusing the object
            camera_obj.location = (74.82, -65.07, 53.43)
            focus_camera_on_object(obj, camera_obj, render_settings.zoom_factor)

            original_use_scene_nodes = scene.use_nodes

            if render_settings.background_option == "WHITE":
                scene.render.film_transparent = True
                setup_white_background_compositor()

            elif render_settings.background_option == "TRANSPARENT":
                scene.render.film_transparent = True

            # Save original rotation
            original_rotation = obj.rotation_euler.copy()

            # Perform rotation and render for each step
            for step in range(render_settings.rotation_steps):
                obj.rotation_euler.z += 2 * math.pi / render_settings.rotation_steps
                scene.render.filepath = os.path.join(output_dir, file_name.format(step=step))
                bpy.ops.render.render(write_still=True) # Image render happens here

                # Update the progress bar
                current_step += 1
                wm.progress_update(current_step)

                # Calculate and print percentage to the console
                percentage = (current_step / total_steps) * 100
                print(f"Rendering progress: {percentage:.2f}%")

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

        # End progress bar
        wm.progress_end()

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

        layout.operator(RENDER_OT_automated_object_renderer.bl_idname)
        layout.prop(render_settings, "output_directory")
        layout.prop(render_settings, "file_format")
        layout.prop(render_settings, "resolution_x")
        layout.prop(render_settings, "resolution_y")
        layout.prop(render_settings, "resolution_percentage")
        layout.prop(render_settings, "zoom_factor")
        layout.prop(render_settings, "background_option")
        layout.prop(render_settings, "rotation_steps")

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
            ("WHITE", "White", "Render with a white background"),
            ("TRANSPARENT", "Transparent", "Render with a transparent background"),
        ],
        default="WHITE",
    )
    rotation_steps: bpy.props.IntProperty(
        name="Rotation Steps",
        description="Number of rotation steps for each object",
        default=5,
        min=1,
        max=360
    )

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