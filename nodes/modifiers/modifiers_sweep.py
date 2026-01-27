# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_sweep.py
#
#  Sweep Node for FreeCAD Nodes Workbench
#  Sweeps a profile along a path (spine)
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_sweep.py
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
class Sweep(FCNNodeModel):
    """
    Sweep Node - Sweeps a profile along a path
    
    Inputs:
        Profile: Wire/Shape to sweep (cross-section)
        Path: Wire/Edge to sweep along (spine)
        Solid: Create solid (True) or shell (False)
        Frenet: Use Frenet mode for orientation (True/False)
    
    Output:
        Shape: Swept shape
    
    Example:
        Circle (profile) + Helix (path) = Spring
        Rectangle (profile) + BSpline (path) = Curved beam 
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Sweep"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Path", True), ("Profile", True), ("Solid", True), ("Frenet", True)],
                         outputs_init_list=[("Shape", True)])
        
        self.grNode.resize(110, 110)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    @staticmethod
    def make_sweep(parameter_zip: tuple) -> Part.Shape:
        profile: Part.Shape = parameter_zip[0]
        path: Part.Shape = parameter_zip[1]
        solid: bool = parameter_zip[2] if len(parameter_zip) > 2 else True
        frenet: bool = parameter_zip[3] if len(parameter_zip) > 3 else True
        
        try:
            # Get wire from profile
            if hasattr(profile, 'Wires') and len(profile.Wires) > 0:
                profile_wire = profile.Wires[0]
            elif hasattr(profile, 'Edges') and len(profile.Edges) > 0:
                profile_wire = Part.Wire(profile.Edges)
            else:
                profile_wire = profile
            
            # Get wire from path
            if hasattr(path, 'Wires') and len(path.Wires) > 0:
                path_wire = path.Wires[0]
            elif hasattr(path, 'Edges') and len(path.Edges) > 0:
                path_wire = Part.Wire(path.Edges)
            else:
                path_wire = path
            
            # Create sweep
            # Method 1: Using makePipeShell
            sweep = Part.Wire(profile_wire).makePipeShell([path_wire], solid, frenet)
            
            return sweep
            
        except Exception as e:
            print(f"Sweep error (trying alternative method): {e}")
            
            try:
                # Method 2: Using makePipe
                if hasattr(profile, 'Wires') and len(profile.Wires) > 0:
                    sweep = profile.Wires[0].makePipe(path)
                else:
                    sweep = profile.makePipe(path)
                return sweep
                
            except Exception as e2:
                print(f"Sweep alternative error: {e2}")
                return profile
    
    def eval_operation(self, sockets_input_data: list) -> list:
        # Get socket inputs
        profile_input: list = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        path_input: list = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else []
        solid_input: list = sockets_input_data[2] if len(sockets_input_data[2]) > 0 else [True]
        frenet_input: list = sockets_input_data[3] if len(sockets_input_data[3]) > 0 else [True]
        
        # Need both profile and path
        if len(profile_input) == 0 or len(path_input) == 0:
            return [[]]
        
        # Broadcast and calculate result
        data_tree: list = list(broadcast_data_tree(profile_input, path_input, solid_input, frenet_input))
        sweeps: list = list(map_objects(data_tree, tuple, self.make_sweep))
        
        return [sweeps]