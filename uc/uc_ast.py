import sys


def represent_node(obj, indent):
    def _repr(obj, indent, printed_set):
        '''
        Get the representation of an object, with dedicated pprint-like format for lists.
        '''
        if isinstance(obj, list):
            indent += 1
            sep = ',\n' + (' ' * indent)
            final_sep = ',\n' + (' ' * (indent - 1))
            return (
                '['
                + (sep.join((_repr(e, indent, printed_set) for e in obj)))
                + final_sep
                + ']'
            )
        elif isinstance(obj, Node):
            if obj in printed_set:
                return ''
            else:
                printed_set.add(obj)
            result = obj.__class__.__name__ + '('
            indent += len(obj.__class__.__name__) + 1
            attrs = []
            for name in obj.__slots__[:-1]:
                if name == 'bind':
                    continue
                value = getattr(obj, name)
                value_str = _repr(value, indent + len(name) + 1, printed_set)
                attrs.append(name + '=' + value_str)
            sep = ',\n' + (' ' * indent)
            final_sep = ',\n' + (' ' * (indent - 1))
            result += sep.join(attrs)
            result += ')'
            return result
        elif isinstance(obj, str):
            return obj
        else:
            return ''

    # avoid infinite recursion with printed_set
    printed_set = set()
    return _repr(obj, indent, printed_set)


class Node:
    '''Abstract base class for AST nodes.'''

    __slots__ = 'coord'
    attr_names = ()

    def __init__(self, coord=None, gen_location=None):
        self.coord = coord
        self.gen_location = gen_location

    def __repr__(self):
        '''Generates a python representation of the current node'''
        return represent_node(self, 0)

    def children(self):
        '''A sequence of all children that are Nodes'''
        pass

    def show(
        self,
        buf=sys.stdout,
        offset=0,
        attrnames=False,
        nodenames=False,
        showcoord=False,
        _my_node_name=None,
    ):
        '''Pretty print the Node and all its attributes and children (recursively) to a buffer.
        buf:
            Open IO buffer into which the Node is printed.
        offset:
            Initial offset (amount of leading spaces)
        attrnames:
            True if you want to see the attribute names in name=value pairs. False to only see the values.
        nodenames:
            True if you want to see the actual node names within their parents.
        showcoord:
            Do you want the coordinates of each Node to be displayed.
        '''
        lead = ' ' * offset
        if nodenames and _my_node_name is not None:
            buf.write(lead + self.__class__.__name__ + ' <' + _my_node_name + '>: ')
            inner_offset = len(self.__class__.__name__ + ' <' + _my_node_name + '>: ')
        else:
            buf.write(lead + self.__class__.__name__ + ':')
            inner_offset = len(self.__class__.__name__ + ':')

        if self.attr_names:
            if attrnames:
                nvlist = [
                    (n, represent_node(getattr(self, n), offset+inner_offset+1+len(n)+1))
                    for n in self.attr_names
                    if getattr(self, n) is not None
                ]
                attrstr = ', '.join('%s=%s' % nv for nv in nvlist)
            else:
                vlist = [getattr(self, n) for n in self.attr_names]
                attrstr = ', '.join(
                    represent_node(v, offset + inner_offset + 1) for v in vlist
                )
            buf.write(' ' + attrstr)

        if showcoord:
            if self.coord and self.coord.line != 0:
                buf.write(' %s' % self.coord)
        buf.write('\n')

        for (child_name, child) in self.children():
            child.show(buf, offset + 4, attrnames, nodenames, showcoord, child_name)


class ArrayDecl(Node):
    __slots__ = ('type', 'size', 'coord', 'gen_location')

    def __init__(self, type, size, coord=None, gen_location=None):
        self.type = type
        self.size = size
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.type is not None:
            nodelist.append(('type', self.type))
        if self.size is not None:
            nodelist.append(('size', self.size))
        return tuple(nodelist)

    attr_names = ()

class ArrayRef(Node):
    __slots__ = ('name', 'subscript', 'type', 'coord', 'gen_location')

    def __init__(self, name, subscript, arr_type=None, coord=None, gen_location=None):
        self.name = name
        self.subscript = subscript
        self.coord = coord
        self.gen_location = gen_location
        self.type = arr_type

    def children(self):
        nodelist = []
        if self.name is not None: nodelist.append(('name', self.name))
        if self.subscript is not None: nodelist.append(('subscript', self.subscript))
        return tuple(nodelist)

    attr_names = ()

class Assert(Node):
    __slots__ = ('expr', 'coord', 'gen_location')

    def __init__(self, expr, coord=None, gen_location=None, attrs=None):
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.expr is not None: nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ()

class Assignment(Node):
    __slots__ = ('op', 'lvalue', 'rvalue', 'coord', 'gen_location')

    def __init__(self, op, lvalue, rvalue, coord=None, gen_location=None):
        self.op = op
        self.lvalue = lvalue
        self.rvalue = rvalue
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.lvalue is not None: nodelist.append(('lvalue', self.lvalue))
        if self.rvalue is not None: nodelist.append(('rvalue', self.rvalue))
        return tuple(nodelist)

    attr_names = ('op',)

class BinaryOp(Node):
    __slots__ = ('op', 'lvalue', 'rvalue', 'type', 'coord', 'gen_location')

    def __init__(self, op, left, right, binary_type=None, coord=None, gen_location=None):
        self.op = op
        self.lvalue = left
        self.rvalue = right
        self.type = binary_type
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.lvalue is not None:
            nodelist.append(('lvalue', self.lvalue))
        if self.rvalue is not None:
            nodelist.append(('rvalue', self.rvalue))
        return tuple(nodelist)

    attr_names = ('op',)

class Break(Node):
    __slots__ = ('coord', 'gen_location')

    def __init__(self, coord=None, gen_location=None):
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        return ()

    attr_names = ()

class Cast(Node):
    __slots__ = ('type_cast', 'expr', 'coord', 'gen_location')

    def __init__(self, type_cast, expr, coord=None, gen_location=None):
        self.type_cast = type_cast
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.type_cast is not None:
            nodelist.append(('type_cast', self.type_cast))
        if self.expr is not None:
            nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ()

class Compound(Node):
    __slots__ = ('block_items', 'coord', 'gen_location')

    def __init__(self, block_items, coord=None, gen_location=None):
        self.block_items = block_items
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.block_items or []):
            nodelist.append(('block_items[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class Constant(Node):
    __slots__ = ('type', 'value', 'uc_type', 'coord', 'gen_location')

    def __init__(self, type, value, uc_type=None, coord=None, gen_location=None):
        self.type = type
        self.value = value
        self.uc_type = uc_type
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        return ()

    attr_names = (
        'type',
        'value',
    )

class Decl(Node):
    __slots__ = ('name', 'type', 'init', 'coord', 'gen_location')

    def __init__(self, name, type, init, coord=None, gen_location=None):
        self.name = name
        self.type = type
        self.init = init
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.type is not None: nodelist.append(('type', self.type))
        if self.init is not None: nodelist.append(('init', self.init))
        return tuple(nodelist)

    def __iter__(self):
        if self.type is not None:
            yield self.type
        if self.init is not None:
            yield self.init

    attr_names = ()

class DeclList(Node):
    __slots__ = ('decls', 'coord', 'gen_location')

    def __init__(self, decls, coord=None, gen_location=None):
        self.decls = decls
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.decls or []):
            nodelist.append(('decls[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()


class EmptyStatement(Node):
    __slots__ = ('coord', 'gen_location')

    def __init__(self, coord=None, gen_location=None):
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        return ()

    attr_names = ()

class ExprList(Node):
    __slots__ = ('exprs', 'coord', 'gen_location')

    def __init__(self, exprs, coord=None, gen_location=None):
        self.exprs = exprs
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.exprs or []):
            nodelist.append(('exprs[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class For(Node):
    __slots__ = ('init', 'cond', 'next', 'statements', 'coord', 'gen_location')

    def __init__(self, init, cond, next, statements, coord=None, gen_location=None):
        self.init = init
        self.cond = cond
        self.next = next
        self.statements = statements
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.init is not None: nodelist.append(('init', self.init))
        if self.cond is not None: nodelist.append(('cond', self.cond))
        if self.next is not None: nodelist.append(('next', self.next))
        if self.statements is not None: nodelist.append(('statements', self.statements))
        return tuple(nodelist)

    attr_names = ()

class FuncCall(Node):
    __slots__ = ('name', 'args', 'coord', 'gen_location')

    def __init__(self, name, args, coord=None, gen_location=None):
        self.name = name
        self.args = args
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.name is not None: nodelist.append(('name', self.name))
        if self.args is not None: nodelist.append(('args', self.args))
        return tuple(nodelist)

    attr_names = ()

class FuncDecl(Node):
    __slots__ = ('args', 'type', 'coord', 'gen_location')

    def __init__(self, args, type, coord=None, gen_location=None):
        self.args = args
        self.type = type
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.args is not None: nodelist.append(('args', self.args))
        if self.type is not None: nodelist.append(('type', self.type))
        return tuple(nodelist)

    def __iter__(self):
        if self.args is not None:
            yield self.args
        if self.type is not None:
            yield self.type

    attr_names = ()

class FuncDef(Node):
    __slots__ = ('spec', 'decl', 'param_decls', 'statements', 'cfg', 'coord', 'gen_location')

    def __init__(self, spec, decl, param_decls, statements, cfg=None, coord=None, gen_location=None):
        self.spec = spec
        self.decl = decl
        self.param_decls = param_decls
        self.statements = statements
        self.cfg = cfg
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.spec is not None: nodelist.append(('spec', self.spec))
        if self.decl is not None: nodelist.append(('decl', self.decl))
        if self.statements is not None: nodelist.append(('statements', self.statements))
        for i, child in enumerate(self.param_decls or []):
            nodelist.append(('param_decls[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class GlobalDecl(Node):
    __slots__ = ('decls', 'coord', 'gen_location')

    def __init__(self, decls, coord=None, gen_location=None):
        self.decls = decls
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.decls or []):
            nodelist.append(('decls[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class ID(Node):
    __slots__ = ('name', 'type', 'coord', 'gen_location')

    def __init__(self, name, id_type=None, coord=None, gen_location=None):
        self.name = name
        self.coord = coord
        self.gen_location = gen_location
        self.type = id_type

    def children(self):
        nodelist = []
        return tuple(nodelist)

    attr_names = ('name', )

class If(Node):
    __slots__ = ('cond', 'if_statements', 'else_statements', 'coord', 'gen_location')

    def __init__(self, cond, if_statements, else_statements, coord=None, gen_location=None):
        self.cond = cond
        self.if_statements = if_statements
        self.else_statements = else_statements
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.cond is not None: nodelist.append(('cond', self.cond))
        if self.if_statements is not None: nodelist.append(('if_statements', self.if_statements))
        if self.else_statements is not None: nodelist.append(('else_statements', self.else_statements))
        return tuple(nodelist)

    attr_names = ()

class InitList(Node):
    __slots__ = ('exprs', 'coord', 'gen_location')

    def __init__(self, exprs, coord=None, gen_location=None):
        self.exprs = exprs
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.exprs or []):
            nodelist.append(('exprs[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class ParamList(Node):
    __slots__ = ('params', 'coord', 'gen_location')

    def __init__(self, params, coord=None, gen_location=None):
        self.params = params
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.params or []):
            nodelist.append(('params[%d]' % i, child))
        return tuple(nodelist)
    
    def __iter__(self):
        for child in (self.params or []):
            yield child

    attr_names = ()

class Print(Node):
    __slots__ = ('expr', 'coord', 'gen_location')

    def __init__(self, expr, coord=None, gen_location=None):
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.expr is not None: nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ()

class Program(Node):
    __slots__ = ('gdecls', 'text', 'coord', 'gen_location')

    def __init__(self, gdecls, text=Node, coord=None, gen_location=None):
        self.gdecls = gdecls
        self.text = text
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        for i, child in enumerate(self.gdecls or []):
            nodelist.append(('gdecls[%d]' % i, child))
        return tuple(nodelist)

    attr_names = ()

class PtrDecl(Node):
    __slots__ = ('type', 'coord', 'gen_location')

    def __init__(self, type, coord=None, gen_location=None):
        self.type = type
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.type is not None: nodelist.append(('type', self.type))
        return tuple(nodelist)

    attr_names = ()

class Read(Node):
    __slots__ = ('expr', 'coord', 'gen_location')

    def __init__(self, expr, coord=None, gen_location=None):
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.expr is not None: nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ()

class Return(Node):
    __slots__ = ('expr', 'coord', 'gen_location')

    def __init__(self, expr, coord=None, gen_location=None):
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.expr is not None: nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ()

class Type(Node):
    __slots__ = ('name', 'coord', 'gen_location')

    attr_names = ('name', )

    def __init__(self, name, coord=None, gen_location=None):
        self.name = name
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        return tuple(nodelist)

class VarDecl(Node):
    __slots__ = ('declname', 'type', 'coord', 'gen_location')

    def __init__(self, declname, type, coord=None, gen_location=None):
        self.declname = declname
        self.type = type
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.type is not None: nodelist.append(('type', self.type))
        return tuple(nodelist)

    def __iter__(self):
        if self.type is not None:
            yield self.type

    attr_names = ()

class UnaryOp(Node):
    __slots__ = ('op', 'expr', 'coord', 'gen_location')

    def __init__(self, op, expr, coord=None, gen_location=None):
        self.op = op
        self.expr = expr
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.expr is not None: nodelist.append(('expr', self.expr))
        return tuple(nodelist)

    attr_names = ('op', )

class While(Node):
    __slots__ = ('cond', 'statements', 'coord', 'gen_location')

    def __init__(self, cond, statements, coord=None, gen_location=None):
        self.cond = cond
        self.statements = statements
        self.coord = coord
        self.gen_location = gen_location

    def children(self):
        nodelist = []
        if self.cond is not None: nodelist.append(('cond', self.cond))
        if self.statements is not None: nodelist.append(('statements', self.statements))
        return tuple(nodelist)

    attr_names = ()
