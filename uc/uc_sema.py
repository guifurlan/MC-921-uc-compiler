import argparse
import pathlib
import sys
from uc.uc_ast import *
from uc.uc_parser import UCParser
from uc.uc_type import CharType, FloatType, IntType, StringType, BoolType, VoidType, FunctionType, ArrayType

class SymbolTable(dict):
    """Class representing a symbol table. It should provide functionality
    for adding and looking up nodes associated with identifiers.
    """

    def __init__(self):
        super().__init__()

    def add(self, name, value, scope):
        self[(name, scope)] = value

    def lookup(self, name, scope):
        return self.get((name, scope), None)


class NodeVisitor:
    """A base NodeVisitor class for visiting uc_ast nodes.
    Subclass it and define your own visit_XXX methods, where
    XXX is the class name you want to visit with these
    methods.
    """

    _method_cache = None

    def visit(self, node):
        """Visit a node."""

        if self._method_cache is None:
            self._method_cache = {}

        visitor = self._method_cache.get(node.__class__.__name__, None)
        if visitor is None:
            method = "visit_" + node.__class__.__name__
            visitor = getattr(self, method, self.generic_visit)
            self._method_cache[node.__class__.__name__] = visitor

        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a
        node. Implements preorder visiting of the node.
        """
        for _, child in node.children():
            self.visit(child)


class Visitor(NodeVisitor):
    """
    Program visitor class. This class uses the visitor pattern. You need to define methods
    of the form visit_NodeName() for each kind of AST node that you want to process.
    """

    def __init__(self):
        # Initialize the symbol table
        self.symtab = SymbolTable()
        self.global_scope = 0
        self.typemap = {
            "int": IntType,
            "float": FloatType,
            "char": CharType,
            "string": StringType,
            "void": VoidType,
            "bool": BoolType,
        }
        self.local_scope = 0
        # TODO: Complete...

    def _assert_semantic(self, condition, msg_code, coord, name="", ltype="", rtype=""):
        """Check condition, if false print selected error message and exit"""
        error_msgs = {
            1: f"{name} is not defined",
            2: f"{ltype} must be of type(int)",
            3: "Expression must be of type(bool)",
            4: f"Cannot assign {rtype} to {ltype}",
            5: f"Assignment operator {name} is not supported by {ltype}",
            6: f"Binary operator {name} does not have matching LHS/RHS types",
            7: f"Binary operator {name} is not supported by {ltype}",
            8: "Break statement must be inside a loop",
            9: "Array dimension mismatch",
            10: f"Size mismatch on {name} initialization",
            11: f"{name} initialization type mismatch",
            12: f"{name} initialization must be a single element",
            13: "Lists have different sizes",
            14: "List & variable have different sizes",
            15: f"conditional expression is {ltype}, not type(bool)",
            16: f"{name} is not a function",
            17: f"no. arguments to call {name} function mismatch",
            18: f"Type mismatch with parameter {name}",
            19: "The condition expression must be of type(bool)",
            20: "Expression must be a constant",
            21: "Expression is not of basic type",
            22: f"{name} does not reference a variable of basic type",
            23: f"\n{name}\nIs not a variable",
            24: f"Return of {ltype} is incompatible with {rtype} function definition",
            25: f"Name {name} is already defined in this scope",
            26: f"Unary operator {name} is not supported",
            27: "Undefined error",
        }
        if not condition:
            msg = error_msgs.get(msg_code)
            print("SemanticError: %s %s" % (msg, coord), file=sys.stdout)
            sys.exit(1)

    def visit_Program(self, node):
        # Visit all of the global declarations
        for _decl in node.gdecls:
            self.visit(_decl)

    def visit_FuncDef(self, node):  # 'spec', 'decl', 'param_decls', 'statements', 'coord'
        # Initialize the list of declarations that appears inside loops. Save the reference to current function.
        # Visit the return type of the Function, the function declaration, the parameters, and the function body.
        self.visit(node.spec)  # function type
        self.visit(node.decl)  # declaration
        
        if (node.param_decls):
            self.visit(node.param_decls)

        self.visit(node.statements)
        if node.statements.block_items is None:
            self._assert_semantic(node.spec.name == 'void', 24, node.statements.coord, ltype='type(void)', rtype='type('+node.spec.name+')')
        else:
            for statement in node.statements.block_items:
                if (isinstance(statement, Return)):
                    return_type = self.visit(statement)
                    self._assert_semantic(node.spec.name == return_type.typename, 24, statement.coord, ltype=return_type, rtype='type('+node.spec.name+')')

    def visit_ParamList(self, node): # 'params', 'coord'
        # Just visit all parameters.
        for param in node.params:
            self.visit(param)

    def visit_GlobalDecl(self, node):
        # Just visit each global declaration.
        for _decl in node.decls:
            self.visit(_decl)

    def visit_Decl(self, node):  # 'name', 'type' [VarDecl, ArrayDecl, FuncDecl], 'init', 'coord'
        # Visit the types of the declaration (VarDecl, ArrayDecl, FuncDecl).
        # Check if the function or the variable is defined, otherwise return an error. If there is an initial value defined, visit it.
     
        if isinstance(node.type, ArrayDecl):
            (var_type, arr_dims) = self.visit(node.type)
            var_name = node.name.name
            var_coord = node.name.coord

            if self.local_scope > 0:
                var_lookup = self.symtab.lookup(var_name, self.local_scope)
                if var_lookup is None:
                    var_lookup = self.symtab.lookup(var_name, self.global_scope)
            else:
                var_lookup = self.symtab.lookup(var_name, self.global_scope)
            if var_lookup is None:
                var_lookup = self.symtab.lookup(var_name, 0)
            
            self._assert_semantic(
                (var_lookup is None),
                25,
                var_coord,
                name=var_name
            )

            if (node.init):
                if isinstance(node.init, Constant):  # 'type', 'value'
                    if (node.init.type == 'string'):
                        if (arr_dims[0] is None):
                            arr_dims[0] = len(node.init.value)
                        # Verify init length with array size
                        self._assert_semantic(arr_dims[0] == len(node.init.value), 10, var_coord, name=var_name)
                        # Verify if array is type char
                        self._assert_semantic(var_type.typename == 'char', 11,var_coord, name=var_name)
                    
                elif isinstance(node.init, ID): # 'name', 'coord'
                    self.visit(node.init)
                else:
                    if (arr_dims[0] is None):
                        arr_dims[0] = len(node.init.exprs)
                    # Verify init length with array size
                    self._assert_semantic(int(arr_dims[0]) == len(node.init.exprs), 14, var_coord)
                    
                    for expr in node.init.exprs:
                        # Verify if expr is a constant
                        self._assert_semantic(isinstance(expr, Constant), 20, expr.coord)
                        # Verify if init value matches array type
                        const_type = expr.type
                        self._assert_semantic(var_type.typename == const_type, 11, var_coord, name=var_name)
            elif len(arr_dims) > 1:
                self._assert_semantic(arr_dims[0] is not None, 9, var_coord)
            var_type = ArrayType(node.type.type, arr_dims)
            node.type.size = arr_dims[0]
        else:
            var_type = self.visit(node.type)
            var_name = node.name.name
            var_coord = node.name.coord
            
            if self.local_scope > 0:
                var_lookup = self.symtab.lookup(var_name, self.local_scope)
                if var_lookup is None:
                    var_lookup = self.symtab.lookup(var_name, self.global_scope)
            else:
                var_lookup = self.symtab.lookup(var_name, self.global_scope)
            if var_lookup is None:
                var_lookup = self.symtab.lookup(var_name, 0)

            self._assert_semantic(
                var_lookup is None,
                25,
                var_coord,
                name=var_name
            )

            if node.init:
                self._assert_semantic(not isinstance(node.init, InitList), 12, var_coord, name=var_name)
                if isinstance(node.init, Constant):  # 'type', 'value'
                    const_type = node.init.type
                    self._assert_semantic(
                        var_type.typename == const_type,
                        11,
                        var_coord,
                        name=var_name
                    )
                elif isinstance(node.init, ID): # 'name', 'coord'
                    self.visit(node.init)
                elif isinstance(node.init, BinaryOp):
                    self.visit(node.init)
                elif isinstance(node.init, UnaryOp):
                    self.visit(node.init)
                elif isinstance(node.init, FuncCall):
                    self.visit(node.init)

        if self.local_scope > 0:
            self.symtab.add(var_name, var_type, self.local_scope)
        else:
            self.symtab.add(var_name, var_type, self.global_scope)

    def visit_VarDecl(self, node):  # 'declname', 'type'
        # First visit the type to adjust the list of types to uCType objects. 
        # Then, get the name of variable and make sure it is not defined in the current scope, otherwise return an error.
        # Next, insert its identifier in the symbol table. Finally, copy the type to the identifier.
        self.visit(node.type)
        var_type = self.typemap[node.type.name]
        return var_type

    def visit_ArrayDecl(self, node): # "type", "size", "coord"
        # First visit the type to adjust the list of types to uCType objects. Array is a modifier type, so append this info in the ID object.
        # Visit the array dimension if defined else the dim will be infered after visit initialization in Decl object.
        arr_dims = []
        if (isinstance(node.type, VarDecl)):
            arr_type = self.visit(node.type)
        else:
            (arr_type, arr_dims) = self.visit(node.type)

        arr_dims.append(node.size if node.size is None else node.size.value)
        return (arr_type, arr_dims)

    def visit_FuncDecl(self, node):  # 'args', 'type'
        # Start by visiting the type. Add the function to the symbol table. Then, visit the arguments. Create the type of the function using its return type and the type of its arguments.
        # Then, visit the arguments. Create the type of the function using its return type and the type of its arguments.
        self.global_scope += 1
        self.visit(node.type)
        if (node.args):
            for arg in node.args:
                self.visit(arg)
        var_type = FunctionType(node.type, node.args)
        return var_type

    def visit_DeclList(self, node): # 'decls', 'coord'
        # Visit all of the declarations that appear inside the statement.
        # Append the declaration to the list of decls in the current function.
        # This list will be used by the code generation to allocate the variables.
        for decl in node.decls:
            self.visit(decl)

    def visit_Type(self, node):  # 'name'
        # Get the matching basic uCType.
        pass

    def visit_If(self, node): # 'cond', 'if_statements', 'else_statements', 'coord'
        # First, visit the condition. Then, check if the conditional expression is of boolean type or return a type error.
        # Finally, visit the statements related to the then, and to the else (in case there are any).
        cond_type = self.visit(node.cond)
        if isinstance(node.cond, Constant):
            self._assert_semantic(node.cond.type == 'bool', 19, node.cond.coord)
        elif isinstance(node.cond, ID):
            self._assert_semantic(cond_type == BoolType, 19, node.cond.coord)
        elif isinstance(node.cond, BinaryOp):
            self._assert_semantic(cond_type == BoolType, 19, node.cond.coord)
        elif isinstance(node.cond, UnaryOp):
            self._assert_semantic(node.cond.op in BoolType.unary_ops, 19, node.cond.coord)
        elif isinstance(node.cond, Assignment):
            self._assert_semantic(not isinstance(node.cond, Assignment), 19, node.cond.coord)

        self.visit(node.if_statements)
        if node.else_statements is not None: self.visit(node.else_statements)

    def visit_For(self, node):  # 'init', 'cond', 'next', 'statements', 'coord'
        self.local_scope = self.global_scope + 1

        if isinstance(node.init, DeclList):
            for decl in node.init.decls:
                var_type = self.visit(decl.type)
                var_name = decl.name.name
                self.symtab.add(var_name, var_type, self.local_scope)
        elif isinstance(node.init, Assignment):
            self.visit(node.init)

        self.visit(node.cond)
        self.visit(node.next)
        self.visit(node.statements)
        self.local_scope = 0
        
    def visit_While(self, node): # 'cond', 'statements', 'coord'
        # First, append the current loop node to the dedicated list attribute used to bind the node to nested break statement.
        # Then, visit the condition and check if the conditional expression is of boolean type or return a type error.
        # Finally, visit the body of the while (stmt).
        cond_type = self.visit(node.cond)
        if isinstance(node.cond, Constant):
            self._assert_semantic(node.cond.type == 'bool', 15, node.coord, ltype='type('+node.cond.type+')')
        if isinstance(node.cond, ID):
            self._assert_semantic(cond_type == BoolType, 15, node.coord, ltype='type('+node.cond.type+')')
        elif isinstance(node.cond, BinaryOp):
            self._assert_semantic(cond_type == BoolType, 15, node.coord, ltype=cond_type)
        elif isinstance(node.cond, UnaryOp):
            self._assert_semantic(node.cond.op in BoolType.unary_ops, 15, node.coord, ltype=cond_type)
        
        self.visit(node.statements)

    def visit_Compound(self, node): # 'block_items', 'coord'
        # Visit the list of block items (declarations or statements).
        if (node.block_items):
            for block_item in node.block_items:
                self.visit(block_item)

    def visit_Break(self, node):
        self._assert_semantic(self.local_scope > 0, 8, node.coord)

    def visit_FuncCall(self, node):  # 'name', 'args', 'coord'
        for scope in range(0, self.global_scope + 1):
            func_lookup = self.symtab.lookup(node.name.name, scope)
            if func_lookup is not None:
                break
        self._assert_semantic(func_lookup is not None, 1, node.coord, name=node.name.name)
        

        # Verify if name is a function
        self._assert_semantic(isinstance(func_lookup, FunctionType), 16, node.coord, name=node.name.name)

        # Verify if number of args called is the same as function args
        if (func_lookup.params or node.args):
            func_args = func_lookup.params.params
            if isinstance(node.args, ExprList):
                call_args = node.args.exprs
                self._assert_semantic(len(func_args) == len(call_args), 17, node.coord, node.name.name)
                for i in range(len(call_args)):
                    if isinstance(call_args[i], Constant):
                        call_arg_type = call_args[i].type
                    elif isinstance(call_args[i], BinaryOp):
                        call_arg_type = self.visit(call_args[i]).typename
                    else:
                        if self.local_scope > 0:
                            call_arg_type = self.symtab.lookup(call_args[i].name, self.local_scope)
                            if call_arg_type is None:
                                call_arg_type = self.symtab.lookup(call_args[i].name, self.global_scope)
                        else:
                            call_arg_type = self.symtab.lookup(call_args[i].name, self.global_scope)
                        if call_arg_type is None:
                            call_arg_type = self.symtab.lookup(call_args[i].name, 0)
                        call_args[i].type = call_arg_type
                        call_arg_type = call_arg_type.typename

                    self._assert_semantic(func_args[i].type.type.name == call_arg_type, 18, call_args[i].coord, name=func_args[i].name.name)
            else:
                self._assert_semantic(len(func_args) == 1, 17, node.coord, node.name.name)
                if isinstance(node.args, Constant):
                    call_arg_type = node.args.type
                elif isinstance(node.args, BinaryOp):
                    call_arg_type = self.visit(node.args).typename
                else:
                    if self.local_scope > 0:
                        call_arg_type = self.symtab.lookup(node.args.name, self.local_scope)
                        if call_arg_type is None:
                            call_arg_type = self.symtab.lookup(node.args.name, self.global_scope)
                    else:
                        call_arg_type = self.symtab.lookup(node.args.name, self.global_scope)
                    if call_arg_type is None:
                        call_arg_type = self.symtab.lookup(node.args.name, 0)
                    node.args.type = call_arg_type
                    call_arg_type = call_arg_type.typename

                self._assert_semantic(func_args[0].type.type.name == call_arg_type, 18, node.args.coord, name=func_args[0].name.name)
            
        func_type = func_lookup.type.type.name
        node.name.type = func_type
        return self.typemap[func_type]

    def visit_Assert(self, node): # 'expr', 'coord'
        expr_type = self.visit(node.expr)
        self._assert_semantic(expr_type == BoolType, 3, coord=node.expr.coord)

    def visit_EmptyStatement(self, node):
        pass

    def visit_Print(self, node):
        if node.expr:
            expr_type = self.visit(node.expr)
            if isinstance(node.expr, ID):
                if self.local_scope > 0:
                    expr_type = self.symtab.lookup(node.expr.name, self.local_scope)
                    if expr_type is None:
                        expr_type = self.symtab.lookup(node.expr.name, self.global_scope)
                else:
                    expr_type = self.symtab.lookup(node.expr.name, self.global_scope)
                if expr_type is None:
                    expr_type = self.symtab.lookup(node.expr.name, 0)
                self._assert_semantic(
                    not isinstance(expr_type, FunctionType)
                    and not isinstance(expr_type, ArrayType)
                    and expr_type != VoidType,
                    22, node.expr.coord, name=node.expr.name
                )
            else:
                self._assert_semantic(
                        not isinstance(expr_type, FunctionType)
                        and not isinstance(expr_type, ArrayType)
                        and expr_type != VoidType,
                        21, node.expr.coord
                    )
            
    def visit_Read(self, node):
        self.visit(node.expr)
        self._assert_semantic(isinstance(node.expr, ID) or isinstance(node.expr, ExprList) or isinstance(node.expr, ArrayRef), 23, node.expr.coord, name=node.expr)

    def visit_Return(self, node):
        if node.expr is not None:
            return self.visit(node.expr)

        return VoidType

    def visit_Constant(self, node): # "type", "value"
        var_type = self.typemap[node.type]
        return var_type

    def visit_ID(self, node):
        if self.local_scope > 0:
            id_lookup = self.symtab.lookup(node.name, self.local_scope)
            if id_lookup is None:
                id_lookup = self.symtab.lookup(node.name, self.global_scope)
        else:
            id_lookup = self.symtab.lookup(node.name, self.global_scope)
        if id_lookup is None:
            id_lookup = self.symtab.lookup(node.name, 0)
        self._assert_semantic(id_lookup is not None, 1, node.coord, name=node.name)
        node.type = id_lookup
        return id_lookup

    def visit_Cast(self, node):  # 'type_cast', 'expr', 'coord'
        self.visit(node.type_cast)
        self.visit(node.expr)
        return self.typemap[node.type_cast.name]
        

    def visit_UnaryOp(self, node): # 'op', 'expr', 'coord'
        expr_type = self.visit(node.expr)
        self._assert_semantic(node.op in expr_type.unary_ops, 26, node.coord, name=node.op)
        return expr_type

    def visit_ExprList(self, node): # 'exprs', 'coord'
        for expr in node.exprs:
            self.visit(expr)

    def visit_ArrayRef(self, node): # 'name', 'subscript', 'coord'
        subscript_type = self.visit(node.subscript)
        self._assert_semantic(subscript_type == IntType, 2, node.subscript.coord, ltype=subscript_type)
        node.type = self.visit(node.name)
        return subscript_type

    def visit_InitList(self, node):  # 'exprs', 'coord'
        # Visit each element of the list. If they are scalar (not InitList), verify they are constants or return an error.
        for elem in node.exprs:
            self.visit(elem)
            self._assert_semantic(isinstance(elem, InitList), 20, node.coord)

    def visit_BinaryOp(self, node):
        # Visit the left and right expression
        ltype = self.visit(node.lvalue)
        rtype = self.visit(node.rvalue)
        #  Make sure left and right operands have the same type
        self._assert_semantic(rtype == ltype, 6, node.coord, name=node.op)
        # Make sure the operation is supported
        self._assert_semantic(node.op in ltype.rel_ops or node.op in ltype.binary_ops, 7, node.coord, name=node.op, ltype=ltype)
        # Assign the result type
        if (node.op in ltype.rel_ops):
            node.type = BoolType
            return BoolType
        
        node.type = ltype
        return ltype

    def visit_Assignment(self, node):
        # visit right side
        rtype = self.visit(node.rvalue)
        # visit left side (must be a location)
        ltype = self.visit(node.lvalue)
        # Check that assignment is allowed
        self._assert_semantic(ltype == rtype, 4, node.coord,
                              ltype=ltype, rtype=rtype)
        # Check that assign_ops is supported by the type
        self._assert_semantic(node.op in ltype.assign_ops, 5, node.coord, name=node.op, ltype=ltype)


if __name__ == "__main__":

    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file", help="Path to file to be semantically checked", type=str
    )
    args = parser.parse_args()

    # get input path
    input_file = args.input_file
    input_path = pathlib.Path(input_file)

    # check if file exists
    if not input_path.exists():
        print("Input", input_path, "not found", file=sys.stderr)
        sys.exit(1)

    # set error function
    p = UCParser()
    # open file and parse it
    with open(input_path) as f:
        ast = p.parse(f.read())
        sema = Visitor()
        sema.visit(ast)
