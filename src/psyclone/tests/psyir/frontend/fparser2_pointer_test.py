
# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2024, Science and Technology Facilities Council.
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

''' Performs py.test tests on the handling of pointers in the fparser2
    PSyIR front-end. '''

from psyclone.psyir.nodes import CodeBlock, Assignment


def test_pointer_assignments(fortran_reader):
    '''
    Test that an interface is handled correctly if it refers to symbols
    for which we don't have type information (because they are imported).
    '''
    test_module = '''
    subroutine mysub()
        use other_symbols
        integer, target :: a = 1
        integer, pointer :: b => null()

        c => a
        field(3,c)%pointer => b
    end subroutine
    '''
    file_container = fortran_reader.psyir_from_source(test_module)
    assert len(file_container.walk(CodeBlock)) == 0
    assignments = file_container.walk(Assignment)
    assert len(assignments) == 2
    for assignment in assignments:
        assert assignment.is_pointer is True

