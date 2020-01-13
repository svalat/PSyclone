# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2020, Science and Technology Facilities Council
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------
# Author: R. W. Ford, STFC Daresbury Lab

'''Module providing a transformation script that converts the supplied
PSyIR to the Stencil intermediate representation (SIR), modifying any
PSyIR min, abs and sign intrinsics to PSyIR code beforehand using
transformations, as SIR does not support intrinsics. Translation to
the SIR is limited to the NEMO API. The NEMO API has no algorithm
layer so all of the original code is captured in the invoke
objects. Therefore by translating all of the invoke objects, all of
the original code is translated.

The min, abs and sign transformations are currently maintained within
this script as the NEMO API does not yet support a symbol table and
therefore the transformations are non-standard (requiring a symbol
table object to be provided to each transformation).

'''
from __future__ import print_function
from psyclone.psyir.backend.sir import SIRWriter
from psyclone.psyir.backend.fortran import FortranWriter
from psyclone.nemo import NemoKern
from psyclone.psyGen import UnaryOperation, BinaryOperation, NaryOperation, \
    Assignment, Reference, Literal, IfBlock, Schedule
import copy
from psyclone.psyir.symbols import DataType, SymbolTable, DataSymbol
import six
import abc
from psyclone.psyGen import Transformation


@six.add_metaclass(abc.ABCMeta)
class NemoOperatorTrans(Transformation):
    '''Provides NEMO-api-specific support for transformations from PSyIR
    intrinsic Operator nodes to equivalent PSyIR code in a PSyIR
    tree. Such transformations can be useful when the intrinsic is not
    supported or if it is more efficient to have explicit code.

    '''
    def __init__(self):
        super(NemoOperatorTrans, self).__init__()
        self._operator_name = None
        
    def __str__(self):
        return ("Convert the PSyIR {0} intrinsic to equivalent PSyIR "
                "code".format(self._operator_name.upper()))

    @property
    def name(self):
        '''
        :returns: the name of the parent transformation as a string.
        :rtype:str

        '''
        return "Nemo{0}Trans".format(self._operator_name.title())

    def validate(self, node, symbol_table):
        '''Perform various checks to ensure that it is valid to apply
        an intrinsic transformation to the supplied Node.

        :param node: the node that is being checked.
        :type node: :py:class:`psyclone.psyGen.Operation`
        :param symbol_table: the symbol table that is being checked.
        :type symbol_table: :py:class:`psyclone.psyir.symbols.SymbolTable`

        :raises TransformationError: if the node argument is not the \
            expected type.
        :raises TransformationError: if the symbol_table argument is not a \
            :py:class:`psyclone.psyir.symbols.SymbolTable`.
        :raises TransformationError: if the api is not nemo.
        :raises TransformationError: if the Operation node does \
            not have an Assignement Node as an ancestor.

        '''
        # Check that the node is the expected type.
        if not isinstance(node, self._class) or \
           not node.operator is self._operator:
            raise TransformationError(
                "Error in {0} transformation. The supplied node argument is "
                "not an {1} operator, found '{2}'."
                "".format(self.name, self._operator_name,
                          type(node).__name__))
        # Check that symbol_table is a PSyIR symbol table
        if not isinstance(symbol_table, SymbolTable):
            raise TransformationError(
                "Error in {0} transformation. The supplied symbol_table "
                "argument is not an a SymbolTable, found '{1}'."
                "".format(self.name, type(symbol_table).__name__))
        # Check that this is the nemo api.
        from psyclone.configuration import Config
        if not Config.get().api == "nemo":
            raise TransformationError(
                "Error in {0} transformation. This transformation only "
                "works for the nemo api, but found '{1}'."
                "".format(self.name, Config.get().api))
        # Check that there is an Assignment node that is an ancestor
        # of this Operation.
        if not node.ancestor(Assignment):
            raise TransformationError(
                "Error in {0} transformation. This transformation requires "
                "the operator to be part of an assignment statement, "
                "but no such assignment was found.".format(self.name))


class NemoAbsTrans(NemoOperatorTrans):
    '''Provides a NEMO-api-specific transformation from a PSyIR ABS
    Operator node to equivalent code in a PSyIR tree. Validity checks
    are also performed.

    The transformation replaces `R=ABS(X)` with the following logic:

    `IF (X<0.0) R=X*-1.0 ELSE R=X`

    '''
    def __init__(self):
        super(NemoAbsTrans, self).__init__()
        self._operator_name = "ABS"
        self._class = UnaryOperation
        self._operator = UnaryOperation.Operator.ABS

    def apply(self, node, symbol_table):
        '''Apply the ABS intrinsic conversion transformation to the specified
        node. This node must be an ABS UnaryOperation. The ABS
        UnaryOperation is converted to the following equivalent inline code:

        R=ABS(X) => IF (X<0.0) R=X*-1.0 ELSE R=X

        In the PSyIR this is implemented as a transform from:

        R= ... ABS(X) ...

        to:

        tmp_abs=X
        IF (tmp_abs<0.0) res_abs=tmp_abs*-1.0 ELSE res_abs=tmp_abs
        R= ... res_abs ...

        where X could be an arbitrarily complex expression.
        
        A symbol table is required as the NEMO api does not currently
        contain a symbol table and one is required in order to create
        temporary variables whose names do not clash with existing
        code. This non-standard argument is also the reason why this
        transformation is currently limited to the NEMO api.

        This transformation requires the operation node to be a
        descendent of an assignment and will raise an exception if
        this is not the case.

        :param node: an ABS UnaryOperation node.
        :type node: :py:class:`psyclone.psyGen.UnaryOperation`
        :param symbol_table: the symbol table.
        :type symbol_table: :py:class:`psyclone.psyir.symbols.SymbolTable`

        '''
        self.validate(node, symbol_table)
        
        oper_parent = node.parent
        assignment = node.ancestor(Assignment)
        # Create two temporary variables.
        res_var = symbol_table.new_symbol_name("res_abs")
        symbol_table.add(DataSymbol(res_var, DataType.REAL))
        tmp_var = symbol_table.new_symbol_name("tmp_abs")
        symbol_table.add(DataSymbol(tmp_var, DataType.REAL))

        # Replace operation with a temporary (res_X).
        oper_parent.children[node.position] = Reference(res_var,
                                                        parent=oper_parent)

        # tmp_var=X
        lhs = Reference(tmp_var)
        rhs = node.children[0]
        new_assignment = Assignment.create(lhs, rhs)
        new_assignment.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, new_assignment)

        # if condition: tmp_var>0.0
        lhs = Reference(tmp_var)
        rhs = Literal("0.0", DataType.REAL)
        if_condition = BinaryOperation.create(BinaryOperation.Operator.GT,
                                              lhs, rhs)

        # then_body: res_var=tmp_var
        lhs = Reference(res_var)
        rhs = Reference(tmp_var)
        then_body = [Assignment.create(lhs, rhs)]

        # else_body: res_var=-1.0*tmp_var
        lhs = Reference(res_var)
        lhs_child = Reference(tmp_var)
        rhs_child = Literal("-1.0", DataType.REAL)
        rhs = BinaryOperation.create(BinaryOperation.Operator.MUL, lhs_child,
                                     rhs_child)
        else_body = [Assignment.create(lhs, rhs)]

        # if [if_condition] then [then_body] else [else_body]
        if_stmt = IfBlock.create(if_condition, then_body, else_body)
        if_stmt.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, if_stmt)


class NemoSignTrans(NemoOperatorTrans):
    '''Provides a NEMO-api-specific transformation from a PSyIR SIGN
    Operator node to equivalent code in a PSyIR tree. Validity checks
    are also performed.

    The transformation replaces `R=SIGN(A,B)` with the following logic:

    `R=SIGN(A,B) => R=ABS(B); if A<0.0 R=R*-1.0`

    Note, an alternative would be:
    `if A<0 then (if B<0 R=B else R=B*-1) else ((if B>0 R=B else R=B*-1))`

    '''
    def __init__(self):
        super(NemoSignTrans, self).__init__()
        self._operator_name = "SIGN"
        self._class = BinaryOperation
        self._operator = BinaryOperation.Operator.SIGN

    def apply(self, node, symbol_table):
        '''Apply the SIGN intrinsic conversion transformation to the specified
        node. This node must be an SIGN BinaryOperation. The SIGN
        BinaryOperation is converted to the following equivalent
        inline code:

        R=SIGN(A,B) => R=ABS(B); if A<0.0 R=R*-1.0

        This is implemented as a transform from:

        R= ... SIGN(A,B) ...

        to:

        tmp_abs=B
        IF (tmp_abs<0.0) res_abs=tmp_abs*-1.0 ELSE res_abs=tmp_abs
        res_sign = res_abs
        tmp_sign = A
        if (tmp_sign<0.0) res_sign=res_sign*-1.0
        R= ... res_x ...

        where A and B could be an arbitrarily complex expressions and
        where ABS is replaced with inline code by the NemoAbsTrans
        transformation.
        
        A symbol table is required as the NEMO api does not currently
        contain a symbol table and one is required in order to create
        temporary variables whose names do not clash with existing
        code. This non-standard argument is also the reason why this
        transformation is currently limited to the NEMO api.

        This transformation requires the operation node to be a
        descendent of an assignment and will raise an exception if
        this is not the case.

        :param node: a SIGN BinaryOperation node.
        :type node: :py:class:`psyclone.psyGen.BinaryOperation`
        :param symbol_table: the symbol table.
        :type symbol_table: :py:class:`psyclone.psyir.symbols.SymbolTable`

        '''
        self.validate(node, symbol_table)

        oper_parent = node.parent
        assignment = node.ancestor(Assignment)
        # Create two temporary variables.
        res_var = symbol_table.new_symbol_name("res_sign")
        symbol_table.add(DataSymbol(res_var, DataType.REAL))
        tmp_var = symbol_table.new_symbol_name("tmp_sign")
        symbol_table.add(DataSymbol(tmp_var, DataType.REAL))

        # Replace operator with a temporary (res_var).
        oper_parent.children[node.position] = Reference(res_var,
                                                        parent=oper_parent)

        # res_var=ABS(B)
        lhs = Reference(res_var)
        rhs = UnaryOperation.create(UnaryOperation.Operator.ABS,
                                    node.children[1])
        new_assignment = Assignment.create(lhs, rhs)
        new_assignment.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, new_assignment)

        # Replace the ABS intrinsic with inline code.
        abs_trans = NemoAbsTrans()
        abs_trans.apply(rhs, symbol_table)

        # tmp_var=A
        lhs = Reference(tmp_var)
        new_assignment = Assignment.create(lhs, node.children[0])
        new_assignment.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, new_assignment)

        # if condition: tmp_var<0.0
        lhs = Reference(tmp_var)
        rhs = Literal("0.0", DataType.REAL)
        if_condition= BinaryOperation.create(BinaryOperation.Operator.LT,
                                             lhs, rhs)

        # then_body: res_var=res_var*-1.0
        lhs = Reference(res_var)
        lhs_child = Reference(res_var)
        rhs_child = Literal("-1.0", DataType.REAL)
        rhs = BinaryOperation.create(BinaryOperation.Operator.MUL,
                                     lhs_child, rhs_child)
        then_body = [Assignment.create(lhs, rhs)]

        # if [if condition] then [then_body]
        if_stmt = IfBlock.create(if_condition, then_body)
        if_stmt.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, if_stmt)


class NemoMinTrans(NemoOperatorTrans):
    '''Provides a NEMO-api-specific transformation from a PSyIR MIN
    Operator node to equivalent code in a PSyIR tree. Validity checks
    are also performed.

    The transformation replaces `R=MIN(A,B,C...)` with the following logic:

    `R=MIN(A,B,C,..) R=A; if B<R R=B; if C<R R=C; ...`

    '''
    def __init__(self):
        super(NemoMinTrans, self).__init__()
        self._operator_name = "MIN"
        self._class = NaryOperation
        self._operator = NaryOperation.Operator.MIN

    def apply(self, node, symbol_table):
        '''Apply the MIN intrinsic conversion transformation to the specified
        node. This node must be an MIN NaryOperation. The MIN
        NaryOperation is converted to the following equivalent inline code:

        R=MIN(A,B,C,..) => R=A; if B<R R=B; if C<R R=C; ...

        In the PSyIR this is implemented as a transform from:

        R= ... MIN(A,B,C...) ...

        to:

        res_min=A
        tmp_min=B
        IF (tmp_min<res_min) res_min=tmp_min
        tmp_min=C
        IF (tmp_min<res_min) res_min=tmp_min
        ...
        R= ... res_min ...

        where A,B,C... could be arbitrarily complex expressions.
        
        A symbol table is required as the NEMO api does not currently
        contain a symbol table and one is required in order to create
        temporary variables whose names do not clash with existing
        code. This non-standard argument is also the reason why this
        transformation is currently limited to the NEMO api.

        This transformation requires the operation node to be a
        descendent of an assignment and will raise an exception if
        this is not the case.

        :param node: a MIN NaryOperation node.
        :type node: :py:class:`psyclone.psyGen.NaryOperation`
        :param symbol_table: the symbol table.
        :type symbol_table: :py:class:`psyclone.psyir.symbols.SymbolTable`

        '''
        self.validate(node, symbol_table)

        oper_parent = node.parent
        assignment = node.ancestor(Assignment)

        # Create a temporary result variable.
        res_var = symbol_table.new_symbol_name("res_min")
        symbol_table.add(DataSymbol(res_var, DataType.REAL))

        # Replace operation with a temporary (res_var).
        oper_parent.children[node.position] = Reference(res_var,
                                                        parent=oper_parent)

        # res_var=A
        lhs = Reference(res_var)
        new_assignment = Assignment.create(lhs, node.children[0])
        new_assignment.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, new_assignment)

        # For each of the remaining min arguments (B,C...)
        for expression in node.children[1:]:
            # Create a temporary variable.
            tmp_var = symbol_table.new_symbol_name("tmp_min")
            symbol_table.add(DataSymbol(tmp_var, DataType.REAL))

            # tmp_var=(B or C or ...)
            lhs = Reference(tmp_var)
            new_assignment = Assignment.create(lhs, expression)
            new_assignment.parent = assignment.parent
            assignment.parent.children.insert(assignment.position,
                                              new_assignment)

            # if_condition: tmp_var<res_var
            lhs = Reference(tmp_var)
            rhs = Reference(res_var)
            if_condition = BinaryOperation.create(BinaryOperation.Operator.LT,
                                                  lhs, rhs)

            # then_body: res_var=tmp_var
            lhs = Reference(res_var)
            rhs = Reference(tmp_var)
            then_body = [Assignment.create(lhs, rhs)]

            # if [if_condition] then [then_body]
            if_stmt = IfBlock.create(if_condition, then_body)
            if_stmt.parent = assignment.parent
            assignment.parent.children.insert(assignment.position, if_stmt)


def trans(psy):
    '''Transformation routine for use with PSyclone. Applies the PSyIR2SIR
    transform to the supplied invokes after replacing any ABS, SIGN or
    MIN intrinsics with equivalent code. This is done because the SIR
    does not support intrinsics. This script is limited to the
    NEMO API becuase the NEMO API does not yet support symbol tables
    (so the transformations are written to cope with that).

    :param psy: the PSy object which this script will transform.
    :type psy: :py:class:`psyclone.psyGen.PSy`
    :returns: the transformed PSy object.
    :rtype: :py:class:`psyclone.psyGen.PSy`

    '''

    abs_trans = NemoAbsTrans()
    sign_trans = NemoSignTrans()
    min_trans = NemoMinTrans()

    sir_writer = SIRWriter()
    # For each Invoke write out the SIR representation of the
    # schedule. Note, there is no algorithm layer in the NEMO API so
    # the invokes represent all of the original code.
    for invoke in psy.invokes.invoke_list:
        sched = invoke.schedule
        for kernel in sched.walk(NemoKern):

            # The NEMO api currently has no symbol table so create one
            # to allow the generation of new variables. Note, this
            # does not guarantee unique names as we don't know any of
            # the existing names (so generated names could clash).
            symbol_table = SymbolTable()

            kernel_schedule = kernel.get_kernel_schedule()
            for oper in kernel_schedule.walk(UnaryOperation):
                if oper.operator == UnaryOperation.Operator.ABS:
                    # Apply ABS transformation
                    abs_trans.apply(oper, symbol_table)
            for oper in kernel_schedule.walk(BinaryOperation):
                if oper.operator == BinaryOperation.Operator.SIGN:
                    # Apply SIGN transformation
                    sign_trans.apply(oper, symbol_table)
            for oper in kernel_schedule.walk(BinaryOperation):
                if oper.operator == BinaryOperation.Operator.MIN:
                    # Apply (2-arg) MIN transformation
                    min_trans.apply(oper, symbol_table)
            for oper in kernel_schedule.walk(NaryOperation):
                if oper.operator == NaryOperation.Operator.MIN:
                    # Apply (n-arg) MIN transformation
                    min_trans.apply(oper, symbol_table)
        kern = sir_writer(sched)
        print(kern)

    return psy

