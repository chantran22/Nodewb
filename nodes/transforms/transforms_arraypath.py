# -*- coding: utf-8 -*-
###################################################################################
#
#  transforms_array_on_path.py
#
#  Array on Path Node for FreeCAD Nodes Workbench
#  Distributes objects along a wire/sketch path
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/transforms/transforms_array_on_path.py
#  2. Restart FreeCAD
#
###################################################################################
from collections import OrderedDict
import math

from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout
from qtpy.QtCore import Qt

import FreeCAD as App
from FreeCAD import Vector, Rotation, Placement
import Part

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel, FCNNodeContentView
from core.nodes_default_node import FCNNodeView
from core.nodes_utils import flatten

from nodes_locator import icon


def get_wire_from_input(input_obj):
    """Extract wire from various input types including Object In output"""
    try:
        if input_obj is None:
            return None
        
        # Handle list (Object In returns a list)
        if isinstance(input_obj, list):
            if len(input_obj) > 0:
                return get_wire_from_input(input_obj[0])
            return None
        
        # Already a wire
        if isinstance(input_obj, Part.Wire):
            return input_obj
        
        # Part.Shape
        if isinstance(input_obj, Part.Shape):
            if hasattr(input_obj, 'Wires') and len(input_obj.Wires) > 0:
                return input_obj.Wires[0]
            elif hasattr(input_obj, 'Edges') and len(input_obj.Edges) > 0:
                return Part.Wire(input_obj.Edges)
            return None
        
        # FreeCAD Document Object (from Object In)
        if hasattr(input_obj, 'TypeId'):
            if hasattr(input_obj, 'Shape'):
                shape = input_obj.Shape
                if hasattr(shape, 'Wires') and len(shape.Wires) > 0:
                    return shape.Wires[0]
                elif hasattr(shape, 'Edges') and len(shape.Edges) > 0:
                    return Part.Wire(shape.Edges)
            return None
        
        # Object with Shape attribute
        if hasattr(input_obj, 'Shape'):
            shape = input_obj.Shape
            if hasattr(shape, 'Wires') and len(shape.Wires) > 0:
                return shape.Wires[0]
            elif hasattr(shape, 'Edges') and len(shape.Edges) > 0:
                return Part.Wire(shape.Edges)
        
        return None
        
    except Exception as e:
        print(f"get_wire_from_input error: {e}")
        return None


def get_points_along_wire(wire, count):
    """
    Get evenly distributed points along a wire.
    Uses discretize method which works reliably with Part.Wire.
    """
    try:
        # Use discretize to get points along the wire
        # This is the most reliable method for Part.Wire
        wire_length = wire.Length
        
        if count <= 1:
            # Single point at middle
            points = wire.discretize(2)
            mid_idx = len(points) // 2
            return [points[mid_idx]], [get_tangent_at_point(wire, points[mid_idx])]
        
        # Get evenly spaced points
        points = wire.discretize(count)
        
        # Calculate tangents at each point
        tangents = []
        for i, pt in enumerate(points):
            tangent = get_tangent_at_point(wire, pt)
            tangents.append(tangent)
        
        return points, tangents
        
    except Exception as e:
        print(f"get_points_along_wire error: {e}")
        return [], []


def get_tangent_at_point(wire, point):
    """Get approximate tangent at a point on wire"""
    try:
        # Find the edge containing or nearest to this point
        min_dist = float('inf')
        best_edge = None
        best_param = 0
        
        for edge in wire.Edges:
            try:
                # Get parameter on edge closest to point
                param = edge.Curve.parameter(point)
                pt_on_edge = edge.valueAt(param)
                dist = (pt_on_edge - point).Length
                
                if dist < min_dist:
                    min_dist = dist
                    best_edge = edge
                    best_param = param
            except:
                pass
        
        if best_edge is not None:
            try:
                return best_edge.tangentAt(best_param)
            except:
                pass
        
        # Fallback: use direction between first and last vertex
        if len(wire.Vertexes) >= 2:
            v1 = wire.Vertexes[0].Point
            v2 = wire.Vertexes[-1].Point
            direction = v2 - v1
            if direction.Length > 0:
                return direction.normalize()
        
        return Vector(1, 0, 0)  # Default tangent
        
    except:
        return Vector(1, 0, 0)


def get_points_by_distance(wire, spacing):
    """Get points along wire with fixed spacing"""
    try:
        wire_length = wire.Length
        
        if spacing <= 0:
            spacing = 100
        
        count = max(2, int(wire_length / spacing) + 1)
        return get_points_along_wire(wire, count)
        
    except Exception as e:
        print(f"get_points_by_distance error: {e}")
        return [], []


def calculate_rotation_to_tangent(tangent):
    """Calculate rotation to align object with tangent direction"""
    try:
        if tangent.Length < 0.001:
            return Rotation()
        
        tangent = tangent.normalize()
        
        # We want to align the X-axis (or Z-axis) to the tangent
        # Using X-axis alignment (object "points" along path)
        x_axis = Vector(1, 0, 0)
        
        # Cross product gives rotation axis
        rot_axis = x_axis.cross(tangent)
        
        if rot_axis.Length < 0.001:
            # Vectors are parallel or anti-parallel
            if tangent.x < 0:
                return Rotation(Vector(0, 0, 1), 180)
            else:
                return Rotation()
        
        rot_axis = rot_axis.normalize()
        
        # Angle between vectors
        dot = max(-1, min(1, x_axis.dot(tangent)))
        angle = math.degrees(math.acos(dot))
        
        return Rotation(rot_axis, angle)
        
    except Exception as e:
        print(f"calculate_rotation error: {e}")
        return Rotation()


@register_node
class ArrayOnPath(FCNNodeModel):
    """
    Array on Path Node - Distribute objects along a path
    
    Inputs:
        Shape: Object to array
        Path: Wire/Sketch path (from Object In or Sketch Wire)
        Count: Number of copies
        Align: Align to path tangent (1=yes, 0=no)
    
    Output:
        Shape: Array of objects along path
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Array on Path"
    op_category: str = "Transforms"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Path", True), 
                                          ("Count", True), ("Align", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(120, 125)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        try:
            # Get inputs
            shape_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
            path_input = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else []
            count_input = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [5]
            align_input = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [1]
            
            # Flatten shape input
            shape_list = list(flatten(shape_input))
            if len(shape_list) == 0:
                print("ArrayOnPath: No input shape")
                return [[]]
            
            # Get count and align
            count = int(count_input[0]) if len(count_input) > 0 else 5
            align = bool(align_input[0]) if len(align_input) > 0 else True
            
            # Get wire from path
            path_data = path_input[0] if len(path_input) > 0 else None
            wire = get_wire_from_input(path_data)
            
            if wire is None:
                print("ArrayOnPath: Could not get wire from path input")
                return [[]]
            
            # Get shape
            shape = shape_list[0]
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            print(f"ArrayOnPath: Wire length={wire.Length:.1f}, count={count}")
            
            # Get points along wire
            points, tangents = get_points_along_wire(wire, count)
            
            if len(points) == 0:
                print("ArrayOnPath: No points generated")
                return [[]]
            
            results = []
            
            for i, point in enumerate(points):
                try:
                    # Copy shape
                    copied = shape.copy()
                    
                    if align and i < len(tangents):
                        # Align to tangent
                        tangent = tangents[i]
                        rotation = calculate_rotation_to_tangent(tangent)
                        
                        if rotation.Angle != 0:
                            copied.rotate(Vector(0, 0, 0), rotation.Axis, rotation.Angle)
                    
                    # Translate to point
                    copied.translate(point)
                    results.append(copied)
                    
                except Exception as e:
                    print(f"ArrayOnPath: Error at copy {i}: {e}")
            
            print(f"ArrayOnPath: Created {len(results)} copies")
            
            # Make compound
            if len(results) > 0:
                compound = Part.makeCompound(results)
                return [[compound]]
            
            return [[]]
            
        except Exception as e:
            print(f"ArrayOnPath error: {e}")
            import traceback
            traceback.print_exc()
            return [[]]


@register_node
class ArrayOnPathSpacing(FCNNodeModel):
    """
    Array on Path (Spacing) - Distribute objects with fixed spacing
    
    Inputs:
        Shape: Object to array
        Path: Wire/Sketch path
        Spacing: Distance between copies
        Align: Align to path tangent (1=yes, 0=no)
    
    Output:
        Shape: Array of objects
        Count: Number of copies created
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Path Spacing"
    op_category: str = "Transforms"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Path", True), 
                                          ("Spacing", True), ("Align", True)],
                         outputs_init_list=[("Shape", True), ("Count", True)])

        self.grNode.resize(120, 125)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        try:
            # Get inputs
            shape_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
            path_input = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else []
            spacing_input = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [100]
            align_input = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [1]
            
            shape_list = list(flatten(shape_input))
            if len(shape_list) == 0:
                print("PathSpacing: No input shape")
                return [[], [0]]
            
            spacing = float(spacing_input[0]) if len(spacing_input) > 0 else 100
            align = bool(align_input[0]) if len(align_input) > 0 else True
            
            # Get wire
            path_data = path_input[0] if len(path_input) > 0 else None
            wire = get_wire_from_input(path_data)
            
            if wire is None:
                print("PathSpacing: Could not get wire from path")
                return [[], [0]]
            
            shape = shape_list[0]
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            wire_length = wire.Length
            
            # Calculate count based on spacing
            if spacing <= 0:
                spacing = 100
            count = max(2, int(wire_length / spacing) + 1)
            
            print(f"PathSpacing: Wire length={wire_length:.1f}, spacing={spacing}, count={count}")
            
            # Get points along wire
            points, tangents = get_points_along_wire(wire, count)
            
            if len(points) == 0:
                print("PathSpacing: No points generated")
                return [[], [0]]
            
            results = []
            
            for i, point in enumerate(points):
                try:
                    copied = shape.copy()
                    
                    if align and i < len(tangents):
                        tangent = tangents[i]
                        rotation = calculate_rotation_to_tangent(tangent)
                        if rotation.Angle != 0:
                            copied.rotate(Vector(0, 0, 0), rotation.Axis, rotation.Angle)
                    
                    copied.translate(point)
                    results.append(copied)
                    
                except Exception as e:
                    print(f"PathSpacing: Error at {i}: {e}")
            
            print(f"PathSpacing: Created {len(results)} copies")
            
            if len(results) > 0:
                compound = Part.makeCompound(results)
                return [[compound], [len(results)]]
            
            return [[], [0]]
            
        except Exception as e:
            print(f"PathSpacing error: {e}")
            import traceback
            traceback.print_exc()
            return [[], [0]]


@register_node
class PointsOnPath(FCNNodeModel):
    """
    Points on Path Node - Get points along a path
    
    Inputs:
        Path: Wire/Sketch path
        Count: Number of points
    
    Outputs:
        Points: List of points along path
        Tangents: List of tangent vectors
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Points on Path"
    op_category: str = "Transforms"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Path", True), ("Count", True)],
                         outputs_init_list=[("Points", True), ("Tangents", True)])

        self.grNode.resize(120, 90)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        try:
            path_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
            count_input = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [10]
            
            count = int(count_input[0]) if len(count_input) > 0 else 10
            
            path_data = path_input[0] if len(path_input) > 0 else None
            wire = get_wire_from_input(path_data)
            
            if wire is None:
                print("PointsOnPath: Could not get wire")
                return [[], []]
            
            points, tangents = get_points_along_wire(wire, count)
            
            print(f"PointsOnPath: Generated {len(points)} points")
            
            return [points, tangents]
            
        except Exception as e:
            print(f"PointsOnPath error: {e}")
            return [[], []]