bl_info = {
    "name": "Image Selector",
    "author": "Parttrap",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "Image Editor > Select Best Object Image",
    "description": "Select the best image of each object and delete the rest",
    "warning": "",
    "doc_url": "",
    "category": "Image",
}

import bpy
import os
import shutil
from bpy.props import StringProperty
from bpy.types import Operator, Panel

class OBJECT_OT_select_best_image(Operator):
    bl_idname = "object.select_best_image"
    bl_label = "Select Best Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        directory = context.scene.select_best_image_directory

        if not os.path.exists(directory):
            self.report({'ERROR'}, "Invalid directory path")
            return {'CANCELLED'}

        image_files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.tiff'))]

        for image in image_files:
            img_path = os.path.join(directory, image)
            bpy.ops.image.open(filepath=img_path)

        return {'FINISHED'}

class OBJECT_OT_next_image(Operator):
    bl_idname = "object.next_image"
    bl_label = "Next Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        images = bpy.data.images
        if len(images) > 0:
            current_image = context.space_data.image
            if current_image:
                object_name = current_image.name.split('_')[0]
                object_images = [img for img in images if img.name.startswith(object_name + "_")]

                index = object_images.index(current_image)
                index = (index + 1) % len(object_images)
                context.space_data.image = object_images[index]

        return {'FINISHED'}

class OBJECT_OT_previous_image(Operator):
    bl_idname = "object.previous_image"
    bl_label = "Previous Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        images = bpy.data.images
        if len(images) > 0:
            current_image = context.space_data.image
            if current_image:
                object_name = current_image.name.split('_')[0]
                object_images = [img for img in images if img.name.startswith(object_name + "_")]

                index = object_images.index(current_image)
                index = (index - 1) % len(object_images)
                context.space_data.image = object_images[index]

        return {'FINISHED'}

class OBJECT_OT_next_object(Operator):
    bl_idname = "object.next_object"
    bl_label = "Next Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        images = bpy.data.images
        if len(images) > 0:
            current_image = context.space_data.image
            if current_image:
                object_names = sorted(set(img.name.split('_')[0] for img in images))
                current_object_name = current_image.name.split('_')[0]

                index = object_names.index(current_object_name)
                index = (index + 1) % len(object_names)
                next_object_name = object_names[index]

                next_object_images = [img for img in images if img.name.startswith(next_object_name + "_")]

                if next_object_images:
                    context.space_data.image = next_object_images[0]

        return {'FINISHED'}

class OBJECT_OT_previous_object(Operator):
    bl_idname = "object.previous_object"
    bl_label = "Previous Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        images = bpy.data.images
        if len(images) > 0:
            current_image = context.space_data.image
            if current_image:
                object_names = sorted(set(img.name.split('_')[0] for img in images))
                current_object_name = current_image.name.split('_')[0]

                index = object_names.index(current_object_name)
                index = (index - 1) % len(object_names)
                prev_object_name = object_names[index]

                prev_object_images = [img for img in images if img.name.startswith(prev_object_name + "_")]

                if prev_object_images:
                    context.space_data.image = prev_object_images[0]

        return {'FINISHED'}

class OBJECT_OT_pick_this_image(Operator):
    bl_idname = "object.pick_this_image"
    bl_label = "Pick This Image"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        current_image = context.space_data.image
        if not current_image:
            self.report({'ERROR'}, "No image selected")
            return {'CANCELLED'}

        directory = context.scene.select_best_image_directory
        omitted_directory = os.path.join(directory, "Omitted")
        os.makedirs(omitted_directory, exist_ok=True)

        object_name = current_image.name.split('_')[0]

        image_files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.tiff'))]

        for image in image_files:
            if image.startswith(object_name + "_"):
                img_path = os.path.join(directory, image)
                if image != current_image.name:
                    shutil.move(img_path, os.path.join(omitted_directory, image))
                    bpy.data.images.remove(bpy.data.images[image])
                else:
                    new_img_path = os.path.join(directory, object_name + os.path.splitext(image)[1])
                    os.rename(img_path, new_img_path)

        return {'FINISHED'}

class IMAGE_PT_select_best_image(Panel):
    bl_label = "Select Best Object Image"
    bl_idname = "IMAGE_PT_select_best_image"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Select Best"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.select_best_image", text="Open Images Folder")
        col.prop(context.scene, "select_best_image_directory", text="Image Folder")
        col.separator()

        current_image = context.space_data.image
        if current_image:
            object_name = current_image.name.split('_')[0]
            col.label(text=f"Current object: {object_name}")
        else:
            col.label(text="No image selected")

        row = col.row(align=True)
        row.operator("object.previous_object", text="Previous Object")
        row.operator("object.next_object", text="Next Object")
        col.separator()
        if current_image:
            image_suffix = current_image.name.split('_')[1].split('.')[0]
            col.label(text=f"Image number: {image_suffix}")
        row = col.row(align=True)
        row.operator("object.previous_image", text="Previous Image")
        row.operator("object.next_image", text="Next Image")
        col.separator()
        col.operator("object.pick_this_image", text="Pick This Image")

def register():
    bpy.utils.register_class(OBJECT_OT_select_best_image)
    bpy.utils.register_class(OBJECT_OT_next_image)
    bpy.utils.register_class(OBJECT_OT_previous_image)
    bpy.utils.register_class(OBJECT_OT_pick_this_image)
    bpy.utils.register_class(OBJECT_OT_next_object)
    bpy.utils.register_class(OBJECT_OT_previous_object)
    bpy.utils.register_class(IMAGE_PT_select_best_image)
    bpy.types.Scene.select_best_image_directory = StringProperty(default="", subtype='DIR_PATH')

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_select_best_image)
    bpy.utils.unregister_class(OBJECT_OT_next_image)
    bpy.utils.unregister_class(OBJECT_OT_previous_image)
    bpy.utils.unregister_class(OBJECT_OT_pick_this_image)
    bpy.utils.unregister_class(OBJECT_OT_next_object)
    bpy.utils.unregister_class(OBJECT_OT_previous_object)
    bpy.utils.unregister_class(IMAGE_PT_select_best_image)
    del bpy.types.Scene.select_best_image_directory

if __name__ == "__main__":
    register()
