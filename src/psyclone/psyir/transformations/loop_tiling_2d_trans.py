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
# Author: S. Siso, STFC Daresbury Lab
# -----------------------------------------------------------------------------

'''This module provides the LoopTiling2DTrans, which transforms a 2D Loop
construct into a tiled implementation of the construct.'''

from psyclone.psyir.nodes import Loop
from psyclone.psyir.transformations import LoopTrans, ChunkLoopTrans
from psyclone.psyir.transformations.transformation_error import \
        TransformationError


class LoopTiling2DTrans(LoopTrans):
    '''
    Apply a 2D loop tiling transformation to a loop. For example:

    >>> from psyclone.psyir.frontend.fortran import FortranReader
    >>> from psyclone.psyir.nodes import Loop
    >>> from psyclone.psyir.transformations import LoopTiling2DTrans
    >>> psyir = FortranReader().psyir_from_source("""
    ... subroutine sub()
    ...     integer :: ji, tmp(100)
    ...     do i=1, 100
    ...       do j=1, 100
    ...         tmp(i, j) = 2 * tmp(i, j)
    ...       enddo
    ...     enddo
    ... end subroutine sub""")
    >>> loop = psyir.walk(Loop)[0]
    >>> LoopTiling2DTrans().apply(loop)

    will generate:

    .. code-block:: fortran

        subroutine sub()
            integer :: ji
            integer, dimension(100) :: tmp
            integer :: ji_el_inner
            integer :: ji_out_var
            do i_out_var = 1, 100, 32
              do j_out_var = 1, 100, 32
                i_el_inner = MIN(i_out_var + 32, 100)
                j_el_inner = MIN(j_out_var + 32, 100)
                do i = i_out_var, i_el_inner, 1
                  do j = j_out_var, j_el_inner, 1
                    tmp(i, j) = 2 * tmp(i, j)
                  enddo
                enddo
              enddo
            enddo
        end subroutine sub

    '''
    def __str__(self):
        return "Tile the loop construct using 2D blocks"

    def validate(self, node, options=None):
        '''
        Validates that the given Loop node can have a LoopTiling2DTrans
        applied.

        :param node: the loop to validate.
        :type node: :py:class:`psyclone.psyir.nodes.Loop`
        :param options: a dict with options for transformation.
        :type options: dict of str:values or None
        :param int options["tilesize"]: The size to tile size for this \
                transformation. If not specified, the value 32 is used.
        '''
        if options is None:
            options = {}
        super(LoopTiling2DTrans, self).validate(node, options=options)
        tilesize = options.get("tilesize", 32)

        outer_loop = node
        if len(node.loop_body.children) != 1:
            raise TransformationError("")

        if not isinstance(node.loop_body.children[0], Loop):
            raise TransformationError("")

        inner_loop = node.loop_body.children[0]

        ChunkLoopTrans().validate(outer_loop, options={'chuncksize': tilesize})
        ChunkLoopTrans().validate(inner_loop, options={'chuncksize': tilesize})

    def apply(self, node, options=None):
        '''
        Converts the given 2D Loop construct into a tiled version of the nested
        loops.

        :param node: the loop to transform.
        :type node: :py:class:`psyclone.psyir.nodes.Loop`
        :param options: a dict with options for transformations.
        :type options: dict of str:values or None
        :param int options["tilesize"]: The size to tile for this \
                transformation. If not specified, the value 32 is used.

        '''
        self.validate(node, options)
        if options is None:
            options = {}
        tilesize = options.get("tilesize", 32)
        parent = node.parent
        position = node.position
        outer_loop = node
        inner_loop = node.loop_body.children[0]

        ChunkLoopTrans().apply(outer_loop, options={'chuncksize': tilesize})
        ChunkLoopTrans().apply(inner_loop, options={'chuncksize': tilesize})

        from psyclone.psyir.transformations import LoopSwapTrans
        loops = parent[position].walk(Loop)[1]
        LoopSwapTrans().apply(loops)
