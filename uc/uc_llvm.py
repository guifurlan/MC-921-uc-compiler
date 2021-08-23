import argparse
import pathlib
import sys
from ctypes import CFUNCTYPE, c_int
from llvmlite import binding, ir
from uc.uc_ast import FuncDef
from uc.uc_block import BlockVisitor, BasicBlock, ConditionBlock
from uc.uc_code import CodeGenerator
from uc.uc_parser import UCParser
from uc.uc_sema import NodeVisitor, Visitor


def make_bytearray(buf):
    # Make a byte array constant from *buf*.
    b = bytearray(buf)
    n = len(b)
    return ir.Constant(ir.ArrayType(ir.IntType(8), n), b)


class LLVMFunctionVisitor(BlockVisitor):
    def __init__(self, module, functions):
        self.module = module
        self.functions = functions
        self.call_params = []
        self.blocks = {}
        self.func = None
        self.builder = None
        self.loc = {}

    def _extract_operation(self, inst):
        _modifier = {}
        _ctype = None
        _aux = inst.split("_")
        _opcode = _aux[0]
        if _opcode not in {"fptosi", "sitofp", "jump", "cbranch", "define"}:
            _ctype = _aux[1]
            for i, _val in enumerate(_aux[2:]):
                if _val.isdigit():
                    _modifier["dim" + str(i)] = _val
                elif _val == "*":
                    _modifier["ptr" + str(i)] = _val
        return _opcode, _ctype, _modifier

    def _get_loc(self, target):
        try:
            if target[0] == "%":
                return self.loc[target]
            elif target[0] == "@":
                return self.module.get_global(target[1:])
        except KeyError:
            return None

    def _global_constant(self, builder_or_module, name, value, linkage="internal"):
        # Get or create a (LLVM module-)global constant with *name* or *value*.
        if isinstance(builder_or_module, ir.Module):
            mod = builder_or_module
        else:
            mod = builder_or_module.module
        data = ir.GlobalVariable(mod, value.type, name=name)
        data.linkage = linkage
        data.global_constant = True
        data.initializer = value
        data.align = 1
        return data

    def _cio(self, fname, format, *target):
        # Make global constant for string format
        mod = self.builder.module
        fmt_bytes = make_bytearray((format + "\00").encode("ascii"))
        global_fmt = self._global_constant(mod, mod.get_unique_name(".fmt"), fmt_bytes)
        fn = mod.get_global(fname)
        ptr_fmt = self.builder.bitcast(global_fmt, ir.IntType(8).as_pointer())
        return self.builder.call(fn, [ptr_fmt] + list(target))

    def _build_print(self, val_type, target):
        if target:
            # get the object assigned to target
            _value = self._get_loc(target)
            if val_type == "int":
                self._cio("printf", "%d", _value)
            elif val_type == "float":
                self._cio("printf", "%.2f", _value)
            elif val_type == "char":
                self._cio("printf", "%c", _value)
            elif val_type == "string":
                self._cio("printf", "%s", _value)
        else:
            self._cio("printf", "\n")

    def _build_alloc(self, val_type, var_name):
        _name = var_name[1:]
        llvm_type = self._get_type(val_type)
        alloc = self.builder.alloca(llvm_type, name=_name)
        self.loc[var_name] = alloc
        # dar return ?

    def _build_load(self, val_type, var_name, target):
        _name = var_name[1:]
        value = self._get_loc(var_name)
        load = self.builder.load(value, name=_name)
        self.loc[target] = load

    def _build_store(self, val_type, source, target):
        _source = self._get_loc(source)
        _target = self._get_loc(target)
        self.builder.store(_source, _target)

    def _build_literal(self, val_type, value, target):
        llvm_type = self._get_type(val_type)
        _value = ir.Constant(llvm_type, value)
        _target = self._get_loc(target)
        if _target is None:
            self.loc[target] = _value
        else:
            self.builder.store(_value, _target)
        # ver se precisa verificar se _target eh alloc

    def _build_elem(self, val_type, source, index, target):
        _type = self._get_type(val_type)
        _index = self._get_loc(index)
        _source = self._get_loc(source)
        gep = self.builder.gep(_source, [ir.Constant(_type, 0), _index])
        self.loc[target] = gep
    
    def _build_add(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.add(_left, _right)
        else:
            temp = self.builder.fadd(_left, _right)
        self.loc[target] = temp

    def _build_sub(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.sub(_left, _right)
        else:
            temp = self.builder.fsub(_left, _right)
        self.loc[target] = temp

    def _build_mul(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.mul(_left, _right)
        else:
            temp = self.builder.fmul(_left, _right)
        self.loc[target] = temp

    def _build_div(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)

        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.sdiv(_left, _right)
        else:
            temp = self.builder.fdiv(_left, _right)
        self.loc[target] = temp

    def _build_mod(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.srem(_left, _right)
        else:
            temp = self.builder.frem(_left, _right)
        self.loc[target] = temp

    def _build_not(self, val_type, expr, target):
        _expr = self._get_loc(expr)
        if isinstance(_expr.type, ir.PointerType):
            _expr = self.builder.load(_expr)

        self.loc[target] = self.builder.not_(_expr)

    def _build_fptosi(self, val_type, fvalue, target):
        _value = self._get_loc(fvalue)
        if isinstance(_value.type, ir.PointerType):
            _value = self.builder.load(_value)

        self.loc[target] = self.builder.fptosi(_value, ir.IntType(32))

    def _build_sitofp(self, val_type, ivalue, target):
        _value = self._get_loc(ivalue)
        if isinstance(_value.type, ir.PointerType):
            _value = self.builder.load(_value)

        self.loc[target] = self.builder.sitofp(_value, ir.DoubleType())

    def _build_lt(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed("<", _left, _right)
        else:
            temp = self.builder.fcmp_ordered("<", _left, _right)
        self.loc[target] = temp

    def _build_le(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed("<=", _left, _right)
        else:
            temp = self.builder.fcmp_ordered("<=", _left, _right)
        self.loc[target] = temp

    def _build_ge(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed(">=", _left, _right)
        else:
            temp = self.builder.fcmp_ordered(">=", _left, _right)
        self.loc[target] = temp

    def _build_gt(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed(">", _left, _right)
        else:
            temp = self.builder.fcmp_ordered(">", _left, _right)
        self.loc[target] = temp

    def _build_eq(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed("==", _left, _right)
        else:
            temp = self.builder.fcmp_ordered("==", _left, _right)
        self.loc[target] = temp

    def _build_ne(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        if val_type == "int" or val_type == "char":
            temp = self.builder.icmp_signed("!=", _left, _right)
        else:
            temp = self.builder.fcmp_ordered("!=", _left, _right)
        self.loc[target] = temp

    def _build_and(self, val_type, left, right, target):
        _left = self._get_loc(left)
        if isinstance(_left.type, ir.PointerType):
            _left = self.builder.load(_left)
            
        _right = self._get_loc(right)
        if isinstance(_right.type, ir.PointerType):
            _right = self.builder.load(_right)

        self.loc[target] = self.builder.and_(_left, _right)

    def _build_or(self, val_type, left, right, target):
        _left = self._get_loc(left)
        _right = self._get_loc(right)
        self.loc[target] = self.builder.or_(_left, _right)

    def _build_jump(self, val_type, target):
        if not self.builder.block.is_terminated:
            label = target.replace('%', '')
            _block = self.blocks[label]
            self.builder.branch(_block)

    def _build_cbranch(self, val_type, expr_test, true_target, false_target):
        if not self.builder.block.is_terminated:
            _expr = self._get_loc(expr_test)
            true_label = true_target.replace('%', '')
            false_label = false_target.replace('%', '')
            true_block = self.blocks[true_label]
            false_block = self.blocks[false_label]
            self.builder.cbranch(_expr, true_block, false_block)
    
    def _build_param(self, val_type, source):
        param = self._get_loc(source)
        self.call_params.append(param)

    def _build_call(self, val_type, source, target):
        func_name = source[1:]
        func = self._get_func(func_name)
        call = self.builder.call(func, self.call_params)
        self.loc[target] = call
        self.call_params = []

    def _build_return(self, val_type, target):
        if not self.builder.block.is_terminated:
            if val_type == 'void':
                self.builder.ret_void()
            else:
                _target = self._get_loc(target)
                self.builder.ret(_target)

    def _build_read(self, val_type, source): pass

    def _build_define(self, val_type, source, args): pass

    def build(self, inst):
        opcode, ctype, modifier = self._extract_operation(inst[0])
        if hasattr(self, "_build_" + opcode):
            args = inst[1:] if len(inst) > 1 else (None,)
            if not modifier:
                getattr(self, "_build_" + opcode)(ctype, *args)
            else:
                getattr(self, "_build_" + opcode + "_")(ctype, *inst[1:], **modifier)
        else:
            print("Warning: No _build_" + opcode + "() method", flush=True)

    def _get_type(self, type_name):
        if type_name == 'int':
            return ir.IntType(32)
        elif type_name == 'float':
            return ir.DoubleType()
        elif type_name == 'double':
            return ir.DoubleType()
        elif type_name == 'char':
            return ir.IntType(8)
        elif type_name == 'bool':
            return ir.IntType(1)
        elif type_name == 'void':
            return ir.VoidType()

    def _get_func(self, func_name):
        try:
            return self.functions[func_name]
        except KeyError:
            return None

    def _get_block(self, label):
        try:
            return self.blocks[label]
        except KeyError:
            return None

    def visit_BasicBlock(self, block):
        # TODO: Complete
        # Create the LLVM function when visiting its first block
        # First visit of the block should create its LLVM equivalent
        # Second visit should create the LLVM instructions within the block
        label = block.label.replace('%', '')
        if len(block.instructions) > 0:
            first_inst = block.instructions[0]
            if 'define' in first_inst[0]:
                func_name = first_inst[1].replace('@', '')
                if self._get_func(func_name) is None:
                    func_type = self._get_type(first_inst[0].replace('define_', ''))
                    func_params = []
                    for param in first_inst[2]:
                        func_params.append(self._get_type(param[0]))
                    fnty = ir.FunctionType(func_type, func_params)
                    self.func = ir.Function(self.module, fnty, func_name)
                    self.functions[func_name] = self.func
                    new_block = self.func.append_basic_block('entry')
                    self.blocks[label] = new_block
                    self.builder = ir.IRBuilder(new_block)

                    for i in range(len(self.func.args)):
                        self.loc['%' + str(i+1)] = self.func.args[i]   

                    block.instructions = block.instructions[1:] 
                return
        
            first_inst = first_inst[0].replace(':', '')
            if first_inst == label:
                block.instructions = block.instructions[1:]

        if self._get_block(label) is None and len(block.instructions) > 0:
            new_block = self.func.append_basic_block(label)
            self.blocks[label] = new_block
            return

        _block = self._get_block(label)
        if _block is not None:
            self.builder.position_at_end(_block)

        for inst in block.instructions:
            label_inst = inst[0].replace(':', '')
            if self._get_block(label_inst) is None and label_inst != 'entry':
                self.build(inst)


    def visit_ConditionBlock(self, block):
        # TODO: Complete
        # Create the LLVM function when visiting its first block
        # First visit of the block should create its LLVM equivalent
        # Second visit should create the LLVM instructions within the block
        label = block.label.replace('%', '')
        if self._get_block(label) is None:
            block = self.func.append_basic_block(label)
            self.blocks[label] = block
            return

        _block = self._get_block(label)
        self.builder.position_at_end(_block)
        for inst in block.instructions:
            label_inst = inst[0].replace(':', '')
            if self._get_block(label_inst) is None and label_inst != 'entry':
                self.build(inst)
            

class LLVMCodeGenerator(NodeVisitor):
    def __init__(self, viewcfg):
        self.viewcfg = viewcfg
        self.binding = binding
        self.binding.initialize()
        self.binding.initialize_native_target()
        self.binding.initialize_native_asmprinter()

        self.module = ir.Module(name=__file__)
        self.module.triple = self.binding.get_default_triple()

        self.engine = self._create_execution_engine()

        # declare external functions
        self._declare_printf_function()
        self._declare_scanf_function()

        self.functions = {}

    def _generate_global_instructions(self, inst):
        for var in inst:
            bb = LLVMFunctionVisitor(self.module, self.functions)
            var_name = var[1].replace('@', '')
            var_type = var[0].replace('global_', '')

            if var_type == 'string':
                value = make_bytearray((var[2]+"\00").encode("ascii"))
            elif '_' in var_type:
                var_type = var_type.split('_')
                size = int(var_type[1])
                llvm_type = bb._get_type(var_type[0])
                value_type = ir.ArrayType(llvm_type, size)
                value = ir.Constant(value_type, var[2])
            else:
                llvm_type = bb._get_type(var_type)
                value = ir.Constant(llvm_type, var[2])
            
            g = bb._global_constant(self.module, var_name, value)


    def _create_execution_engine(self):
        """
        Create an ExecutionEngine suitable for JIT code generation on
        the host CPU.  The engine is reusable for an arbitrary number of
        modules.
        """
        target = self.binding.Target.from_default_triple()
        target_machine = target.create_target_machine()
        # And an execution engine with an empty backing module
        backing_mod = binding.parse_assembly("")
        return binding.create_mcjit_compiler(backing_mod, target_machine)

    def _declare_printf_function(self):
        voidptr_ty = ir.IntType(8).as_pointer()
        printf_ty = ir.FunctionType(ir.IntType(32), [voidptr_ty], var_arg=True)
        printf = ir.Function(self.module, printf_ty, name="printf")
        self.printf = printf

    def _declare_scanf_function(self):
        voidptr_ty = ir.IntType(8).as_pointer()
        scanf_ty = ir.FunctionType(ir.IntType(32), [voidptr_ty], var_arg=True)
        scanf = ir.Function(self.module, scanf_ty, name="scanf")
        self.scanf = scanf

    def _compile_ir(self):
        """
        Compile the LLVM IR string with the given engine.
        The compiled module object is returned.
        """
        # Create a LLVM module object from the IR
        llvm_ir = str(self.module)
        mod = self.binding.parse_assembly(llvm_ir)
        mod.verify()
        # Now add the module and make sure it is ready for execution
        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()
        return mod

    def save_ir(self, output_file):
        output_file.write(str(self.module))

    def execute_ir(self, opt, opt_file):
        mod = self._compile_ir()

        if opt:
            # apply some optimization passes on module
            pmb = self.binding.create_pass_manager_builder()
            pm = self.binding.create_module_pass_manager()

            pmb.opt_level = 0
            if opt == "ctm" or opt == "all":
                # Sparse conditional constant propagation and merging
                pm.add_sccp_pass()
                # Merges duplicate global constants together
                pm.add_constant_merge_pass()
                # Combine inst to form fewer, simple inst
                # This pass also does algebraic simplification
                pm.add_instruction_combining_pass()
            if opt == "dce" or opt == "all":
                pm.add_dead_code_elimination_pass()
            if opt == "cfg" or opt == "all":
                # Performs dead code elimination and basic block merging
                pm.add_cfg_simplification_pass()

            pmb.populate(pm)
            pm.run(mod)
            opt_file.write(str(mod))

        # Obtain a pointer to the compiled 'main' - it's the address of its JITed code in memory.
        main_ptr = self.engine.get_function_address("main")
        # To convert an address to an actual callable thing we have to use
        # CFUNCTYPE, and specify the arguments & return type.
        main_function = CFUNCTYPE(c_int)(main_ptr)
        # Now 'main_function' is an actual callable we can invoke
        res = main_function()

    def visit_Program(self, node):
        # node.text contains the global instructions into the Program node
        self._generate_global_instructions(node.text)
        # Visit all the function definitions and emit the llvm code from the
        # uCIR code stored inside basic blocks.
        for _decl in node.gdecls:
            if isinstance(_decl, FuncDef):
                # _decl.cfg contains the Control Flow Graph for the function
                bb = LLVMFunctionVisitor(self.module, self.functions)
                # Visit the CFG to define the Function and Create the Basic Blocks
                bb.visit(_decl.cfg)
                # Visit CFG again to create the instructions inside Basic Blocks
                bb.visit(_decl.cfg)

                self.functions = bb.functions

                if self.viewcfg:
                    dot = binding.get_function_cfg(bb.func)
                    gv = binding.view_dot_graph(dot, _decl.decl.name.name, False)
                    gv.filename = _decl.decl.name.name + ".ll.gv"
                    gv.view()


if __name__ == "__main__":

    # create argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file",
        help="Path to file to be used to generate LLVM IR. By default, this script runs the LLVM IR without any optimizations.",
        type=str,
    )
    parser.add_argument(
        "-c",
        "--cfg",
        help="show the CFG of the optimized uCIR for each function in pdf format",
        action="store_true",
    )
    parser.add_argument(
        "--llvm-opt",
        default=None,
        choices=["ctm", "dce", "cfg", "all"],
        help="specify which llvm pass optimizations should be enabled",
    )
    args = parser.parse_args()

    create_cfg = args.cfg
    llvm_opt = args.llvm_opt

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

    gen = CodeGenerator(False)
    gen.visit(ast)

    llvm = LLVMCodeGenerator(create_cfg)
    llvm.visit(ast)
    llvm.execute_ir(llvm_opt, None)
