# -*- coding: utf-8 -*-
###################################################################################
#
#  modifiers_make_solid.py
#
#  Make Solid Node for FreeCAD Nodes Workbench
#  Converts closed shell/faces into solid
#
#  INSTALLATION:
#  1. Save as: FreeCAD/Mod/Nodes/nodes/modifiers/modifiers_make_solid.py
#  2. Restart FreeCAD
#
#  USAGE:
#     [Thickness] → [Make Solid] → [CViewer]
#
###################################################################################

import FreeCAD as App
from FreeCAD import Vector
import Part

from core.nodes_conf import register_node
from core.nodes_default_node import FCNNodeModel
from core.nodes_utils import flatten

from nodes_locator import icon


@register_node
class MakeSolid(FCNNodeModel):
    """
    Make Solid Node - Convert closed shell/faces to solid
    
    Inputs:
        Shape: Shell or shape with closed faces
    
    Output:
        Solid: Converted solid shape
    
    Use after Thickness or other operations that create shells instead of solids.
    
    Methods tried (in order):
        1. makeSolid() - Standard conversion
        2. sewShape() + makeSolid() - Sew gaps first
        3. makeShell() + makeSolid() - Rebuild shell
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Make Solid"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True)],
                         outputs_init_list=[("Solid", True)])
        
        self.grNode.resize(110, 55)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        
        shape_list = list(flatten(shape_input))
        if len(shape_list) == 0:
            print("MakeSolid: No input shape")
            return [[]]
        
        results = []
        
        for shape in shape_list:
            solid = self.convert_to_solid(shape)
            if solid is not None:
                results.append(solid)
        
        return [results] if results else [[]]
    
    def convert_to_solid(self, shape):
        """Try multiple methods to convert shape to solid"""
        try:
            # Get Part.Shape from FreeCAD object
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Already a solid?
            if isinstance(shape, Part.Solid):
                print("MakeSolid: Already a solid")
                return shape
            
            if hasattr(shape, 'Solids') and len(shape.Solids) > 0:
                print(f"MakeSolid: Shape has {len(shape.Solids)} solid(s)")
                if len(shape.Solids) == 1:
                    return shape.Solids[0]
                else:
                    return Part.makeCompound(shape.Solids)
            
            # Method 1: Direct makeSolid
            try:
                solid = Part.makeSolid(shape)
                if solid.isValid():
                    print("MakeSolid: Success with makeSolid()")
                    return solid
            except Exception as e:
                print(f"MakeSolid: makeSolid() failed: {e}")
            
            # Method 2: Get shell and convert
            if hasattr(shape, 'Shells') and len(shape.Shells) > 0:
                for shell in shape.Shells:
                    try:
                        solid = Part.makeSolid(shell)
                        if solid.isValid():
                            print("MakeSolid: Success with shell.makeSolid()")
                            return solid
                    except:
                        pass
            
            # Method 3: Sew faces first, then make solid
            try:
                if hasattr(shape, 'Faces') and len(shape.Faces) > 0:
                    # Create shell from faces
                    shell = Part.makeShell(shape.Faces)
                    
                    # Sew the shell
                    shell.sewShape()
                    
                    # Try to make solid
                    solid = Part.makeSolid(shell)
                    if solid.isValid():
                        print("MakeSolid: Success with sewShape() + makeSolid()")
                        return solid
            except Exception as e:
                print(f"MakeSolid: Sew method failed: {e}")
            
            # Method 4: Use BOPTools
            try:
                from BOPTools import BOPFeatures
                solid = BOPFeatures.makeSolid(shape)
                if solid and solid.isValid():
                    print("MakeSolid: Success with BOPFeatures")
                    return solid
            except:
                pass
            
            # Method 5: Fix and convert
            try:
                fixed = shape.copy()
                fixed.fix(0.01, 0.01, 0.01)  # tolerance for fixing
                solid = Part.makeSolid(fixed)
                if solid.isValid():
                    print("MakeSolid: Success with fix() + makeSolid()")
                    return solid
            except Exception as e:
                print(f"MakeSolid: Fix method failed: {e}")
            
            print("MakeSolid: All methods failed, returning original shape")
            return shape
            
        except Exception as e:
            print(f"MakeSolid error: {e}")
            import traceback
            traceback.print_exc()
            return shape


@register_node
class ShellToSolid(FCNNodeModel):
    """
    Shell to Solid Node - Convert shell to solid with tolerance
    
    Inputs:
        Shape: Shell shape
        Tolerance: Sewing tolerance (default 0.01)
    
    Output:
        Solid: Converted solid
    
    Use when MakeSolid fails - allows adjusting tolerance for sewing gaps.
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Shell to Solid"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True), ("Tolerance", True)],
                         outputs_init_list=[("Solid", True)])
        
        self.grNode.resize(120, 75)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        tol_input = sockets_input_data[1] if len(sockets_input_data[1]) > 0 else [0.01]
        
        tolerance = float(tol_input[0]) if len(tol_input) > 0 else 0.01
        
        shape_list = list(flatten(shape_input))
        if len(shape_list) == 0:
            return [[]]
        
        results = []
        
        for shape in shape_list:
            solid = self.shell_to_solid(shape, tolerance)
            if solid is not None:
                results.append(solid)
        
        return [results] if results else [[]]
    
    def shell_to_solid(self, shape, tolerance):
        """Convert shell to solid with specified tolerance"""
        try:
            if hasattr(shape, 'Shape'):
                shape = shape.Shape
            
            # Get faces
            if hasattr(shape, 'Faces') and len(shape.Faces) > 0:
                faces = shape.Faces
            else:
                print("ShellToSolid: No faces found")
                return shape
            
            # Make shell from faces
            shell = Part.makeShell(faces)
            
            # Sew with tolerance
            shell.sewShape(tolerance)
            
            # Make solid
            solid = Part.makeSolid(shell)
            
            if solid.isValid():
                print(f"ShellToSolid: Success with tolerance={tolerance}")
                return solid
            else:
                print("ShellToSolid: Result not valid, returning shell")
                return shell
                
        except Exception as e:
            print(f"ShellToSolid error: {e}")
            return shape


@register_node
class CheckSolid(FCNNodeModel):
    """
    Check Solid Node - Check if shape is solid and get info
    
    Inputs:
        Shape: Shape to check
    
    Outputs:
        IsSolid: 1 if solid, 0 if not
        Volume: Volume of shape
        Info: Shape type info
    
    Useful for debugging geometry issues.
    """
    
    icon: str = icon("nodes_default.png")
    op_title: str = "Check Solid"
    op_category: str = "Modifiers"
    content_label_objname: str = "fcn_node_bg"
    
    def __init__(self, scene):
        super().__init__(scene=scene,
                         inputs_init_list=[("Shape", True)],
                         outputs_init_list=[("IsSolid", True), ("Volume", True), ("Faces", True)])
        
        self.grNode.resize(110, 75)
        for socket in self.inputs + self.outputs:
            socket.setSocketPosition()
    
    def eval_operation(self, sockets_input_data: list) -> list:
        shape_input = sockets_input_data[0] if len(sockets_input_data[0]) > 0 else []
        
        shape_list = list(flatten(shape_input))
        if len(shape_list) == 0:
            return [[0], [0], [0]]
        
        shape = shape_list[0]
        if hasattr(shape, 'Shape'):
            shape = shape.Shape
        
        # Check type
        is_solid = 0
        volume = 0
        num_faces = 0
        
        try:
            if isinstance(shape, Part.Solid):
                is_solid = 1
                print("CheckSolid: Shape IS a solid")
            elif hasattr(shape, 'Solids') and len(shape.Solids) > 0:
                is_solid = 1
                print(f"CheckSolid: Shape contains {len(shape.Solids)} solid(s)")
            else:
                is_solid = 0
                shape_type = type(shape).__name__
                print(f"CheckSolid: Shape is NOT a solid, type={shape_type}")
            
            # Get volume
            if hasattr(shape, 'Volume'):
                volume = shape.Volume
                print(f"CheckSolid: Volume = {volume:.2f}")
            
            # Get face count
            if hasattr(shape, 'Faces'):
                num_faces = len(shape.Faces)
                print(f"CheckSolid: Faces = {num_faces}")
            
            # Check if closed
            if hasattr(shape, 'Shells'):
                for i, shell in enumerate(shape.Shells):
                    if hasattr(shell, 'isClosed'):
                        closed = shell.isClosed()
                        print(f"CheckSolid: Shell {i} isClosed = {closed}")
                        
        except Exception as e:
            print(f"CheckSolid error: {e}")
        
        return [[is_solid], [volume], [num_faces]]