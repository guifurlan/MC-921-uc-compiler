class uCType:
    """
    Class that represents a type in the uC language.  Basic
    Types are declared as singleton instances of this type.
    """

    def __init__(
        self, name, binary_ops=set(), unary_ops=set(), rel_ops=set(), assign_ops=set()
    ):
        """
        You must implement yourself and figure out what to store.
        """
        self.typename = name
        self.unary_ops = unary_ops
        self.binary_ops = binary_ops
        self.rel_ops = rel_ops
        self.assign_ops = assign_ops
    
    def __str__(self):
        return 'type('+self.typename+')'


# Create specific instances of basic types. You will need to add
# appropriate arguments depending on your definition of uCType
IntType = uCType(
    "int",
    unary_ops={"-", "+", "--", "++", "p--", "p++", "*", "&"},
    binary_ops={"+", "-", "*", "/", "%"},
    rel_ops={"==", "!=", "<", ">", "<=", ">="},
    assign_ops={"=", "+=", "-=", "*=", "/=", "%="},
)

FloatType = uCType(
    "float",
    unary_ops={"-", "+", "--", "++", "p--", "p++", "*", "&"},
    binary_ops={"+", "-", "*", "/", "%"},
    rel_ops={"==", "!=", "<", ">", "<=", ">="},
    assign_ops={"=", "+=", "-=", "*=", "/=", "%="},
)

CharType = uCType(
    "char",
    unary_ops={"-", "+", "--", "++", "p--", "p++", "*", "&"},
    binary_ops={},
    rel_ops = {"==", "!="},
    assign_ops={"="},
)

StringType = uCType(
    "string",
    binary_ops={"+"},
    rel_ops={"==", "!="},
    assign_ops={"=", "+="},
)

BoolType = uCType(
    "bool",
    unary_ops={"!", "&", "*"},
    binary_ops={"&&", "||"},
    rel_ops={"==", "!="},
    assign_ops={"="},
)

VoidType = uCType("void")


# TODO: add pointer type ?
# Array, Pointer & Function types need to be instantiated for each declaration
class ArrayType(uCType):
    def __init__(self, element_type, size=None):
        """
        type: Any of the uCTypes can be used as the array's type. This
              means that there's support for nested types, like matrices.
              TODO: VOID TYPE NO UCTYPES PODE DAR PROBLEMA?
        size: Integer with the length of the array.
        """
        self.type = element_type
        self.size = size
        super().__init__(None, unary_ops={"*", "&"}, rel_ops={"==", "!="})
        
    def __str__(self):
        return 'type('+self.type.type.name+')'

class FunctionType(uCType):
    def __init__(self, function_type, params_list):
        """
        type: Any of the uCTypes can be used as the function's type.
        params: List of parameters of the function.
        """
        self.type = function_type
        self.params = params_list
        super().__init__(None)
    
    def __str__(self):
        return 'type('+self.type.type.name+')'
