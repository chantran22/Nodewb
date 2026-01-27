# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_mirror.py
#
#  Mirror Node for FreeCAD Nodes Workbench
#  Mirrors 3D objects across planes
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_mirror.py
#  2. Restart FreeCAD
#
#  USAGE:
#     [Box] → [Mirror] → [CViewer]
#               ↑
#         Plane: XY, XZ, or YZ
#         Base Point: origin or custom
#
###################################################################################
from collections import OrderedDict
import math

from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout, QHBoxLayout, QLabel
from qtpy.QtCore import Qt

import FreeCAD as App
from FreeCAD import Vector, Matrix, Placement, Rotation
import Part

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel, FCNNodeContentView
from core.nodes_default_node import FCNNodeView
from core.nodes_utils import map_objects, broadcast_data_tree, flatten

from nodes_locator import icon


def parse_mirror_plane(plane_input) -> tuple:
    """
    Parse mirror plane input.
    
    Args:
        plane_input: "XY", "XZ", "YZ", "xy", "yz", etc.
    
    Returns:
        (normal_vector, plane_name)
        
    Mirror planes:
        XY plane: Normal is Z (0,0,1) - mirrors across horizontal plane
        XZ plane: Normal is Y (0,1,0) - mirrors front/back
        YZ plane: Normal is X (1,0,0) - mirrors left/right
    """
    if isinstance(plane_input, str):
        p = plane_input.strip().upper().replace(" ", "")
        
        # Sort characters to handle both "XY" and "YX"
        chars = sorted(p)
        plane_key = "".join(chars)
        
        if plane_key == "XY" or p == "Z":
            return (Vector(0, 0, 1), "XY")
        elif plane_key == "XZ" or p == "Y":
            return (Vector(0, 1, 0), "XZ")
        elif plane_key == "YZ" or p == "X":
            return (Vector(1, 0, 0), "YZ")
        else:
            # Default to XY
            return (Vector(0, 0, 1), "XY")
    else:
        return (Vector(0, 0, 1), "XY")


class MirrorPlaneContent(QDMNodeContentWidget):
    """Content widget with plane input box"""
    
    layout: QLayout
    plane_edit: QLineEdit

    def initUI(self):
        self.layout: QLayout = QHBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(3)
        self.setLayout(self.layout)

        # Plane label
        label = QLabel("Plane:")
        label.setMaximumWidth(35)
        self.layout.addWidget(label)

        # Plane input
        self.plane_edit: QLineEdit = QLineEdit("XY", self)
        self.plane_edit.setObjectName(self.node.content_label_objname)
        self.plane_edit.setPlaceholderText("XY,XZ,YZ")
        self.plane_edit.setToolTip("Mirror plane: XY, XZ, or YZ")
        self.plane_edit.setMaximumWidth(45)
        self.layout.addWidget(self.plane_edit)

    def serialize(self) -> OrderedDict:
        res: OrderedDict = super().serialize()
        res['plane'] = self.plane_edit.text()
        return res

    def deserialize(self, data: dict, hashmap=None, restore_id: bool = True) -> bool:
        if hashmap is None:
            hashmap = {}

        res = super().deserialize(data, hashmap)
        try:
            self.plane_edit.setText(data.get('plane', 'XY'))
            return True & res
        except Exception as e:
            print(f"Deserialize error: {e}")
        return res


@register_node
class Mirror(FCNNodeModel):
    """
    Mirror Node - Mirror object across a plane
    
    Inputs:
        Shape: 3D object to mirror
        Base: Base point for mirror plane (optional, default origin)
        Plane (text box): "XY", "XZ", or "YZ"
    
    Output:
        Shape: Mirrored shape (copy only, not fused with original)
    
    Mirror Planes:
        XY: Horizontal plane (mirrors up/down in Z)
        XZ: Vertical plane (mirrors front/back in Y)
        YZ: Vertical plane (mirrors left/right in X)
    
    Usage:
        [Box at X=50] → [Mirror Plane=YZ] → Box at X=-50
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Mirror"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Base", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(130, 85)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = MirrorPlaneContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.plane_edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        base_input = sockets_input_data[1][0] if len(sockets_input_data[1]) > 0 else None
        
        # Get plane from text box
        plane_text = str(self.content.plane_edit.text())
        normal, plane_name = parse_mirror_plane(plane_text)
        
        # Parse base point
        base_point = self.parse_point(base_input)
        
        if len(shape_input) == 0:
            print("Mirror: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            mirrored = self.make_mirror(shape, normal, base_point, plane_name)
            if mirrored is not None:
                results.append(mirrored)
        
        return [results] if results else [[]]
    
    def parse_point(self, point_input):
        """Parse point input to Vector"""
        if point_input is None:
            return Vector(0, 0, 0)
        elif hasattr(point_input, 'x'):
            return point_input
        elif isinstance(point_input, (list, tuple)) and len(point_input) >= 3:
            return Vector(point_input[0], point_input[1], point_input[2])
        else:
            return Vector(0, 0, 0)
    
    def make_mirror(self, shape, normal, base_point, plane_name):
        """Create mirrored shape"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Create mirror matrix
            # Mirror formula: P' = P - 2 * ((P - Base) · Normal) * Normal
            # Using FreeCAD's mirror method
            
            mirrored = shape.mirror(base_point, normal)
            
            print(f"Mirror: Mirrored across {plane_name} plane at {base_point}")
            return mirrored
            
        except Exception as e:
            print(f"Mirror error: {e}")
            return None


@register_node
class MirrorFuse(FCNNodeModel):
    """
    Mirror Fuse Node - Mirror and combine with original
    
    Inputs:
        Shape: 3D object to mirror
        Base: Base point for mirror plane (optional)
        Plane (text box): "XY", "XZ", or "YZ"
    
    Output:
        Shape: Original + Mirrored combined (fused)
    
    Creates symmetric objects!
    
    Usage:
        [Half cup] → [Mirror Fuse Plane=YZ] → Full symmetric cup
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Mirror Fuse"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Base", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(130, 85)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = MirrorPlaneContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.plane_edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        base_input = sockets_input_data[1][0] if len(sockets_input_data[1]) > 0 else None
        
        plane_text = str(self.content.plane_edit.text())
        normal, plane_name = parse_mirror_plane(plane_text)
        
        base_point = self.parse_point(base_input)
        
        if len(shape_input) == 0:
            print("MirrorFuse: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            fused = self.make_mirror_fuse(shape, normal, base_point, plane_name)
            if fused is not None:
                results.append(fused)
        
        return [results] if results else [[]]
    
    def parse_point(self, point_input):
        if point_input is None:
            return Vector(0, 0, 0)
        elif hasattr(point_input, 'x'):
            return point_input
        elif isinstance(point_input, (list, tuple)) and len(point_input) >= 3:
            return Vector(point_input[0], point_input[1], point_input[2])
        else:
            return Vector(0, 0, 0)
    
    def make_mirror_fuse(self, shape, normal, base_point, plane_name):
        """Create mirrored shape and fuse with original"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Mirror
            mirrored = shape.mirror(base_point, normal)
            
            # Fuse with original
            fused = shape.fuse(mirrored)
            
            print(f"MirrorFuse: Mirrored and fused across {plane_name} plane")
            return fused
            
        except Exception as e:
            print(f"MirrorFuse error: {e}")
            return None


@register_node
class MirrorCustom(FCNNodeModel):
    """
    Mirror Custom Node - Mirror across custom plane defined by normal vector
    
    Inputs:
        Shape: 3D object to mirror
        Base: Base point for mirror plane
        Normal: Normal vector defining plane orientation (e.g., Vector(1,1,0) for diagonal)
    
    Output:
        Shape: Mirrored shape
    
    For irregular/diagonal mirror planes!
    
    Usage:
        [Shape] → [Mirror Custom] → Mirrored shape
                      ↑
               Normal: (1,1,0) = diagonal 45° plane
               Base: (0,0,0)
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Mirror Custom"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Base", True), ("Normal", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(130, 100)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        base_input = sockets_input_data[1][0] if len(sockets_input_data[1]) > 0 else None
        normal_input = sockets_input_data[2][0] if len(sockets_input_data[2]) > 0 else None
        
        base_point = self.parse_vector(base_input, Vector(0, 0, 0))
        normal = self.parse_vector(normal_input, Vector(0, 0, 1))
        
        # Normalize the normal vector
        if normal.Length > 0:
            normal = normal.normalize()
        else:
            normal = Vector(0, 0, 1)
        
        if len(shape_input) == 0:
            print("MirrorCustom: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            mirrored = self.make_mirror(shape, normal, base_point)
            if mirrored is not None:
                results.append(mirrored)
        
        return [results] if results else [[]]
    
    def parse_vector(self, vec_input, default):
        if vec_input is None:
            return default
        elif hasattr(vec_input, 'x'):
            return vec_input
        elif isinstance(vec_input, (list, tuple)) and len(vec_input) >= 3:
            return Vector(vec_input[0], vec_input[1], vec_input[2])
        else:
            return default
    
    def make_mirror(self, shape, normal, base_point):
        """Create mirrored shape across custom plane"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            mirrored = shape.mirror(base_point, normal)
            
            print(f"MirrorCustom: Mirrored across plane with normal {normal}")
            return mirrored
            
        except Exception as e:
            print(f"MirrorCustom error: {e}")
            return None


@register_node
class MirrorLine(FCNNodeModel):
    """
    Mirror Line Node - Mirror across a plane defined by a line/edge
    
    Inputs:
        Shape: 3D object to mirror
        Line: Edge/Wire to define mirror plane (plane contains this line)
        Base: Base point (optional, uses line start if not provided)
        Axis: "X", "Y", "Z" - which axis the plane normal is perpendicular to
    
    Output:
        Shape: Mirrored shape
    
    The mirror plane:
        - Contains the input line
        - Has normal perpendicular to the line and the specified axis
    
    Usage:
        Draw a diagonal line, mirror object across plane containing that line
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Mirror Line"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Line", True), ("Base", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(130, 100)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        line_input = sockets_input_data[1][0] if len(sockets_input_data[1]) > 0 else None
        base_input = sockets_input_data[2][0] if len(sockets_input_data[2]) > 0 else None
        
        if len(shape_input) == 0:
            print("MirrorLine: No input shape")
            return [[]]
        
        if line_input is None:
            print("MirrorLine: No line input")
            return [[]]
        
        # Get line direction and point
        line_dir, line_point = self.get_line_info(line_input)
        
        if line_dir is None:
            print("MirrorLine: Could not get line direction")
            return [[]]
        
        # Base point
        if base_input is not None:
            base_point = self.parse_vector(base_input)
        else:
            base_point = line_point
        
        # Calculate normal: perpendicular to line direction
        # We use cross product with Z axis (or Y if line is parallel to Z)
        up = Vector(0, 0, 1)
        if abs(line_dir.dot(up)) > 0.99:
            up = Vector(0, 1, 0)
        
        normal = line_dir.cross(up)
        if normal.Length > 0:
            normal = normal.normalize()
        else:
            normal = Vector(1, 0, 0)
        
        results = []
        
        for shape in shape_input:
            mirrored = self.make_mirror(shape, normal, base_point)
            if mirrored is not None:
                results.append(mirrored)
        
        return [results] if results else [[]]
    
    def get_line_info(self, line_input):
        """Extract direction and point from line/edge input"""
        try:
            # If it's a FreeCAD object with Shape
            if hasattr(line_input, 'Shape'):
                line_input = line_input.Shape
            
            # If it's a wire, get first edge
            if hasattr(line_input, 'Edges') and len(line_input.Edges) > 0:
                edge = line_input.Edges[0]
                # Get direction from edge
                if hasattr(edge, 'Vertexes') and len(edge.Vertexes) >= 2:
                    p1 = edge.Vertexes[0].Point
                    p2 = edge.Vertexes[1].Point
                    direction = (p2 - p1).normalize()
                    return (direction, p1)
            
            # If it's an edge directly
            if hasattr(line_input, 'Vertexes') and len(line_input.Vertexes) >= 2:
                p1 = line_input.Vertexes[0].Point
                p2 = line_input.Vertexes[1].Point
                direction = (p2 - p1).normalize()
                return (direction, p1)
            
            # If it's a vector (direction only)
            if hasattr(line_input, 'x'):
                return (line_input.normalize(), Vector(0, 0, 0))
            
            return (None, None)
            
        except Exception as e:
            print(f"MirrorLine get_line_info error: {e}")
            return (None, None)
    
    def parse_vector(self, vec_input):
        if vec_input is None:
            return Vector(0, 0, 0)
        elif hasattr(vec_input, 'x'):
            return vec_input
        elif isinstance(vec_input, (list, tuple)) and len(vec_input) >= 3:
            return Vector(vec_input[0], vec_input[1], vec_input[2])
        else:
            return Vector(0, 0, 0)
    
    def make_mirror(self, shape, normal, base_point):
        """Create mirrored shape"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            mirrored = shape.mirror(base_point, normal)
            
            print(f"MirrorLine: Mirrored across plane at {base_point}")
            return mirrored
            
        except Exception as e:
            print(f"MirrorLine error: {e}")
            return None