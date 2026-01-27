# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_linear_array.py
#
#  Linear Array Node for FreeCAD Nodes Workbench
#  Creates multiple copies of a shape along a direction
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_linear_array.py
#  2. Restart FreeCAD
#
###################################################################################
from FreeCAD import Vector
import Part

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel
from core.nodes_utils import map_objects, broadcast_data_tree

from nodes_locator import icon


@register_node
class LinearArray(FCNNodeModel):
    """
    Linear Array Node - Creates copies along a direction
    
    Inputs:
        Shape: Shape to array
        Count: Number of copies (including original)
        Spacing: Distance between copies
        Direction: 0=X, 1=Y, 2=Z (default Z)
    
    Output:
        Shape: All copies combined (fused)
        Shapes: List of individual shapes
    
    Example:
        Box + Count=5 + Spacing=100 + Direction=2(Z)
        = 5 boxes stacked in Z, 100mm apart
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Linear Array"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Count", True), ("Spacing", True), ("Direction", True)],
                         outputs_init_list=[("Shape", True), ("Shapes", True)])
        
        self.grNode.resize(120, 120)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_array(parameter_zip: tuple) -> tuple:
        shape: Part.Shape = parameter_zip[0]
        count: int = int(parameter_zip[1]) if len(parameter_zip) > 1 else 3
        spacing: float = float(parameter_zip[2]) if len(parameter_zip) > 2 else 100.0
        direction: int = int(parameter_zip[3]) if len(parameter_zip) > 3 else 2  # Default Z
        
        # Ensure at least 1 copy
        count = max(1, count)
        
        # Create direction vector
        if direction == 0:
            dir_vec = Vector(1, 0, 0)  # X
        elif direction == 1:
            dir_vec = Vector(0, 1, 0)  # Y
        else:
            dir_vec = Vector(0, 0, 1)  # Z (default)
        
        try:
            shapes_list = []
            
            for i in range(count):
                # Calculate offset
                offset = Vector(dir_vec.x * spacing * i,
                               dir_vec.y * spacing * i,
                               dir_vec.z * spacing * i)
                
                # Create translated copy
                if i == 0:
                    copy = shape.copy()
                else:
                    copy = shape.translated(offset)
                
                shapes_list.append(copy)
            
            # Fuse all shapes into one
            if len(shapes_list) > 1:
                combined = shapes_list[0]
                for s in shapes_list[1:]:
                    combined = combined.fuse(s)
            else:
                combined = shapes_list[0]
            
            return (combined, shapes_list)
            
        except Exception as e:
            print(f"LinearArray error: {e}")
            return (shape, [shape])
    
    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        count_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [3]
        spacing_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [100.0]
        direction_input: list = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [2]
        
        if len(shape_input) == 0:
            return [[], []]
        
        # Process each shape
        combined_list = []
        shapes_list = []
        
        for shape in shape_input:
            result = self.make_array((shape, count_input[0], spacing_input[0], direction_input[0]))
            combined_list.append(result[0])
            shapes_list.extend(result[1])
        
        return [combined_list, shapes_list]


@register_node
class LinearArrayVector(FCNNodeModel):
    """
    Linear Array (Vector) Node - Creates copies along custom vector direction
    
    Inputs:
        Shape: Shape to array
        Count: Number of copies (including original)
        Vector: Direction and spacing as vector (e.g., 100,0,50 = X+Z diagonal)
    
    Output:
        Shape: All copies combined
        Shapes: List of individual shapes
    
    Example:
        Box + Count=5 + Vector(100,0,50)
        = 5 boxes in diagonal X-Z direction
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Array Vector"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Count", True), ("Vector", True)],
                         outputs_init_list=[("Shape", True), ("Shapes", True)])
        
        self.grNode.resize(120, 100)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_array_vector(parameter_zip: tuple) -> tuple:
        shape: Part.Shape = parameter_zip[0]
        count: int = int(parameter_zip[1]) if len(parameter_zip) > 1 else 3
        vec = parameter_zip[2] if len(parameter_zip) > 2 else Vector(0, 0, 100)
        
        # Handle vector input
        if isinstance(vec, (list, tuple)) and len(vec) >= 3:
            direction = Vector(vec[0], vec[1], vec[2])
        elif hasattr(vec, 'x'):
            direction = vec
        else:
            direction = Vector(0, 0, 100)
        
        count = max(1, count)
        
        try:
            shapes_list = []
            
            for i in range(count):
                offset = Vector(direction.x * i, direction.y * i, direction.z * i)
                
                if i == 0:
                    copy = shape.copy()
                else:
                    copy = shape.translated(offset)
                
                shapes_list.append(copy)
            
            # Fuse all shapes
            if len(shapes_list) > 1:
                combined = shapes_list[0]
                for s in shapes_list[1:]:
                    combined = combined.fuse(s)
            else:
                combined = shapes_list[0]
            
            return (combined, shapes_list)
            
        except Exception as e:
            print(f"ArrayVector error: {e}")
            return (shape, [shape])
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        count_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [3]
        vector_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [Vector(0, 0, 100)]
        
        if len(shape_input) == 0:
            return [[], []]
        
        combined_list = []
        shapes_list = []
        
        for shape in shape_input:
            result = self.make_array_vector((shape, count_input[0], vector_input[0]))
            combined_list.append(result[0])
            shapes_list.extend(result[1])
        
        return [combined_list, shapes_list]


@register_node
class RectangularArray(FCNNodeModel):
    """
    Rectangular Array Node - Creates 2D grid of copies
    
    Inputs:
        Shape: Shape to array
        Count X: Number in X direction
        Count Y: Number in Y direction
        Spacing X: Distance in X
        Spacing Y: Distance in Y
    
    Output:
        Shape: All copies combined
        Shapes: List of individual shapes
    
    Example:
        Box + CountX=3 + CountY=4 + SpacingX=100 + SpacingY=100
        = 3x4 grid of boxes
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Rect Array"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Count X", True), ("Count Y", True), 
                                          ("Spacing X", True), ("Spacing Y", True)],
                         outputs_init_list=[("Shape", True), ("Shapes", True)])
        
        self.grNode.resize(120, 140)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_rect_array(parameter_zip: tuple) -> tuple:
        shape: Part.Shape = parameter_zip[0]
        count_x: int = int(parameter_zip[1]) if len(parameter_zip) > 1 else 3
        count_y: int = int(parameter_zip[2]) if len(parameter_zip) > 2 else 3
        spacing_x: float = float(parameter_zip[3]) if len(parameter_zip) > 3 else 100.0
        spacing_y: float = float(parameter_zip[4]) if len(parameter_zip) > 4 else 100.0
        
        count_x = max(1, count_x)
        count_y = max(1, count_y)
        
        try:
            shapes_list = []
            
            for i in range(count_x):
                for j in range(count_y):
                    offset = Vector(spacing_x * i, spacing_y * j, 0)
                    
                    if i == 0 and j == 0:
                        copy = shape.copy()
                    else:
                        copy = shape.translated(offset)
                    
                    shapes_list.append(copy)
            
            # Fuse all shapes
            if len(shapes_list) > 1:
                combined = shapes_list[0]
                for s in shapes_list[1:]:
                    combined = combined.fuse(s)
            else:
                combined = shapes_list[0]
            
            return (combined, shapes_list)
            
        except Exception as e:
            print(f"RectArray error: {e}")
            return (shape, [shape])
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        count_x_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [3]
        count_y_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [3]
        spacing_x_input: list = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [100.0]
        spacing_y_input: list = sockets_input_data[4] if len(sockets_input_data[4]) > 0 else [100.0]
        
        if len(shape_input) == 0:
            return [[], []]
        
        combined_list = []
        shapes_list = []
        
        for shape in shape_input:
            result = self.make_rect_array((shape, count_x_input[0], count_y_input[0],
                                           spacing_x_input[0], spacing_y_input[0]))
            combined_list.append(result[0])
            shapes_list.extend(result[1])
        
        return [combined_list, shapes_list]


@register_node
class PolarArray(FCNNodeModel):
    """
    Polar Array Node - Creates copies in circular pattern
    
    Inputs:
        Shape: Shape to array
        Count: Number of copies
        Angle: Total angle in degrees (360 = full circle)
        Axis: 0=X, 1=Y, 2=Z (rotation axis, default Z)
    
    Output:
        Shape: All copies combined
        Shapes: List of individual shapes
    
    Example:
        Box + Count=6 + Angle=360 + Axis=2(Z)
        = 6 boxes in circle around Z axis
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Polar Array"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Count", True), ("Angle", True), ("Axis", True)],
                         outputs_init_list=[("Shape", True), ("Shapes", True)])
        
        self.grNode.resize(120, 120)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_polar_array(parameter_zip: tuple) -> tuple:
        import math
        
        shape: Part.Shape = parameter_zip[0]
        count: int = int(parameter_zip[1]) if len(parameter_zip) > 1 else 6
        total_angle: float = float(parameter_zip[2]) if len(parameter_zip) > 2 else 360.0
        axis: int = int(parameter_zip[3]) if len(parameter_zip) > 3 else 2  # Default Z
        
        count = max(1, count)
        
        # Create axis vector
        if axis == 0:
            axis_vec = Vector(1, 0, 0)  # X
        elif axis == 1:
            axis_vec = Vector(0, 1, 0)  # Y
        else:
            axis_vec = Vector(0, 0, 1)  # Z (default)
        
        # Angle per copy
        if count > 1:
            angle_step = total_angle / count
        else:
            angle_step = 0
        
        try:
            shapes_list = []
            
            for i in range(count):
                angle = angle_step * i
                
                if i == 0:
                    copy = shape.copy()
                else:
                    # Rotate around axis through origin
                    copy = shape.copy()
                    copy.rotate(Vector(0, 0, 0), axis_vec, angle)
                
                shapes_list.append(copy)
            
            # Fuse all shapes
            if len(shapes_list) > 1:
                combined = shapes_list[0]
                for s in shapes_list[1:]:
                    combined = combined.fuse(s)
            else:
                combined = shapes_list[0]
            
            return (combined, shapes_list)
            
        except Exception as e:
            print(f"PolarArray error: {e}")
            return (shape, [shape])
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        count_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [6]
        angle_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [360.0]
        axis_input: list = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [2]
        
        if len(shape_input) == 0:
            return [[], []]
        
        combined_list = []
        shapes_list = []
        
        for shape in shape_input:
            result = self.make_polar_array((shape, count_input[0], angle_input[0], axis_input[0]))
            combined_list.append(result[0])
            shapes_list.extend(result[1])
        
        return [combined_list, shapes_list]
        
 

@register_node
class PolarArrayUp(FCNNodeModel):
    """
    Polar Array Up Node - Creates copies in circular pattern and moves them along chosen axis
    
    Inputs:
        Shape: Shape to array
        Count: Number of copies
        Angle: Total angle in degrees (360 = full circle)
        Axis: 0=X, 1=Y, 2=Z (rotation axis, also direction of translation)
        Step: Distance moved per copy along axis
    
    Output:
        Shape: All copies combined
        Shapes: List of individual shapes
    
    Creates spiral/helical patterns like:
        - Spiral staircase
        - Helix
        - Screw threads
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Polar Array Up"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Count", True), ("Angle", True), ("Axis", True), ("Step", True)],
                         outputs_init_list=[("Shape", True), ("Shapes", True)])
        
        self.grNode.resize(140, 140)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_polar_array_up(parameter_zip: tuple) -> tuple:
        import math
        
        shape: Part.Shape = parameter_zip[0]
        count: int = int(parameter_zip[1]) if len(parameter_zip) > 1 else 6
        total_angle: float = float(parameter_zip[2]) if len(parameter_zip) > 2 else 360.0
        axis: int = int(parameter_zip[3]) if len(parameter_zip) > 3 else 2  # Default Z
        step: float = float(parameter_zip[4]) if len(parameter_zip) > 4 else 25.0
        
        count = max(1, count)
        
        # Axis vector (used for both rotation and translation)
        if axis == 0:
            axis_vec = Vector(1, 0, 0)  # X
        elif axis == 1:
            axis_vec = Vector(0, 1, 0)  # Y
        else:
            axis_vec = Vector(0, 0, 1)  # Z
        
        # Angle per copy
        angle_step = total_angle / count if count > 1 else 0
        
        try:
            shapes_list = []
            
            for i in range(count):
                angle = angle_step * i
                copy = shape.copy()
                
                # Rotate around axis (only if not first copy and angle > 0)
                if angle != 0:
                    copy.rotate(Vector(0, 0, 0), axis_vec, angle)
                
                # Translate along same axis
                # FIX: Don't use multiply() - it modifies in place!
                # Use Vector multiplication instead
                translation = Vector(
                    axis_vec.x * step * i,
                    axis_vec.y * step * i,
                    axis_vec.z * step * i
                )
                copy.translate(translation)
                
                shapes_list.append(copy)
            
            # Make compound instead of fuse (faster and preserves individual shapes)
            if len(shapes_list) > 0:
                combined = Part.makeCompound(shapes_list)
            else:
                combined = shape
            
            return (combined, shapes_list)
        
        except Exception as e:
            print(f"PolarArrayUp error: {e}")
            import traceback
            traceback.print_exc()
            return (shape, [shape])
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        count_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [6]
        angle_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [360.0]
        axis_input: list = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [2]
        step_input: list = sockets_input_data[4] if len(sockets_input_data[4]) > 0 else [25.0]
        
        if len(shape_input) == 0:
            return [[], []]
        
        combined_list = []
        shapes_list = []
        
        for shape in shape_input:
            # Handle FreeCAD objects
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            result = self.make_polar_array_up((shape, count_input[0], angle_input[0], axis_input[0], step_input[0]))
            combined_list.append(result[0])
            shapes_list.extend(result[1])
        
        return [combined_list, shapes_list]
