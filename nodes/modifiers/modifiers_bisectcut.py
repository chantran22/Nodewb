# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_bisect.py
#
#  Bisect Cut Node for FreeCAD Nodes Workbench
#  Cuts object with a plane and keeps one side
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_bisect.py
#  2. Restart FreeCAD
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
            try:
                num = int(float(axis_input))
                if num == 0:
                    return (Vector(1, 0, 0), "X")
                elif num == 1:
                    return (Vector(0, 1, 0), "Y")
                else:
                    return (Vector(0, 0, 1), "Z")
            except:
                return (Vector(0, 0, 1), "Z")
    else:
        try:
            num = int(axis_input)
            if num == 0:
                return (Vector(1, 0, 0), "X")
            elif num == 1:
                return (Vector(0, 1, 0), "Y")
            else:
                return (Vector(0, 0, 1), "Z")
        except:
            return (Vector(0, 0, 1), "Z")


class BisectContent(QDMNodeContentWidget):
    """Content widget with axis input box - simple style like Text node"""
    
    layout: QLayout
    axis_edit: QLineEdit

    def initUI(self):
        self.layout: QLayout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # Simple input box like Text node - no label to avoid overlap
        self.axis_edit: QLineEdit = QLineEdit("Z", self)
        self.axis_edit.setObjectName(self.node.content_label_objname)
        self.axis_edit.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.axis_edit)

    def serialize(self) -> OrderedDict:
        res: OrderedDict = super().serialize()
        res['axis'] = self.axis_edit.text()
        return res

    def deserialize(self, data: dict, hashmap=None, restore_id: bool = True) -> bool:
        if hashmap is None:
            hashmap = {}

        res = super().deserialize(data, hashmap)
        try:
            self.axis_edit.setText(data.get('axis', 'Z'))
            return True & res
        except Exception as e:
            print(f"Deserialize error: {e}")
        return res


@register_node
class Bisect(FCNNodeModel):
    """
    Bisect Node - Cut object with a plane, keep one side
    
    Inputs:
        Shape: 3D object to cut
        Position: Cut plane position along axis (e.g., Z=50 cuts at height 50)
        Angle: Rotate cut plane (degrees, around perpendicular axis)
    
    Input Box:
        Axis: Type "X", "Y", or "Z" - normal direction of cut plane
    
    Output:
        Shape: Cut result (keeps NEGATIVE side / below plane)
    
    How it works:
        - Axis Z, Position 50: Horizontal cut at Z=50, keeps Z<50 (below)
        - Axis X, Position 100: Vertical cut at X=100, keeps X<100 (left)
        - Axis Y, Position 0: Vertical cut at Y=0, keeps Y<0 (back)
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Bisect"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Pos", True), ("Angle", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(100, 110)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = BisectContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.axis_edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        position = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 0.0
        angle = float(sockets_input_data[2][0]) if len(sockets_input_data[2]) > 0 else 0.0
        
        # Get axis from text box
        axis_text = str(self.content.axis_edit.text())
        axis_vec, axis_name = parse_axis(axis_text)
        
        if len(shape_input) == 0:
            print("Bisect: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            cut_result = self.make_bisect(shape, axis_vec, axis_name, position, angle)
            if cut_result is not None:
                results.append(cut_result)
        
        return [results] if results else [[]]
    
    def make_bisect(self, shape, axis_vec, axis_name, position, angle):
        """Create bisect cut"""
        try:
            # Handle different input types
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Get bounding box of shape
            bbox = shape.BoundBox
            size = max(bbox.XLength, bbox.YLength, bbox.ZLength) * 10 + 1000
            
            # Create cutting box on POSITIVE side (to be removed)
            if axis_name == "Z":
                base_point = Vector(0, 0, position)
                cut_box = Part.makeBox(size * 2, size * 2, size)
                cut_box.translate(Vector(-size, -size, position))
                rot_axis = Vector(1, 0, 0)
                    
            elif axis_name == "X":
                base_point = Vector(position, 0, 0)
                cut_box = Part.makeBox(size, size * 2, size * 2)
                cut_box.translate(Vector(position, -size, -size))
                rot_axis = Vector(0, 0, 1)
                    
            else:  # Y
                base_point = Vector(0, position, 0)
                cut_box = Part.makeBox(size * 2, size, size * 2)
                cut_box.translate(Vector(-size, position, -size))
                rot_axis = Vector(0, 0, 1)
            
            # Apply angle rotation if needed
            if angle != 0:
                cut_box.rotate(base_point, rot_axis, angle)
            
            # Cut: remove the positive side
            result = shape.cut(cut_box)
            
            print(f"Bisect: Cut at {axis_name}={position}, angle={angle}°")
            return result
            
        except Exception as e:
            print(f"Bisect error: {e}")
            return None


@register_node
class BisectKeep(FCNNodeModel):
    """
    Bisect Keep Node - Choose which side to keep
    
    Inputs:
        Shape: 3D object to cut
        Pos: Cut plane position along axis
        Angle: Rotate cut plane (degrees)
        Keep: 0 = Keep negative/below, 1 = Keep positive/above
    
    Input Box:
        Axis: "X", "Y", or "Z"
    
    Output:
        Shape: Cut result
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Bisect Keep"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Pos", True), 
                                          ("Angle", True), ("Keep", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(110, 130)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = BisectContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.axis_edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        position = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 0.0
        angle = float(sockets_input_data[2][0]) if len(sockets_input_data[2]) > 0 else 0.0
        keep = sockets_input_data[3][0] if len(sockets_input_data[3]) > 0 else 0
        
        # Parse keep value
        if isinstance(keep, str):
            keep_positive = keep.strip() in ["+", "1", "positive", "above", "top"]
        else:
            keep_positive = bool(keep)
        
        # Get axis from text box
        axis_text = str(self.content.axis_edit.text())
        axis_vec, axis_name = parse_axis(axis_text)
        
        if len(shape_input) == 0:
            print("BisectKeep: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_input:
            cut_result = self.make_bisect(shape, axis_name, position, angle, keep_positive)
            if cut_result is not None:
                results.append(cut_result)
        
        return [results] if results else [[]]
    
    def make_bisect(self, shape, axis_name, position, angle, keep_positive):
        """Create bisect cut with choice of which side to keep"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Get bounding box
            bbox = shape.BoundBox
            size = max(bbox.XLength, bbox.YLength, bbox.ZLength) * 10 + 1000
            
            # Create cutting box
            if axis_name == "Z":
                if keep_positive:
                    cut_box = Part.makeBox(size * 2, size * 2, size)
                    cut_box.translate(Vector(-size, -size, position - size))
                else:
                    cut_box = Part.makeBox(size * 2, size * 2, size)
                    cut_box.translate(Vector(-size, -size, position))
                base_point = Vector(0, 0, position)
                rot_axis = Vector(1, 0, 0)
                    
            elif axis_name == "X":
                if keep_positive:
                    cut_box = Part.makeBox(size, size * 2, size * 2)
                    cut_box.translate(Vector(position - size, -size, -size))
                else:
                    cut_box = Part.makeBox(size, size * 2, size * 2)
                    cut_box.translate(Vector(position, -size, -size))
                base_point = Vector(position, 0, 0)
                rot_axis = Vector(0, 0, 1)
                    
            else:  # Y
                if keep_positive:
                    cut_box = Part.makeBox(size * 2, size, size * 2)
                    cut_box.translate(Vector(-size, position - size, -size))
                else:
                    cut_box = Part.makeBox(size * 2, size, size * 2)
                    cut_box.translate(Vector(-size, position, -size))
                base_point = Vector(0, position, 0)
                rot_axis = Vector(0, 0, 1)
            
            # Apply angle rotation
            if angle != 0:
                cut_box.rotate(base_point, rot_axis, angle)
            
            # Cut
            result = shape.cut(cut_box)
            
            side = "+" if keep_positive else "-"
            print(f"BisectKeep: Cut at {axis_name}={position}, keep {side} side")
            return result
            
        except Exception as e:
            print(f"BisectKeep error: {e}")
            return None


@register_node
class BisectBoth(FCNNodeModel):
    """
    Bisect Both Node - Returns BOTH halves
    
    Inputs:
        Shape: 3D object to cut
        Pos: Cut plane position along axis
        Angle: Rotate cut plane (degrees)
    
    Input Box:
        Axis: "X", "Y", or "Z"
    
    Outputs:
        Neg: Part below/left/back of cut plane
        Pos: Part above/right/front of cut plane
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Bisect Both"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("Shape", True), ("Pos", True), ("Angle", True)],
                         outputs_init_list=[("Neg", True), ("Pos", True)])

        self.grNode.resize(110, 110)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = BisectContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.axis_edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get inputs
        shape_input = list(flatten(sockets_input_data[0])) if len(sockets_input_data[0]) > 0 else []
        position = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 0.0
        angle = float(sockets_input_data[2][0]) if len(sockets_input_data[2]) > 0 else 0.0
        
        axis_text = str(self.content.axis_edit.text())
        axis_vec, axis_name = parse_axis(axis_text)
        
        if len(shape_input) == 0:
            print("BisectBoth: No input shape")
            return [[], []]
        
        neg_results = []
        pos_results = []
        
        for shape in shape_input:
            neg, pos = self.make_bisect_both(shape, axis_name, position, angle)
            if neg is not None:
                neg_results.append(neg)
            if pos is not None:
                pos_results.append(pos)
        
        return [neg_results, pos_results]
    
    def make_bisect_both(self, shape, axis_name, position, angle):
        """Create both halves of bisect cut"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            bbox = shape.BoundBox
            size = max(bbox.XLength, bbox.YLength, bbox.ZLength) * 10 + 1000
            
            # Create cutting boxes for both sides
            if axis_name == "Z":
                cut_box_pos = Part.makeBox(size * 2, size * 2, size)
                cut_box_pos.translate(Vector(-size, -size, position))
                cut_box_neg = Part.makeBox(size * 2, size * 2, size)
                cut_box_neg.translate(Vector(-size, -size, position - size))
                base_point = Vector(0, 0, position)
                rot_axis = Vector(1, 0, 0)
                    
            elif axis_name == "X":
                cut_box_pos = Part.makeBox(size, size * 2, size * 2)
                cut_box_pos.translate(Vector(position, -size, -size))
                cut_box_neg = Part.makeBox(size, size * 2, size * 2)
                cut_box_neg.translate(Vector(position - size, -size, -size))
                base_point = Vector(position, 0, 0)
                rot_axis = Vector(0, 0, 1)
                    
            else:  # Y
                cut_box_pos = Part.makeBox(size * 2, size, size * 2)
                cut_box_pos.translate(Vector(-size, position, -size))
                cut_box_neg = Part.makeBox(size * 2, size, size * 2)
                cut_box_neg.translate(Vector(-size, position - size, -size))
                base_point = Vector(0, position, 0)
                rot_axis = Vector(0, 0, 1)
            
            # Apply angle rotation
            if angle != 0:
                cut_box_pos.rotate(base_point, rot_axis, angle)
                cut_box_neg.rotate(base_point, rot_axis, angle)
            
            # Cut to get both halves
            negative_half = shape.cut(cut_box_pos)
            positive_half = shape.cut(cut_box_neg)
            
            print(f"BisectBoth: Split at {axis_name}={position}")
            return (negative_half, positive_half)
            
        except Exception as e:
            print(f"BisectBoth error: {e}")
            return (None, None)