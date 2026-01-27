# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_thickness.py
#
#  Thickness (Shell/Offset) Node for FreeCAD Nodes Workbench
#  Creates a hollow shell from a solid by offsetting faces
#
#  Updated: Added Join Type (Intersection) and default Z-face opening
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_thickness.py
#  2. Restart FreeCAD
#
###################################################################################
from FreeCAD import Vector
import Part

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel
from core.nodes_utils import map_objects, broadcast_data_tree

from nodes_locator import icon


# Join Type constants (matching FreeCAD)
JOIN_ARC = 0         # Arc
JOIN_TANGENT = 1     # Tangent  
JOIN_INTERSECT = 2   # Intersection (most common for thickness)


def find_z_face(shape, find_max=True):
    """
    Find the face with highest or lowest Z center point.
    
    Args:
        shape: Part.Shape with faces
        find_max: True = top face (max Z), False = bottom face (min Z)
    
    Returns:
        Face with highest/lowest Z center
    """
    if not hasattr(shape, 'Faces') or len(shape.Faces) == 0:
        return None
    
    target_face = None
    target_z = None
    
    for face in shape.Faces:
        # Get center of mass of face
        center = face.CenterOfMass
        z = center.z
        
        if target_z is None:
            target_z = z
            target_face = face
        elif find_max and z > target_z:
            target_z = z
            target_face = face
        elif not find_max and z < target_z:
            target_z = z
            target_face = face
    
    return target_face


@register_node
class Thickness(FCNNodeModel):
    """
    Thickness Node - Creates hollow shell from solid
    
    Inputs:
        Shape: Solid shape to hollow out
        Thickness: Wall thickness value (mm)
        Open Face: Which face to remove
                   0 = Auto top Z face (default)
                   1 = Bottom Z face
                   2+ = Specific face index
    
    Output:
        Shape: Hollowed shell shape
    
    Settings:
        - Mode: Skin
        - Join Type: Intersection (default)
        - Open Face: Top Z face (default)
    
    Note:
        - Positive thickness = inward offset (wall inside)
        - Negative thickness = outward offset (wall outside)
    """
    
    icon: str = icon("nodes_default.svg")
    op_title: str = "Thickness"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Thickness", True), ("Open Face", True)],
                         outputs_init_list=[("Shape", True)])
        
        self.grNode.resize(120, 100)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_thickness(parameter_zip: tuple) -> Part.Shape:
        shape: Part.Shape = parameter_zip[0]
        thickness: float = float(parameter_zip[1]) if len(parameter_zip) > 1 else 1.0
        open_face_mode: int = int(parameter_zip[2]) if len(parameter_zip) > 2 else 0
        
        try:
            # Get faces from shape
            if not hasattr(shape, 'Faces') or len(shape.Faces) == 0:
                print("Thickness error: Shape has no faces")
                return shape
            
            # Determine which face to remove (open)
            if open_face_mode == 0:
                # Auto: Top Z face (default)
                face_to_remove = find_z_face(shape, find_max=True)
            elif open_face_mode == 1:
                # Bottom Z face
                face_to_remove = find_z_face(shape, find_max=False)
            else:
                # Specific face index (mode 2 = face 0, mode 3 = face 1, etc.)
                face_index = open_face_mode - 2
                num_faces = len(shape.Faces)
                face_index = max(0, min(face_index, num_faces - 1))
                face_to_remove = shape.Faces[face_index]
            
            if face_to_remove is None:
                print("Thickness error: Could not find face to remove")
                return shape
            
            # Create shell using makeThickSolid
            # Parameters: 
            #   facesToRemove: list of faces to remove
            #   offset: thickness value
            #   tolerance: precision
            #   intersection: use intersection mode (True)
            #   selfInter: allow self-intersection (False)
            #   join: join type (0=Arc, 1=Tangent, 2=Intersection)
            
            shell = shape.makeThickSolid(
                [face_to_remove],      # Faces to remove (open)
                thickness,              # Offset/thickness
                1e-3,                   # Tolerance
                False,                  # Intersection mode
                False,                  # Self-intersection
                JOIN_INTERSECT          # Join type = Intersection
            )
            
            return shell
            
        except Exception as e:
            print(f"Thickness error: {e}")
            
            # Try simpler method
            try:
                # Fallback: try with fewer parameters
                face_to_remove = find_z_face(shape, find_max=True)
                shell = shape.makeThickSolid([face_to_remove], thickness, 1e-3)
                return shell
                
            except Exception as e2:
                print(f"Thickness fallback error: {e2}")
                return shape
    
    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        thickness_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [1.0]
        open_face_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [0]
        
        # Need shape input
        if len(shape_input) == 0:
            return [[]]
        
        # Broadcast and calculate result
        data_tree: list = list(broadcast_data_tree(shape_input, thickness_input, open_face_input))
        shells: list = list(map_objects(data_tree, tuple, self.make_thickness))
        
        return [shells]


@register_node
class Offset3D(FCNNodeModel):
    """
    Offset 3D Node - Offsets all faces of a shape uniformly
    
    Inputs:
        Shape: Shape to offset
        Distance: Offset distance (positive = outward, negative = inward)
        Join Type: 0=Arc, 1=Tangent, 2=Intersection (default)
    
    Output:
        Shape: Offset shape
    
    Note: Unlike Thickness, this doesn't remove any face - 
          it creates a larger/smaller version of the shape.
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Offset 3D"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Distance", True), ("Join Type", True)],
                         outputs_init_list=[("Shape", True)])
        
        self.grNode.resize(110, 100)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_offset(parameter_zip: tuple) -> Part.Shape:
        shape: Part.Shape = parameter_zip[0]
        distance: float = float(parameter_zip[1]) if len(parameter_zip) > 1 else 1.0
        join_type: int = int(parameter_zip[2]) if len(parameter_zip) > 2 else JOIN_INTERSECT
        
        try:
            # makeOffsetShape(offset, tolerance, fill=False, join=0, intersection=False)
            # join: 0=Arc, 1=Tangent, 2=Intersection
            offset_shape = shape.makeOffsetShape(distance, 1e-3, False, join_type, False)
            return offset_shape
            
        except Exception as e:
            print(f"Offset 3D error: {e}")
            return shape
    
    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        distance_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [1.0]
        join_type_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [JOIN_INTERSECT]
        
        if len(shape_input) == 0:
            return [[]]
        
        # Broadcast and calculate result
        data_tree: list = list(broadcast_data_tree(shape_input, distance_input, join_type_input))
        offsets: list = list(map_objects(data_tree, tuple, self.make_offset))
        
        return [offsets]