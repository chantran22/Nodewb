# -*- coding: utf-8 -*-
###################################################################################
#
#  text_equation.py
#
#  Equation Node for FreeCAD Nodes Workbench
#  Evaluates math expressions and outputs float result
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/text/text_equation.py
#  2. Restart FreeCAD
#
###################################################################################
from collections import OrderedDict
import math

from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from qtpy.QtCore import Qt

from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel, FCNNodeContentView
from core.nodes_default_node import FCNNodeView

from nodes_locator import icon


# Safe math functions for equation evaluation
SAFE_MATH = {
    'sqrt': math.sqrt,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'abs': abs,
    'min': min,
    'max': max,
    'pow': pow,
    'round': round,
    'floor': math.floor,
    'ceil': math.ceil,
    'pi': math.pi,
    'e': math.e,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'radians': math.radians,
    'degrees': math.degrees,
}


def evaluate_equation(formula):
    """
    Safely evaluate a math formula.
    
    Args:
        formula: String like "(100 + 50) * 2" or "sqrt(16) + pi"
    
    Returns:
        Calculated result as float
    """
    try:
        result = eval(formula, {"__builtins__": {}}, SAFE_MATH)
        return float(result)
    except Exception as e:
        print(f"Equation error: {e}")
        return 0.0


class EquationContent(QDMNodeContentWidget):
    """Content widget with equation input"""
    
    layout: QLayout
    edit: QLineEdit

    def initUI(self):
        self.layout: QLayout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # Equation input - simple style like Number node
        self.edit: QLineEdit = QLineEdit("0", self)
        self.edit.setObjectName(self.node.content_label_objname)
        self.edit.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.edit)

    def serialize(self) -> OrderedDict:
        res: OrderedDict = super().serialize()
        res['equation'] = self.edit.text()
        return res

    def deserialize(self, data: dict, hashmap=None, restore_id: bool = True) -> bool:
        if hashmap is None:
            hashmap = {}

        res = super().deserialize(data, hashmap)
        try:
            equation = data.get('equation', '0')
            self.edit.setText(equation)
            return True & res
        except Exception as e:
            print(f"Deserialize error: {e}")
        return res


@register_node
class Equation(FCNNodeModel):
    """
    Equation Node - Evaluate math expressions
    
    Input Box:
        Type equation like: (100 + 50) * 2
    
    Output:
        Out: Result as float number
    
    Supported:
        +, -, *, /, ** (power)
        sqrt, sin, cos, tan, asin, acos, atan
        abs, min, max, pow, round, floor, ceil
        log, log10, exp, radians, degrees
        pi, e (constants)
    
    Examples:
        100 + 50
        sqrt(16) * 2
        sin(radians(45)) * 100
        5000*cos(10*pi/180)
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Equation"
    op_category: str = "Text"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[], 
                         outputs_init_list=[("Out", True)])

        self.grNode.resize(140, 55)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = EquationContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.edit.textChanged.connect(self.onInputChanged)

    def eval_operation(self, sockets_input_data: list) -> list:
        formula: str = str(self.content.edit.text())
        result = evaluate_equation(formula)
        return [[result]]


@register_node
class EquationVar(FCNNodeModel):
    """
    Equation with Variables - Use a, b, c, d from inputs
    
    Inputs:
        a, b, c, d: Number values (optional)
    
    Input Box:
        Type equation using a, b, c, d
        Example: (a + b) * c
    
    Output:
        Out: Result as float
    """

    icon: str = icon("nodes_default.png")
    op_title: str = "Equation Var"
    op_category: str = "Text"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene, 
                         inputs_init_list=[("a", True), ("b", True), ("c", True), ("d", True)],
                         outputs_init_list=[("Out", True)])

        self.grNode.resize(140, 130)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    def initInnerClasses(self):
        self.content: QDMNodeContentWidget = EquationContent(self)
        self.grNode: QDMGraphicsNode = FCNNodeView(self)
        self.content.edit.textChanged.connect(self.onInputChanged)
        self.content.edit.setText("a + b")  # Default formula

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get variable values from inputs
        a = float(sockets_input_data[0][0]) if len(sockets_input_data[0]) > 0 else 0.0
        b = float(sockets_input_data[1][0]) if len(sockets_input_data[1]) > 0 else 0.0
        c = float(sockets_input_data[2][0]) if len(sockets_input_data[2]) > 0 else 0.0
        d = float(sockets_input_data[3][0]) if len(sockets_input_data[3]) > 0 else 0.0
        
        formula: str = str(self.content.edit.text())
        
        # Add variables to safe dict
        variables = {'a': a, 'b': b, 'c': c, 'd': d}
        safe_dict = {**SAFE_MATH, **variables}
        
        try:
            result = eval(formula, {"__builtins__": {}}, safe_dict)
            return [[float(result)]]
        except Exception as e:
            print(f"EquationVar error: {e}")
            return [[0.0]]