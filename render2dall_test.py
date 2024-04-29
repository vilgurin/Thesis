import argparse, sys, os, math, re
import bpy
from glob import glob
from mathutils import Vector 

parser = argparse.ArgumentParser(description='Renders given obj files in a directory by rotating a camera around them.')
parser.add_argument('--views', type=int, default=180,
                    help='number of views to be rendered')
parser.add_argument('obj_dir', type=str,
                    help='Directory containing the obj files to be rendered.')
parser.add_argument('--output_folder', type=str, default='/tmp',
                    help='The path the output will be dumped to.')
parser.add_argument('--scale', type=float, default=1,
                    help='Scaling factor applied to model. Depends on size of mesh.')
parser.add_argument('--remove_doubles', type=bool, default=True,
                    help='Remove double vertices to improve mesh quality.')
parser.add_argument('--edge_split', type=bool, default=True,
                    help='Adds edge split filter.')
parser.add_argument('--depth_scale', type=float, default=1.4,
                    help='Scaling that is applied to depth. Depends on size of mesh. Try out various values until you get a good result. Ignored if format is OPEN_EXR.')
parser.add_argument('--color_depth', type=str, default='8',
                    help='Number of bit per channel used for output. Either 8 or 16.')
parser.add_argument('--format', type=str, default='PNG',
                    help='Format of files generated. Either PNG or OPEN_EXR')
parser.add_argument('--resolution', type=int, default=600,
                    help='Resolution of the images.')
parser.add_argument('--engine', type=str, default='BLENDER_EEVEE',
                    help='Blender internal engine for rendering. E.g. CYCLES, BLENDER_EEVEE, ...')

argv = sys.argv[sys.argv.index("--") + 1:]
args = parser.parse_args(argv)

def setup_lighting():
    light_data = bpy.data.lights.new(name="New_Light", type='SUN')
    light_object = bpy.data.objects.new(name="New_Light", object_data=light_data)
    bpy.context.collection.objects.link(light_object)
    light_object.location = (10, 10, 10)
    light_data.energy = 1.0  

def cleanup_scene():
    bpy.ops.object.select_all(action='DESELECT')
    object_types = ['MESH', 'LIGHT', 'CAMERA']

    for object_type in object_types:
        for obj in bpy.context.scene.objects:
            if obj.type == object_type:
                obj.select_set(True)
        bpy.ops.object.delete()

    print("Scene cleanup completed.")

def setup_scene():
    context = bpy.context
    scene = context.scene
    render = scene.render
    if "Cube" in scene.objects:
        bpy.data.objects['Cube'].select_set(True)
        bpy.ops.object.delete()

    if "Light" in scene.objects:
        bpy.data.objects['Light'].select_set(True)
        bpy.ops.object.delete()

    render.engine = args.engine
    render.image_settings.color_mode = 'RGBA'  
    render.image_settings.color_depth = args.color_depth
    render.image_settings.file_format = args.format
    render.resolution_x = args.resolution
    render.resolution_y = args.resolution
    render.resolution_percentage = 100
    render.film_transparent = True


    scene.use_nodes = True
    scene.view_layers["View Layer"].use_pass_normal = True
    scene.view_layers["View Layer"].use_pass_diffuse_color = True
    scene.view_layers["View Layer"].use_pass_object_index = True

    nodes = scene.node_tree.nodes
    links = scene.node_tree.links
    for n in nodes:
        nodes.remove(n)

    render_layers = nodes.new('CompositorNodeRLayers')

    setup_lighting()

    print("Scene setup completed.")


def render_obj(obj_path):
   
    bpy.ops.import_scene.obj(filepath=obj_path)
    obj = bpy.context.selected_objects[0]  
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')


    if args.scale != 1:
        obj.scale = (args.scale, args.scale, args.scale)
    bpy.ops.object.transform_apply(scale=True)


    if args.remove_doubles:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.remove_doubles()
        bpy.ops.object.mode_set(mode='OBJECT')
    if args.edge_split:
        bpy.ops.object.modifier_add(type='EDGE_SPLIT')
        obj.modifiers["EdgeSplit"].split_angle = 1.32645
        bpy.ops.object.modifier_apply(modifier="EdgeSplit")

    obj.pass_index = 1

    update_camera_and_lighting(obj)

    model_identifier = os.path.splitext(os.path.basename(obj_path))[0]
    output_path = os.path.join(args.output_folder, model_identifier)

    for i in range(args.views):
        print(f"Rendering view {i + 1}/{args.views} for {model_identifier}")
        
        
        z_rotation_degrees = random.uniform(-15, 15)  

        z_rotation_radians = math.radians(z_rotation_degrees)
        
        cam_empty = bpy.data.objects.get("CameraEmpty")
        if cam_empty:
            original_rotation = cam_empty.rotation_euler[2]
            cam_empty.rotation_euler[0] = z_rotation_radians

        render_file_path = f"{output_path}_r_{i:03d}.png"
        bpy.context.scene.render.filepath = render_file_path
        
        bpy.ops.render.render(write_still=True)
        
        if cam_empty:
            cam_empty.rotation_euler[2] = original_rotation
        
        if cam_empty:
            cam_empty.rotation_euler[2] += math.radians(360 / args.views)




def update_camera_and_lighting(obj):
    scene = bpy.context.scene

    cam_empty = bpy.data.objects.get("CameraEmpty")
    if not cam_empty:
        cam_empty = bpy.data.objects.new("CameraEmpty", None)
        scene.collection.objects.link(cam_empty)

    
    cam = scene.camera
    if not cam:
       
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
    
    
    max_dimension = max(obj.dimensions)
    fov = cam.data.angle
    aspect_ratio = scene.render.resolution_x / scene.render.resolution_y
    if aspect_ratio > 1:
        
        fov = 2 * math.atan(math.tan(fov / 2) * aspect_ratio)
    distance = (max_dimension / 2.0) / math.tan(fov / 2.0)
    distance *= 1.1  

    
    obj_center = 0.125 * sum((Vector(b) for b in obj.bound_box), Vector())
    global_obj_center = obj.matrix_world @ obj_center
    cam_empty.location = global_obj_center
    cam.location = cam_empty.location + Vector((0, -distance, distance / 10))

    
    cam.parent = cam_empty  
    track_to = cam.constraints.new(type='TRACK_TO') if not cam.constraints.get("Track To") else cam.constraints["Track To"]
    track_to.target = cam_empty
    track_to.track_axis = 'TRACK_NEGATIVE_Z'
    track_to.up_axis = 'UP_Y'

    setup_lighting()

   


if __name__ == "__main__":
    
    if not os.path.isdir(args.output_folder):
        print(f"Creating output directory at {args.output_folder}")
        os.makedirs(args.output_folder, exist_ok=True)

    if not os.path.isdir(args.obj_dir):
        print(f"Error: The specified directory does not exist: {args.obj_dir}")
        sys.exit(1)
    
    obj_files = glob(os.path.join(args.obj_dir, '*.obj'))
    if not obj_files:
        print(f"No .obj files found in the specified directory: {args.obj_dir}")
        sys.exit(1)
    setup_scene()

    for obj_path in obj_files[150:300]:
        print(f"Processing {obj_path}")
        render_obj(obj_path)
        cleanup_scene() 

    print("Finished processing all .obj files.")
