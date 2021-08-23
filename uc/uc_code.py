import argparse
import pathlib
import sys
from uc.uc_ast import FuncDef, VarDecl, ArrayRef, ArrayDecl, FuncDecl, ExprList, FuncCall, ID, Constant
from uc.uc_block import CFG, BasicBlock, ConditionBlock, format_instruction, EmitBlocks
from uc.uc_interpreter import Interpreter
from uc.uc_parser import UCParser
from uc.uc_sema import NodeVisitor, Visitor


class CodeGenerator(NodeVisitor):
    """
    Node visitor class that creates 3-address encoded instruction sequences
    with Basic Blocks & Control Flow Graph.
    """

    def __init__(self, viewcfg):
        self.viewcfg = viewcfg
        self.current_block = None

        # version dictionary for temporaries. We use the name as a Key
        self.fname = "_glob_"
        self.versions = {self.fname: 0}

        # The generated code (list of tuples)
        # At the end of visit_program, we call each function definition to emit
        # the instructions inside basic blocks. The global instructions that
        # are stored in self.text are appended at beginning of the code
        self.code = []

        self.text = []  # Used for global declarations & constants (list, strings)

        self.return_key = None
        self.function_type = None

        self.for_count = 0
        self.while_count = 0
        self.if_count = 0
        self.current_break = None
        # TODO: Complete if needed.

    def show(self, buf=sys.stdout):
        _str = ""
        for _code in self.code:
            _str += format_instruction(_code) + "\n"
        buf.write(_str)

    def new_temp(self):
        """
        Create a new temporary variable of a given scope (function name).
        """
        if self.fname not in self.versions:
            self.versions[self.fname] = 1
        name = "%" + "%d" % (self.versions[self.fname])
        self.versions[self.fname] += 1
        return name

    def new_text(self, typename):
        """
        Create a new literal constant on global section (text).
        """
        name = "@." + typename + "." + "%d" % (self.versions["_glob_"])
        self.versions["_glob_"] += 1
        return name

    # You must implement visit_Nodename methods for all of the other
    # AST nodes.  In your code, you will need to make instructions
    # and append them to the current block code list.
    #
    # A few sample methods follow. Do not hesitate to complete or change
    # them if needed.

    def cast_value(self, var_type, var_value):
        if var_type == 'int':
            var_value = int(var_value)
        elif var_type == 'float':
            var_value = float(var_value)
        return var_value

    def visit_ID(self, node):
        var_name = '@' + node.name
        _isglobal = False
        for global_var in self.text:
            if var_name == global_var[1]:
                _isglobal = True
                break
        if not _isglobal:
            var_name = '%' + node.name

        temp_name = self.new_temp()
        inst = ("load_" + node.type.typename, var_name, temp_name)

        self.current_block.append(inst)
        node.gen_location = temp_name

    def visit_ArrayRef(self, node): # ('name', 'subscript', 'type', 'coord', 'gen_location')
        var_name = '@' + node.name.name
        _isglobal = False
        for global_var in self.text:
            if global_var[1] == var_name:
                _isglobal = True
                break
        if not _isglobal:
            var_name = '%' + node.name.name

        self.visit(node.subscript)

        temp_name = self.new_temp()
        inst = ('elem_' + node.type.type.type.name, var_name, node.subscript.gen_location, temp_name)
        self.current_block.append(inst)

        load_name = self.new_temp()
        inst = ('load_' + node.type.type.type.name + '_*', temp_name, load_name)
        self.current_block.append(inst)
        
        node.gen_location = load_name

    def visit_ArrayDecl(self, node):  # ('type', 'size', 'coord', 'gen_location')
        self.visit(node.type)

    def visit_Constant(self, node):  # ("type", "value", "uc_type", "gen_location")
        if node.type == "string":
            _target = self.new_text("str")
            inst = ("global_string", _target, node.value)
            self.text.append(inst)
        else:
            # Create a new temporary variable name
            _target = self.new_temp()
            # Make the SSA opcode and append to list of generated instructions
            inst = ("literal_" + node.type, self.cast_value(node.type, node.value), _target)
            self.current_block.append(inst)
        # Save the name of the temporary variable where the value was placed
        node.gen_location = _target

    def visit_Cast(self, node):  # ('type_cast', 'expr', 'coord', 'gen_location')
        self.visit(node.expr)

        _target = self.new_temp()
        if (node.type_cast.name == 'int'):
            inst = ('fptosi', node.expr.gen_location, _target) 
            self.current_block.append(inst)
        else:
            inst = ('sitofp', node.expr.gen_location, _target) 
            self.current_block.append(inst)
        
        node.gen_location = _target

    def visit_BinaryOp(self, node):  # ("op", "lvalue", "rvalue", "gen_location")
        # Visit the left and right expressions
        self.visit(node.rvalue)
        self.visit(node.lvalue)

        if isinstance(node.lvalue, ArrayRef):
            _ltype = node.lvalue.type.type.type.name
        elif isinstance(node.lvalue, FuncCall):
            _ltype = node.lvalue.name.type
        else:
            _ltype = node.lvalue.type.typename
        
        binary_ops = {
            '+': 'add',
            '*': 'mul',
            '-': 'sub',
            '/': 'div',
            '%': 'mod',
            '<': 'lt',
            '<=': 'le',
            '>=': 'ge',
            '>': 'gt',
            '==': 'eq',
            '!=': 'ne',
            '&&': 'and',
            '||': 'or',
            '!': 'not',
        }

        # TODO:
        # - Load the location containing the left expression
        # - Load the location containing the right expression

        # Make a new temporary for storing the result
        target = self.new_temp()
        
        # Create the opcode and append to list
        opcode = binary_ops[node.op] + "_" + _ltype
        inst = (opcode, node.lvalue.gen_location, node.rvalue.gen_location, target)
        self.current_block.append(inst)

        # Store location of the result on the node
        node.gen_location = target

    def visit_UnaryOp(self, node):  # ('op', 'expr', 'coord', 'gen_location')
        self.visit(node.expr)

        if node.op == '!':
            # Sub 1 to var
            _exprtarget = self.new_temp()
            inst = ('not_bool', node.expr.gen_location, _exprtarget)
            self.current_block.append(inst)
            # Gen location = result location
            node.gen_location = _exprtarget
        elif node.op == '-':
            # Load constant 0
            _target = self.new_temp()
            inst = ("literal_int", 0, _target)
            self.current_block.append(inst)
            _exprtarget = self.new_temp()
            inst = ('sub_' + node.expr.type, _target, node.expr.gen_location, _exprtarget)
            self.current_block.append(inst)
            node.gen_location = _exprtarget
        else:
            # Load constant 1
            _target = self.new_temp()
            inst = ("literal_int", 1, _target)
            self.current_block.append(inst)
            _exprtarget = self.new_temp()

            if node.op == '++':
                # Add 1 to var
                inst = ('add_' + node.expr.type.typename, node.expr.gen_location, _target, _exprtarget)
                self.current_block.append(inst)
                # Gen location = var location
                node.gen_location = node.expr.gen_location
                # Store var incremented/decremented value
                inst = ('store_int', _exprtarget, '%' + node.expr.name)
                self.current_block.append(inst)
            elif node.op == '--':
                # Sub 1 to var
                inst = ('sub_' + node.expr.type.typename, node.expr.gen_location, _target, _exprtarget)
                self.current_block.append(inst)
                # Gen location = var location
                node.gen_location = node.expr.gen_location
                # Store var incremented/decremented value
                inst = ('store_int', _exprtarget, '%' + node.expr.name)
                self.current_block.append(inst)
            elif node.op == 'p++':
                # Add 1 to var
                inst = ('add_' + node.expr.type.typename, node.expr.gen_location, _target, _exprtarget)
                self.current_block.append(inst)
                # Gen location = result location
                node.gen_location = _exprtarget
                # Store var incremented/decremented value
                inst = ('store_int', _exprtarget, '%' + node.expr.name)
                self.current_block.append(inst)
            elif node.op == 'p--':
                # Sub 1 to var
                inst = ('sub_' + node.expr.type.typename, node.expr.gen_location, _target, _exprtarget)
                self.current_block.append(inst)
                # Gen location = result location
                node.gen_location = _exprtarget
                # Store var incremented/decremented value
                inst = ('store_int', _exprtarget, '%' + node.expr.name)
                self.current_block.append(inst)

    def visit_Print(self, node):
        if isinstance(node.expr, ExprList):
            for expr in node.expr.exprs:
                self.visit(expr)

                if isinstance(expr, ArrayRef):
                    _type = expr.name.type.type.type.name
                elif isinstance(expr, ID):
                    _type = expr.type.typename
                elif isinstance(expr, FuncCall):
                    _type = expr.name.type
                else:
                    _type = expr.type

                # Create the opcode and append to list
                inst = ("print_" + _type, expr.gen_location)
                self.current_block.append(inst)
        elif node.expr is not None:
            # Visit the expression
            self.visit(node.expr)

            # TODO: Load the location containing the expression

            if isinstance(node.expr, ArrayRef):
                _type = node.expr.name.type.type.type.name
            elif isinstance(node.expr, ID):
                _type = node.expr.type.typename
            elif isinstance(node.expr, FuncCall):
                _type = node.expr.name.type
            else:
                _type= node.expr.type

            # Create the opcode and append to list
            inst = ("print_" + _type, node.expr.gen_location)
            self.current_block.append(inst)
        
        else:
            inst = ("print_void",)
            self.current_block.append(inst)

    def visit_Assert(self, node): # ('expr', 'coord', 'gen_location')
        _conditionblock = ConditionBlock('%assert')
        _blockfalse = BasicBlock('%assert.false')
        _blocktrue = BasicBlock('%assert.true')

        _conditionblock.predecessors.append(self.current_block)
        self.current_block.branch = _conditionblock
        inst = ('jump', '%assert')
        self.current_block.append(inst)

        _conditionblock.taken = _blocktrue
        _conditionblock.fall_through = _blockfalse

        self.current_block.next_block = _conditionblock
        self.current_block = _conditionblock
        
        self.visit(node.expr)
        
        inst = ('cbranch', node.expr.gen_location, '%assert.true', '%assert.false')
        self.current_block.append(inst)

        _blockfalse.predecessors.append(_conditionblock)
        error_name = self.new_text('str')
        error_inst = ('global_string', error_name, 'assertion_fail on' + str(node.expr.coord).replace('@', ''))  #s.replace('a', '')
        self.text.append(error_inst)

        self.current_block.next_block = _blockfalse
        self.current_block = _blockfalse
        false_block = ('assert.false:',)
        self.current_block.append(false_block)
        self.current_block.append(('print_string', error_name))
        self.current_block.append(('jump', '%exit'))
        
        _blockfalse.predecessors.append(_blockfalse)
        _blockfalse.predecessors.append(_conditionblock)
        
        self.current_block.next_block = _blocktrue
        self.current_block = _blocktrue
        true_block = ('assert.true:',)
        self.current_block.append(true_block)

    def visit_Break(self, node):
        inst = ('jump', '%' + self.current_break)
        self.current_block.append(inst)
        self.current_break = None
    
    def visit_If(self, node):  # ('cond', 'if_statements', 'else_statements', 'coord', 'gen_location')
        if_then = 'if.then.' + str(self.if_count) if self.if_count != 0 else 'if.then'
        if_end = 'if.end.' + str(self.if_count) if self.if_count != 0 else 'if.end'
        _else = 'else.' + str(self.if_count) if self.if_count != 0 else 'else'
        _if = 'if.' + str(self.if_count) if self.if_count != 0 else 'if'

        _ifblock = ConditionBlock('%' + _if)

        self.if_count += 1

        _end = if_end
        if node.else_statements is not None:
            _end = _else

        then_block = BasicBlock('%' + if_then)
        end_block = BasicBlock('%' + if_end)
        else_block = BasicBlock('%' + _else)

        self.current_block.branch = _ifblock
        _ifblock.predecessors.append(self.current_block)

        inst = ('jump', '%' + _if)
        self.current_block.append(inst)
        self.current_block.next_block = _ifblock
        self.current_block = _ifblock

        self.current_block.append((_if + ':',))
        self.visit(node.cond)
        inst = ('cbranch', node.cond.gen_location, '%' + if_then, '%' + _end)
        self.current_block.append(inst)

        _ifblock.taken = then_block
        then_block.predecessors.append(self.current_block)
        self.current_block.next_block = then_block
        self.current_block = then_block
        
        if_block = (if_then + ':',)
        self.current_block.append(if_block)
        self.visit(node.if_statements)
        if_jump = ('jump', '%' + if_end)
        self.current_block.append(if_jump)
        
        self.current_block.branch = end_block
        end_block.predecessors.append(self.current_block)

        if node.else_statements is not None:
            else_block.predecessors.append(_ifblock)
            _ifblock.fall_through = else_block

            self.current_block.next_block = else_block
            self.current_block = else_block
            else_block = (_else + ':',)
            self.current_block.append(else_block)

            self.visit(node.else_statements)

            if_jump = ('jump', '%' + if_end)
            
            self.current_block.append(if_jump)
            self.current_block.branch = end_block
            end_block.predecessors.append(self.current_block)
        else:
            _ifblock.fall_through = end_block

        self.current_block.next_block = end_block
        self.current_block = end_block

        end_block = (if_end + ':',)
        self.current_block.append(end_block)

    def visit_For(self, node):  # ('init', 'cond', 'next', 'statements', 'coord', 'gen_location')
        self.visit(node.init)

        for_cond = 'for.cond.' + str(self.for_count) if self.for_count != 0 else 'for.cond'
        for_body = 'for.body.' + str(self.for_count) if self.for_count != 0 else 'for.body'
        for_end = 'for.end.' + str(self.for_count) if self.for_count != 0 else 'for.end'
        for_inc = 'for.inc.' + str(self.for_count) if self.for_count != 0 else 'for.inc'

        cond_block = ConditionBlock('%' + for_cond)
        stat_block = BasicBlock('%' + for_body)
        inc_block = BasicBlock('%' + for_inc)
        end_block = BasicBlock('%' + for_end)

        self.for_count += 1
        self.current_break = for_end

        inst = ('jump', '%' + for_cond)
        self.current_block.append(inst)

        self.current_block.branch = cond_block
        cond_block.predecessors.append(self.current_block)
        cond_block.predecessors.append(inc_block)
        cond_block.taken = stat_block
        cond_block.fall_through = end_block
        
        self.current_block.next_block = cond_block
        self.current_block = cond_block

        self.current_block.append((for_cond + ':',))
        self.visit(node.cond)
        inst = ('cbranch', node.cond.gen_location, '%' + for_body, '%' + for_end)
        self.current_block.append(inst)

        stat_block.predecessors.append(cond_block)

        self.current_block.next_block = stat_block
        self.current_block = stat_block

        self.current_block.append((for_body + ':',))
        self.visit(node.statements)
        inst = ('jump', '%' + for_inc)
        self.current_block.append(inst)

        self.current_block.branch = inc_block

        inc_block.predecessors.append(self.current_block)
        inc_block.branch = cond_block

        self.current_block.next_block = inc_block
        self.current_block = inc_block

        self.current_block.append((for_inc + ':',))
        self.visit(node.next)
        inst = ('jump', '%' + for_cond)
        self.current_block.append(inst)

        end_block.predecessors.append(cond_block)

        self.current_block.next_block = end_block
        self.current_block = end_block

        self.current_block.append((for_end + ':',))

    def visit_While(self, node): # ('cond', 'statements', 'coord', 'gen_location')
        while_cond = 'while.cond.' + str(self.while_count) if self.while_count != 0 else 'while.cond'
        while_body = 'while.body.' + str(self.while_count) if self.while_count != 0 else 'while.body'
        while_end = 'while.end.' + str(self.while_count) if self.while_count != 0 else 'while.end'

        cond_block = ConditionBlock('%' + while_cond)
        stat_block = BasicBlock('%' + while_body)
        end_block = BasicBlock('%' + while_end)

        cond_block.predecessors.append(self.current_block)
        cond_block.predecessors.append(stat_block)
        cond_block.taken = stat_block
        cond_block.fall_through = end_block
        self.current_block.branch = cond_block

        self.while_count += 1
        self.current_break = while_end

        inst = ('jump', '%' + while_cond)
        self.current_block.append(inst)
        self.current_block.next_block = cond_block
        self.current_block = cond_block

        self.current_block.append((while_cond + ':',))
        self.visit(node.cond)
        inst = ('cbranch', node.cond.gen_location, '%' + while_body, '%' + while_end)
        self.current_block.append(inst)

        stat_block.predecessors.append(cond_block)
        stat_block.branch = cond_block

        self.current_block.next_block = stat_block
        self.current_block = stat_block

        self.current_block.append((while_body + ':',))
        self.visit(node.statements)
        inst = ('jump', '%' + while_cond)
        self.current_block.append(inst)

        end_block.predecessors.append(cond_block)

        self.current_block.next_block = end_block
        self.current_block = end_block
        self.current_block.append((while_end + ':',))

    def visit_Assignment(self, node):  # ('op', 'lvalue', 'rvalue', 'coord', 'gen_location')
        # "=", "+=", "-=", "*=", "/=", "%="
        self.visit(node.rvalue)
        if isinstance(node.lvalue, ID):
            _leftname = '%' + node.lvalue.name
            _lefttype = node.lvalue.type.typename
        elif isinstance(node.lvalue, ArrayRef):  #('name', 'subscript', 'type', 'coord', 'gen_location')
            self.visit(node.lvalue)
            _leftname = node.lvalue.gen_location
            _lefttype = node.lvalue.type.type.type.name + '_*'
        else:
            _leftname = '%' + node.lvalue.name


        _target = _leftname
        _source = node.rvalue.gen_location
        
        if node.op == '+=':
            _source = self.new_temp()
            inst = ('add_' + _lefttype, _target, node.rvalue.gen_location, _source)
            self.current_block.append(inst)
        elif node.op == '-=':
            _source = self.new_temp()
            inst = ('sub_' + _lefttype, _target, node.rvalue.gen_location, _source)
            self.current_block.append(inst)
        elif node.op == '*=':
            _source = self.new_temp()
            inst = ('mul_' + _lefttype, _target, node.rvalue.gen_location, _source)
            self.current_block.append(inst)
        elif node.op == '/=':
            _source = self.new_temp()
            inst = ('div_' + _lefttype, _target, node.rvalue.gen_location, _source)
            self.current_block.append(inst)
        elif node.op == '%=':
            _source = self.new_temp()
            inst = ('mod_' + _lefttype, _target, node.rvalue.gen_location, _source)
            self.current_block.append(inst)

        inst = ('store_' + _lefttype, _source, _target)
        self.current_block.append(inst)

    def visit_Decl(self, node):  # ('name', 'type', 'init', 'gen_location')
        # Global variables
        if self.fname == "_glob_":
            _varname = "@" + node.name.name
            _init = node.init
            if isinstance(node.type, VarDecl):
                _vartype = node.type.type.name
                if _init is not None:
                    _init_value = self.cast_value(_vartype, _init.value)
                    inst = ("global_" + _vartype, _varname, _init_value)
                else:
                    inst = ("global_" + _vartype, _varname)
                self.text.append(inst)
            elif isinstance(node.type, ArrayDecl): # 'type', 'size', 'coord', 'gen_location'
                _vartype = node.type.type.type.name
                if _init is not None:
                    _initlist = []
                    for expr in _init.exprs:
                        _initlist.append(self.cast_value(expr.type, expr.value))
                    inst = ("global_" + _vartype + '_' + str(node.type.size), _varname, _initlist)
                else:
                    inst = ("global_" + _vartype + '_' + str(node.type.size), _varname)
                self.text.append(inst)
        # Allocate on stack memory
        else:
            _varname = "%" + node.name.name
            if isinstance(node.type, VarDecl):
                _vartype = node.type.type.name
                inst = ("alloc_" + _vartype, _varname)
                self.current_block.append(inst)
                node.name.gen_location = _varname
            elif isinstance(node.type, ArrayDecl): # 'type', 'size', 'coord', 'gen_location'
                _vartype = node.type.type.type.name
                inst = ("alloc_" + _vartype + '_' + str(node.type.size), _varname)
                self.current_block.append(inst)
                node.name.gen_location = _varname

                _varname = self.new_text('const_' + node.name.name)
                _vartype = node.type.type.type.name
                _init = node.init
                if _init is not None:
                    _initlist = []
                    for expr in _init.exprs:
                        _initlist.append(self.cast_value(expr.type, expr.value))
                    inst = ("global_" + _vartype + '_' + str(node.type.size), _varname, _initlist)
                else:
                    inst = ("global_" + _vartype + '_' + str(node.type.size), _varname)
                self.text.append(inst)
                
                inst = ('store_' + node.type.type.type.name + '_'+ str(node.type.size), _varname, '%' + node.name.name)
                self.current_block.append(inst)
            elif isinstance(node.type, FuncDecl):
                self.visit(node.type)
            #     _varname = "@" + node.name.name
            #     _vartype = node.type.type.type.name
            #     inst = ("define_" + _vartype, _varname, )
            #     self.current_block.append(inst)

            # Store optional init val
            _init = node.init
            if _init is not None:
                self.visit(_init)
                inst = (
                    "store_" + _vartype,
                    _init.gen_location,
                    node.name.gen_location,
                )
                self.current_block.append(inst)
            

    def visit_FuncDecl(self, node):
        if node.args is not None:
            self.visit(node.args)

    def visit_ParamList(self, node):
        for param in node.params:
            self.visit(param)
            inst = (
                    "store_" + param.type.type.name,
                    param.gen_location,
                    "%" + param.name.name,
                )
            self.current_block.append(inst)

    # def visit_VarDecl(self, node):
    #     # Allocate on stack memory
    #     _varname = "%" + node.declname.name
    #     inst = ("alloc_" + node.type.name, _varname)
    #     self.current_block.append(inst)

    def visit_FuncCall(self, node):  # ('name', 'args', 'coord', 'gen_location')
        if node.args is not None:
            if isinstance(node.args, ExprList):
                for expr in node.args.exprs:
                    self.visit(expr)
                    if isinstance(expr, Constant):
                        _exprtype = expr.type
                    else:
                        _exprtype = expr.type.typename

                    inst = ('param_' + _exprtype, expr.gen_location)
                    self.current_block.append(inst)
            else:
                self.visit(node.args)
                if isinstance(node.args, Constant):
                    _argstype = node.args.type
                else:
                    _argstype = node.args.type.typename

                inst = ('param_' + _argstype, node.args.gen_location)
                self.current_block.append(inst)

        temp_name = self.new_temp()
        inst = ('call_' + node.name.type, '@' + node.name.name, temp_name)
        self.current_block.append(inst)
        node.gen_location = temp_name

    def visit_Compound(self, node):
        if (node.block_items):
            for block_item in node.block_items:
                self.visit(block_item)

    def visit_Return(self, node): # 'expr', 'coord', 'gen_location'
        if node.expr is not None:
            self.visit(node.expr)
            inst = (
                    "store_" + self.function_type,
                    node.expr.gen_location,
                    self.return_key,
                )
            self.current_block.append(inst)
        
        inst_exit = ('jump', '%exit')
        self.current_block.append(inst_exit)
        
    def visit_Program(self, node):
        # Visit all of the global declarations
        for _decl in node.gdecls:
            self.visit(_decl)
        # At the end of codegen, first init the self.code with
        # the list of global instructions allocated in self.text
        self.code = self.text.copy()
        # Also, copy the global instructions into the Program node
        node.text = self.text.copy()
        # After, visit all the function definitions and emit the
        # code stored inside basic blocks.
        for _decl in node.gdecls:
            if isinstance(_decl, FuncDef):
                # _decl.cfg contains the Control Flow Graph for the function
                # cfg points to start basic block
                bb = EmitBlocks()
                bb.visit(_decl.cfg)
                for _code in bb.code:
                    self.code.append(_code)

        if self.viewcfg:  # evaluate to True if -cfg flag is present in command line
            for _decl in node.gdecls:
                if isinstance(_decl, FuncDef):
                    dot = CFG(_decl.decl.name.name)
                    dot.view(_decl.cfg)  # _decl.cfg contains the CFG for the function

    def visit_FuncDef(self, node): # 'spec', 'decl', 'param_decls', 'statements', 'cfg', 'coord', 'gen_location'
        func_name = node.decl.name.name
        func_type = node.spec.name
        func_block = BasicBlock('%' + func_name)        

        self.fname = func_name

        params_temp = []

        if node.decl.type.args is not None:
            for param in node.decl.type.args.params:
                var_name = self.new_temp()
                var_type = param.type.type.name
                params_temp.append((var_type, var_name))
                param.gen_location = var_name
        func_def = ('define_' + func_type, '@' + func_name, params_temp)
        func_block.append(func_def)
        func_block.append(('entry:',))
        self.function_type = func_type
        if func_type != 'void':
            return_name = self.new_temp()
            inst = ('alloc_' + func_type, return_name)
            func_block.append(inst)
            self.return_key = return_name

        node.cfg = func_block

        if self.current_block is not None:
            node.cfg.predecessors.append(self.current_block)
            self.current_block.next_block = node.cfg
        self.current_block = node.cfg
        
        self.visit(node.decl)
        self.visit(node.statements)

        exit_block = BasicBlock('%exit')
        exit_block.predecessors.append(self.current_block)
        self.current_block.branch = exit_block
        exit_block.append(('exit:',))
        
        if func_type != 'void':
            temp_return = self.new_temp()
            inst = ('load_' + func_type, return_name, temp_return)
            exit_block.append(inst)
            return_inst = ('return_' + func_type, temp_return)
            exit_block.append(return_inst)
        else:
            return_inst = ('return_void', )
            exit_block.append(return_inst)

        self.current_block.next_block = exit_block
        self.current_block.taken = exit_block

        self.fname = "_glob_"
        self.current_block = None
    # TODO: Complete.


if __name__ == "__main__":

    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file",
        help="Path to file to be used to generate uCIR. By default, this script only runs the interpreter on the uCIR. \
              Use the other options for printing the uCIR, generating the CFG or for the debug mode.",
        type=str,
    )
    parser.add_argument(
        "--ir",
        help="Print uCIR generated from input_file.",
        action="store_true",
    )
    parser.add_argument(
        "--cfg", help="Show the cfg of the input_file.", action="store_true"
    )
    parser.add_argument(
        "--debug", help="Run interpreter in debug mode.", action="store_true"
    )
    args = parser.parse_args()

    print_ir = args.ir
    create_cfg = args.cfg
    interpreter_debug = args.debug

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

    gen = CodeGenerator(create_cfg)
    gen.visit(ast)
    gencode = gen.code

    if print_ir:
        print("Generated uCIR: --------")
        gen.show()
        print("------------------------\n")

    vm = Interpreter(interpreter_debug)
    vm.run(gencode)
