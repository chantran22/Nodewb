# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_revolve.py
#
#  Revolve Node for FreeCAD Nodes Workbench
#  Revolves a closed sketch/face around an axis
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_revolve.py
#  2. Restart FreeCAD
#
#  USAGE:
#     [Sketch Face] → [Revolve] → [CViewer]
#                        ↑
#                   Axis: "X", "Y", or "Z"
#                   Angle: 360 (full) or less (partial)
#
###################################################################################
from collections import OrderedDict
import math

from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout, QHBoxLayout, QLabel
from qtpy.QtCore import Qt

import FreeCAD as App
from FreeCAD import Vector
import Part

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel, FCNNodeContentView
from core.nodes_default_node import FCNNodeView
from core.nodes_utils import map_objects, broadcast_data_tree, flatten

from nodes_locator import icon


def parse_axis(axis_input) -> tuple:
    """
    Parse axis input - accepts text or number.
    
    Args:
        axis_input: "X", "Y", "Z", "x", "y", "z", 0, 1, 2
    
    Returns:
        (axis_vector, axis_name)
    """
    if isinstance(axis_input, str):
        a = axis_input.strip().upper()
        if a == "X":
            return (Vector(1, 0, 0), "X")
        elif a == "Y":
            return (Vector(0, 1, 0), "Y")
        elif a == "Z":
            return (Vector(0, 0, 1), "Z")
        else:
            # Try to parse as number
            try:
                num = int(float(axis_input))
                if num == 0:
                    return (Vector(1, 0, 0), "X")
                elif num == 1:
                    return (Vector(0, 1, 0), "Y")
                else:
                    return (Vector(0, 0, 1), "Z")
            except:
                return (Vector(0, 0, 1), "Z")  # Default Z
    else:
        # Numeric input
        try:
            num = int(axis_input)
            if num == 0:
                return (Vector(1, 0, 0), "X")
            elif num == 1:
                return (Vector(0, 1, 0), "Y")
            else:
                return (Vector(0, 0, 1), "Z")
        except:
            return (Vector(0, 0, 1), "Z")  # Default Z


class RevolveAxisContent(QDMNodeContentWidget):
    """Content widget with axis input box"""
    
    layout: QLayout
    edit: QLineEdit

    def initUI(self):
        self.layout: QLayout = QHBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(3)
        self.setLayout(self.layout)

        # Label
        label = QLabel("Axis:")
        label.setMaximumWidth(30)
        self.layout.addWidget(label)

        # Axis input
        self.edit: QLineEdit = QLineEdit("Z", self)
        self.edit.setObjectName(self.node.content_label_objname)
        self.edit.setPlaceholderText("X, Y, Z")
        self.edit.setToolTip("Enter axis: X, Y, or Z")
        self.edit.setMaximumWidth(50)
        self.layout.addWidget(self.edit)

    def serialize(self) -> OrderedDict:
        res: OrderedDict = super().serialize()
        res['axis'] = self.edit.text()
        return res

    def deserialize(self, data: dict, hashmap=None, restore_id: bool = True) -> bool:
        if hashmap is None:
            hashmap = {}

        res = super().deserialize(data, hashmap)
        try:
            axis = data['axis']
            self.edit.setText(axis)
            return True & res
        except Exception as e:
            print(f"Deserialize error: {e}")
        return res


@register_node
class Revolve(FCNNodeModel):
    """
    Revolve Node - Revolves a face around an axis
    
    Inputs:
        Shape: Face or closed wire to revolve
        Angle: Angle in degrees (360 = full revolution)
        Axis (text box): "X", "Y", or "Z"
    
    Output:
        Shape: Revolved solid
    
    Usage:
        [Sketch Face: "Sketch"] → Shape → [Revolve] → [CViewer]
                                            ↑
                                    Axis: Z, Angle: 360
    
    Examples:
        - Revolve rectangle around Z = Cylinder/Tube
        - Revolve half-circle around Y = Sphere
        - Revolve L-shape around Z = Bowl/Vase
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Revolve"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Angle", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(130, 90)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = RevolveAxisContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        angle = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 360.0
        
        # Get axis from text box
        axis_text = str(self.content.edit.text())
        axis_vec, axis_name = parse_axis(axis_text)
        
        if len(shape_input) == 0:
            print("Revolve: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            revolved = self.make_revolve(shape, axis_vec, angle)
            if revolved is not None:
                results.append(revolved)
        
        return [results] if results else [[]]
    
    def make_revolve(self, shape, axis_vec, angle):
        """Create revolved shape"""
        try:
            # Get the face/wire to revolve
            profile = None
            
            # If it's a face, use it directly
            if isinstance(shape, Part.Face):
                profile = shape
            # If it's a shape with faces
            elif hasattr(shape, 'Faces') and len(shape.Faces) > 0:
                profile = shape.Faces[0]
            # If it's a wire, make face first
            elif isinstance(shape, Part.Wire):
                profile = Part.Face(shape)
            elif hasattr(shape, 'Wires') and len(shape.Wires) > 0:
                profile = Part.Face(shape.Wires[0])
            # If it's a FreeCAD object
            elif hasattr(shape, 'Shape'):
                return self.make_revolve(shape.Shape, axis_vec, angle)
            
            if profile is None:
                print("Revolve: Could not get profile face")
                return None
            
            # Revolve around axis through origin
            center = Vector(0, 0, 0)
            
            # Create revolution
            revolved = profile.revolve(center, axis_vec, angle)
            
            print(f"Revolve: Created revolution around {self.content.edit.text()} axis, {angle}°")
            return revolved
            
        except Exception as e:
            print(f"Revolve error: {e}")
            return None


@register_node
class RevolveAdvanced(FCNNodeModel):
    """
    Revolve Advanced - More control over revolution
    
    Inputs:
        Shape: Face or closed wire to revolve
        Angle: Angle in degrees
        Axis: "X", "Y", "Z" (or 0, 1, 2) via socket
        Center: Center point for axis (optional, default origin)
    
    Output:
        Shape: Revolved solid
    
    Use this when you need:
        - Custom axis from socket input
        - Custom center point (not origin)
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Revolve+"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Angle", True), 
                                          ("Axis", True), ("Center", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(110, 120)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        angle = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 360.0
        axis_raw = sockets_input_data[2][0] if len(sockets_input_data[2]) > 0 else "Z"
        center_input = sockets_input_data[3][0] if len(sockets_input_data[3]) > 0 else None
        
        # Parse axis
        axis_vec, axis_name = parse_axis(axis_raw)
        
        # Parse center
        if center_input is None:
            center = Vector(0, 0, 0)
        elif hasattr(center_input, 'x'):
            center = center_input
        elif isinstance(center_input, (list, tuple)) and len(center_input) >= 3:
            center = Vector(center_input[0], center_input[1], center_input[2])
        else:
            center = Vector(0, 0, 0)
        
        if len(shape_input) == 0:
            print("Revolve+: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            revolved = self.make_revolve(shape, axis_vec, angle, center)
            if revolved is not None:
                results.append(revolved)
        
        return [results] if results else [[]]
    
    def make_revolve(self, shape, axis_vec, angle, center):
        """Create revolved shape"""
        try:
            # Get the face/wire to revolve
            profile = None
            
            if isinstance(shape, Part.Face):
                profile = shape
            elif hasattr(shape, 'Faces') and len(shape.Faces) > 0:
                profile = shape.Faces[0]
            elif isinstance(shape, Part.Wire):
                profile = Part.Face(shape)
            elif hasattr(shape, 'Wires') and len(shape.Wires) > 0:
                profile = Part.Face(shape.Wires[0])
            elif hasattr(shape, 'Shape'):
                return self.make_revolve(shape.Shape, axis_vec, angle, center)
            
            if profile is None:
                print("Revolve+: Could not get profile face")
                return None
            
            # Create revolution
            revolved = profile.revolve(center, axis_vec, angle)
            
            print(f"Revolve+: Created revolution, {angle}°")
            return revolved
            
        except Exception as e:
            print(f"Revolve+ error: {e}")
            return None