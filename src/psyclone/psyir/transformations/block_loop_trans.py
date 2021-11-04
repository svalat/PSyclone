# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021, Science and Technology Facilities Council.
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
# Authors A. B. G. Chalk STFC Daresbury Lab
# -----------------------------------------------------------------------------

'''This module provides the BlockLoopTrans, which transforms a Loop into a
blocked implementation of the Loop'''

from psyclone.core import VariablesAccessInfo, Signature, AccessType
from psyclone.psyir import nodes
from psyclone.psyir.nodes import Assignment, BinaryOperation, Reference, \
        Literal, Loop, Schedule
from psyclone.psyir.symbols import DataSymbol, ScalarType
from psyclone.psyir.transformations.loop_trans import LoopTrans
from psyclone.psyir.transformations.transformation_error import \
        TransformationError


class BlockLoopTrans(LoopTrans):
    '''
    Apply a blocking transformation to a loop (in order to permit a
    chunked parallelisation or improve cache utilisation). For example:

    >>> from psyclone.psyir.frontend.fortran import FortranReader
    >>> from psyclone.psyir.nodes import Loop
    >>> from psyclone.psyir.transformations import BlockLoopTrans
    >>> psyir = FortranReader().psyir_from_source("""
    ... subroutine sub()
    ...     integer :: ji, tmp(100)
    ...     do ji=1, 100
    ...         tmp(ji) = 2 * ji
    ...     enddo
    ... end subroutine sub""")
    >>> loop = psyir.walk(Loop)[0]
    >>> BlockLoopTrans().apply(loop)

    will generate:
    .. code-block:: fortran
        subroutine sub()
            integer :: ji
            integer, dimension(100) :: tmp
            integer :: ji_el_inner
            integer :: ji_out_var

            do ji_out_var = 1, 100, 32
                ji_el_inner = MIN(ji_out_var + 32, 100)
                do ji = ji_out_var, ji_el_inner, 1
                    tmp(ji) = 2 * ji
                enddo
            enddo

        end subroutine sub
    '''
    def __str__(self):
        return "Split a loop into a blocked loop pair"

    def validate(self, node, options=None):
        '''
        Validates that the given Loop node can have a BlockLoopTrans applied.

        :param node: the loop to validate.
        :type node: :py:class:`psyclone.psyir.nodes.Loop`
        :param options: a dict with options for transformation.
        :type options: dict of string:values or None
        :param int options["blocksize"]: The size to block over for this \
                transformation. If not specified, the value 32 is used.

        :raises TransformationError: if the supplied Loop has a step size \
                which is not a constant value.
        :raises TransformationError: if the supplied Loop has a non-integer \
                step size.
        :raises TransformationError: if the supplied Loop has a step size \
                larger than the chosen block size.
        :raises TransformationError: if the supplied Loop is a blocked loop.
        :raises TransformationError: if the supplied Loop has a step size \
                of 0.
        :raises TransformationError: if the supplied Loop writes to Loop \
                variables inside the Loop body.
        '''
        super(BlockLoopTrans, self).validate(node, options=options)
        if options is None:
            options = {}
        if not isinstance(node.children[2], nodes.Literal):
            # If step is a variable we don't support it.
            raise TransformationError("Cannot apply a BlockLoopTrans to "
                                      "a loop with a non-constant step size.")
        if node.children[2].datatype.intrinsic is not \
           ScalarType.Intrinsic.INTEGER:
            raise TransformationError("Cannot apply a BlockLoopTrans to a "
                                      "loop with a non-integer step size.")
        block_size = options.get("blocksize", 32)
        if abs(int(node.children[2].value)) > abs(block_size):
            raise TransformationError("Cannot apply a BlockLoopTrans to "
                                      "a loop with larger step size ({0}) "
                                      "than the chosen block size ({1})."
                                      .format(node.children[2].value,
                                              block_size))
        if 'blocked' in node.annotations:
            raise TransformationError("Cannot apply a BlockLoopTrans to "
                                      "an already blocked loop.")

        if int(node.children[2].value) == 0:
            raise TransformationError("Cannot apply a BlockLoopTrans to "
                                      "a loop with a step size of 0.")
        # Other checks needed for validation
        # Dependency analysis, following rules:
        # No child has a write dependency to the loop variable.
        # Find variable access info for the loop variable and step
        refs = VariablesAccessInfo(node.children[0])
        bounds_ref = VariablesAccessInfo()
        if refs is not None:
            bounds_ref.merge(refs)
        refs = VariablesAccessInfo(node.children[1])
        if refs is not None:
            bounds_ref.merge(refs)
        # The current implementation of BlockedLoopTrans does not allow
        # the step size to be non-constant, so it is ignored.

        # Add the access pattern to the node variable name
        bounds_ref.add_access(Signature(node.variable.name),
                              AccessType.READWRITE, self)

        bounds_sigs = bounds_ref.all_signatures

        # Find the Loop code's signatures
        body_refs = VariablesAccessInfo(node.children[3])
        body_sigs = body_refs.all_signatures

        for ref1 in bounds_sigs:
            if ref1 not in body_sigs:
                continue
            access2 = body_refs[ref1]

            # If access2 is a write then we write to a loop variable
            if access2.is_written():
                raise TransformationError("Cannot apply a BlockedLoopTrans "
                                          "to this loop because the boundary "
                                          "variable '{0}' is written to "
                                          "inside the loop body.".format(
                                              access2.signature.var_name))

    def apply(self, node, options=None):
        '''
        Converts the given Loop node into a nested loop where the outer
        loop is over blocks and the inner loop is over each individual element
        of the block.

        :param node: the loop to transform.
        :type node: :py:class:`psyclone.psyir.nodes.Loop`
        :param options: a dict with options for transformations.
        :type options: dict of string:values or None
        :param int options["blocksize"]: The size to block over for this \
                transformation. If not specified, the value 32 is used.

        :returns: Tuple of None and None
        :rtype: (None, None)
        '''

        self.validate(node, options)
        if options is None:
            options = {}
        block_size = options.get("blocksize", 32)
        # Create (or find) the symbols we need for the blocking transformation
        routine = node.ancestor(nodes.Routine)
        end_inner_loop = routine.symbol_table.symbol_from_tag(
                "{0}_el_inner".format(node.variable.name),
                symbol_type=DataSymbol,
                datatype=node.variable.datatype)
        outer_loop_variable = routine.symbol_table.symbol_from_tag(
                "{0}_out_var".format(node.variable.name),
                symbol_type=DataSymbol,
                datatype=node.variable.datatype)
        # We currently don't allow BlockedLoops to be ancestors of BlockedLoop
        # so our ancestors cannot use these variables.

        # Store the node's parent for replacing later and the start and end
        # indicies
        start = node.children[0]
        stop = node.children[1]

        # For positive steps we do el_inner = min(out_var+block_size, el_outer)
        # For negative steps we do el_inner = max(out_var-block_size, el_outer)
        if int(node.children[2].value) > 0:
            add = BinaryOperation.create(BinaryOperation.Operator.ADD,
                                         Reference(outer_loop_variable),
                                         Literal("{0}".format(block_size),
                                                 node.variable.datatype))
            minop = BinaryOperation.create(BinaryOperation.Operator.MIN, add,
                                           stop.copy())
            inner_loop_end = Assignment.create(Reference(end_inner_loop),
                                               minop)
        elif int(node.children[2].value) < 0:
            sub = BinaryOperation.create(BinaryOperation.Operator.SUB,
                                         Reference(outer_loop_variable),
                                         Literal("{0}".format(block_size),
                                                 node.variable.datatype))
            maxop = BinaryOperation.create(BinaryOperation.Operator.MAX, sub,
                                           stop.copy())
            inner_loop_end = Assignment.create(Reference(end_inner_loop),
                                               maxop)
            # block_size needs to be negative if we're reducing
            block_size = -block_size
        # step size of 0 is caught by the validate call

        # Replace the inner loop start and end with the blocking ones
        start.replace_with(Reference(outer_loop_variable))
        stop.replace_with(Reference(end_inner_loop))

        # Create the outerloop of the same type and loop_type
        outerloop = Loop(variable=outer_loop_variable,
                         valid_loop_types=node.valid_loop_types)
        outerloop.children = [start, stop,
                              Literal("{0}".format(block_size),
                                      outer_loop_variable.datatype),
                              Schedule(parent=outerloop,
                                       children=[inner_loop_end])]
        if node.loop_type is not None:
            outerloop.loop_type = node.loop_type
        # Add the blocked annotation
        outerloop.annotations.append('blocked')
        node.annotations.append('blocked')
        # Replace this loop with the outerloop
        node.replace_with(outerloop)
        # Add the loop to the innerloop's schedule
        outerloop.children[3].addchild(node)

        return None, None
