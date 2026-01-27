# -*- coding: utf-8 -*-
###################################################################################
#
#  scene_sketch_in.py
#
#  Sketch In Node for FreeCAD Nodes Workbench
#  Directly links to a Sketch and outputs Face ready for extrusion
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/scene/scene_sketch_in.py
#  2. Restart FreeCAD
#
###################################################################################
from collections import OrderedDict

from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout
from qtpy.QtCore import Qt

import FreeCAD as App
import Part

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel, FCNNodeContentView
from core.nodes_default_node import FCNNodeView

from nodes_locator import icon


class SketchInputContent(QDMNodeContentWidget):
    """Content widget with text input for sketch name"""
    
    layout: QLayout
    edit: QLineEdit

    def initUI(self):
        self.layout: QLayout = QVBoxLayout()
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.layout)

        self.edit: QLineEdit = QLineEdit("Sketch", self)
        self.edit.setObjectName(self.node.content_label_objname)
        self.edit.setPlaceholderText("Sketch name")

        self.layout.addWidget(self.edit)

    def serialize(self) -> OrderedDict:
        res: OrderedDict = super().serialize()
        res['value'] = self.edit.text()
        return res

    def deserialize(self, data: dict, hashmap=None, restore_id: bool = True) -> bool:
        if hashmap is None:
            hashmap = {}

        res = super().deserialize(data, hashmap)
        try:
            value = data['value']
            self.edit.setText(value)
            return True & res
        except Exception as e:
            print(f"Deserialize error: {e}")
        return res


@register_node
class SketchIn(FCNNodeModel):
    """
    Sketch In Node - Links to Sketch and outputs Face
    
    Input:
        Type sketch label in the text box (e.g., "Sketch", "Sketch001")
    
    Outputs:
        Face: Face made from sketch (ready for Extrude!)
        Wire: Wire from sketch
        Object: Original sketch object
    
    Usage:
        [Sketch In: "Sketch"] → Face → [Extrude] → [CViewer]
        
    No need for Object Info, Shape Info, or Make Face!
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Sketch In"
    op_category: str = "Scene"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[], 
                         outputs_init_list=[("Face", True), ("Wire", True), ("Object", True)])

        self.grNode.resize(120, 90)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = SketchInputContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        sketch_label: str = str(self.content.edit.text())
        
        if App.ActiveDocument is None:
            print("SketchIn: No active document")
            return [[], [], []]
        
        # Try to find sketch by label
        objs = App.ActiveDocument.getObjectsByLabel(sketch_label)
        
        if len(objs) == 0:
            # Try by name instead
            obj = App.ActiveDocument.getObject(sketch_label)
            if obj is None:
                print(f"SketchIn: Sketch '{sketch_label}' not found")
                return [[], [], []]
            objs = [obj]
        
        sketch_obj = objs[0]
        
        # Check if it has a Shape
        if not hasattr(sketch_obj, 'Shape'):
            print(f"SketchIn: Object '{sketch_label}' has no Shape")
            return [[], [], [sketch_obj]]
        
        shape = sketch_obj.Shape
        
        # Get wire
        wire = None
        if hasattr(shape, 'Wires') and len(shape.Wires) > 0:
            wire = shape.Wires[0]
        elif hasattr(shape, 'Edges') and len(shape.Edges) > 0:
            try:
                wire = Part.Wire(shape.Edges)
            except:
                pass
        
        # Make face from wire
        face = None
        if wire is not None:
            try:
                face = Part.Face(wire)
                print(f"SketchIn: Created face from '{sketch_label}'")
            except Exception as e:
                print(f"SketchIn: Could not create face - {e}")
                print("Hint: Make sure sketch is closed (all lines connected)")
        
        # Return outputs: Face, Wire, Object
        face_out = [face] if face is not None else []
        wire_out = [wire] if wire is not None else []
        obj_out = [sketch_obj]
        
        return [face_out, wire_out, obj_out]


@register_node
class SketchFace(FCNNodeModel):
    """
    Sketch Face Node - Simplest way to get face from sketch
    
    Input:
        Type sketch label in the text box
    
    Output:
        Face: Face ready for extrusion
    
    Usage:
        [Sketch Face: "Sketch"] → [Extrude] → [CViewer]
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Sketch Face"
    op_category: str = "Scene"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[], 
                         outputs_init_list=[("Face", True)])

        self.grNode.resize(120, 70)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = SketchInputContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        sketch_label: str = str(self.content.edit.text())
        
        if App.ActiveDocument is None:
            print("SketchFace: No active document")
            return [[]]
        
        # Find sketch
        objs = App.ActiveDocument.getObjectsByLabel(sketch_label)
        if len(objs) == 0:
            obj = App.ActiveDocument.getObject(sketch_label)
            if obj is None:
                print(f"SketchFace: '{sketch_label}' not found")
                return [[]]
            objs = [obj]
        
        sketch_obj = objs[0]
        
        if not hasattr(sketch_obj, 'Shape'):
            print(f"SketchFace: '{sketch_label}' has no Shape")
            return [[]]
        
        shape = sketch_obj.Shape
        
        # Get wire and make face
        try:
            if hasattr(shape, 'Wires') and len(shape.Wires) > 0:
                face = Part.Face(shape.Wires[0])
                print(f"SketchFace: Created face from '{sketch_label}'")
                return [[face]]
        except Exception as e:
            print(f"SketchFace error: {e}")
        
        return [[]]