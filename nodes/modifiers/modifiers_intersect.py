# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_intersect.py
#
#  Boolean Intersect (Common) Node for FreeCAD Nodes Workbench
#  Returns common volume of two shapes
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_intersect.py
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
class Intersect(FCNNodeModel):

    icon: str = icon("nodes_default.png")
    op_title: str = "Intersect"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"

    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape A", True), ("Shape B", True)],
                         outputs_init_list=[("Shape", True)])

        self.grNode.resize(100, 80)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()

    @staticmethod
    def make_intersect(parameter_zip: tuple) -> Part.Shape:
        shape_a: Part.Shape = parameter_zip[0]
        shape_b: Part.Shape = parameter_zip[1]

        return shape_a.common(shape_b)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        shape_a_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        shape_b_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else []

        # If either input is empty, return empty
        if len(shape_a_input) == 0 or len(shape_b_input) == 0:
            return [[]]

        # Broadcast and calculate result
        data_tree: list = list(broadcast_data_tree(shape_a_input, shape_b_input))
        intersects: list = list(map_objects(data_tree, tuple, self.make_intersect))

        return [intersects]