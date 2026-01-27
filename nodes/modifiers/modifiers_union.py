# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_union.py
#
#  Boolean Union (Fuse) Node for FreeCAD Nodes Workbench
#  Combines two shapes into one
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_union.py
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
class Union(FCNNodeModel):

    icon: str = icon("nodes_default.png")
    op_title: str = "Union"
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
    def make_union(parameter_zip: tuple) -> Part.Shape:
        shape_a: Part.Shape = parameter_zip[0]
        shape_b: Part.Shape = parameter_zip[1]

        return shape_a.fuse(shape_b)

    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        shape_a_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        shape_b_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else []

        # If either input is empty, return the other
        if len(shape_a_input) == 0:
            return [shape_b_input]
        if len(shape_b_input) == 0:
            return [shape_a_input]

        # Broadcast and calculate result
        data_tree: list = list(broadcast_data_tree(shape_a_input, shape_b_input))
        unions: list = list(map_objects(data_tree, tuple, self.make_union))

        return [unions]