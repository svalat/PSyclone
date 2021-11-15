# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2021, Science and Technology Facilities Council.
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
# Author: J. Henrichs, Bureau of Meteorology
# Modified: A. R. Porter and R. W. Ford  STFC Daresbury Lab
# Modified: I. Kavcic, Met Office


''' Module containing py.test tests for dependency analysis.'''

from __future__ import print_function, absolute_import

import os
import pytest
from sympy import simplify
from sympy.parsing.sympy_parser import parse_expr

from fparser.common.readfortran import FortranStringReader

from psyclone.core import SymbolicMaths
from psyclone.psyGen import PSyFactory

# Constants
API = "nemo"
# Location of the Fortran files associated with these tests
BASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "test_files")


def test_sym_maths_get():
    '''Makes sure that the getter works as expected, especially
    that sympy can be imported.'''

    sym_maths = SymbolicMaths.get()
    assert sym_maths is not None

    assert not sym_maths.equal(None, 1)
    assert not sym_maths.equal(2, None)


@pytest.mark.parametrize("expressions", [("i", "i"),
                                         ("2", "1+1"),
                                         ("2.0", "1.1+0.9"),
                                         ("2", "1+7*i-3-4*i-3*i+4"),
                                         ("i+j", "j+i"),
                                         ("i+j+k", "i+k+j"),
                                         ("i+i", "2*i"),
                                         ("i+j-2*k+3*j-2*i", "-i+4*j-2*k"),
                                         ("max(1, 2, 3)", "max(1, 2, 3)")
                                         ])
def test_math_equal(parser, expressions):
    '''Test that the sympy based comparison handles complex
    expressions that are equal.

    '''
    # A dummy program to easily create the PSyIR for the
    # expressions we need. We just take the RHS of the assignments
    reader = FortranStringReader('''program test_prog
                                    use some_mod
                                    integer :: i, j, k, x
                                    type(my_mod_type) :: a, b
                                    x = {0}
                                    x = {1}
                                    end program test_prog
                                 '''.format(expressions[0],
                                            expressions[1]))
    prog = parser(reader)
    psy = PSyFactory("nemo", distributed_memory=False).create(prog)
    schedule = psy.invokes.get("test_prog").schedule

    sym_maths = SymbolicMaths.get()
    assert sym_maths.equal(schedule[0].rhs, schedule[1].rhs)


@pytest.mark.parametrize("expressions", [("a%b", "a%b"),
                                         ("a%b(i)", "a%b(i)"),
                                         ("a%b(2*i)", "a%b(3*i-i)"),
                                         ("a%b(i-1)%c(j+1)",
                                          "a%b(-1+i)%c(1+j)"),
                                         ("c(i,j)%b(i,j)", "c(i,j)%b(i,j)"),
                                         ("c(i+k,j-1-2*j)%b(2*i-i,j+3*k)",
                                          "c(k+i,-1-j)%b(i,3*k+j)"),
                                         ("a%b(a%b,a%b,a%b)",
                                          "a%b(a%b,a%b,a%b)"),
                                         ("a%b%c%d", "a%b%c%d")
                                         ])
def test_math_equal_structures(parser, expressions):
    '''Test that the sympy based comparison handles structures as expected.

    '''
    # A dummy program to easily create the PSyIR for the
    # expressions we need. We just take the RHS of the assignments
    reader = FortranStringReader('''program test_prog
                                    use some_mod
                                    integer :: i, j, k
                                    type(my_mod_type) :: a, b, c
                                    x = {0}
                                    x = {1}
                                    end program test_prog
                                 '''.format(expressions[0],
                                            expressions[1]))
    prog = parser(reader)
    psy = PSyFactory("nemo", distributed_memory=False).create(prog)
    schedule = psy.invokes.get("test_prog").schedule

    sym_maths = SymbolicMaths.get()
    assert sym_maths.equal(schedule[0].rhs, schedule[1].rhs)


@pytest.mark.parametrize("expressions", [("i", "0"),
                                         ("i", "j"),
                                         ("2", "1+1-1"),
                                         ("i+j", "j+i+1"),
                                         ("i-j", "j-i"),
                                         ("max(1, 2)", "max(1, 2, 3)")
                                         ])
def test_math_not_equal(parser, expressions):
    '''Test that the sympy based comparison handles complex
    expressions.

    '''
    # A dummy program to easily create the PSyIR for the
    # expressions we need. We just take the RHS of the assignments
    reader = FortranStringReader('''program test_prog
                                    use some_mod
                                    integer :: i, j, k, x
                                    type(my_mod_type) :: a, b
                                    x = {0}
                                    x = {1}
                                    end program test_prog
                                 '''.format(expressions[0],
                                            expressions[1]))

    sym_maths = SymbolicMaths.get()

    prog = parser(reader)
    psy = PSyFactory("nemo", distributed_memory=False).create(prog)
    schedule = psy.invokes.get("test_prog").schedule

    # Note we cannot use 'is False', since sym_maths returns an
    # instance of its own boolean type.
    assert not sym_maths.equal(schedule[0].rhs, schedule[1].rhs)


@pytest.mark.parametrize("expressions", [("a%b", "a%c"),
                                         ("a%b(i)", "a%b(i+1)"),
                                         ("a%b(i)%c(k)", "a%b(i+1)%c(k)"),
                                         ("a%b(i)%c(k)", "a%b(i)%c(k+1)"),
                                         ("a%b(i+1)%c(k)", "a%b(i)%c(k+1)"),
                                         ])
def test_math_not_equal_structures(parser, expressions):
    '''Test that the sympy based comparison handles complex
    expressions.

    '''
    # A dummy program to easily create the PSyIR for the
    # expressions we need. We just take the RHS of the assignments
    reader = FortranStringReader('''program test_prog
                                    use some_mod
                                    integer :: i, j, k, x
                                    type(my_mod_type) :: a, b
                                    x = {0}
                                    x = {1}
                                    end program test_prog
                                 '''.format(expressions[0],
                                            expressions[1]))

    sym_maths = SymbolicMaths.get()

    prog = parser(reader)
    psy = PSyFactory("nemo", distributed_memory=False).create(prog)
    schedule = psy.invokes.get("test_prog").schedule

    # Note we cannot use 'is False', since sym_maths returns an
    # instance of its own boolean type.
    assert not sym_maths.equal(schedule[0].rhs, schedule[1].rhs)


@pytest.mark.parametrize("expressions", [("max(3, 2, 1)", "max(1, 2, 3)"),
                                         ("max(1, 3)", "max(1, 2, 3)")
                                         ])
def test_math_functions_with_constants(parser, expressions):
    '''Test how known functions with constant values are handled.
    At this stage sympy can handle them, but the output format of
    the Fortran writer (all capitals, e.g. 'MAX') prevents this
    from working (sympy expects 'Max')

    '''
    # First show that sympy itself can handle known functions with
    # constant parameters, if they have the correct spelling:
    str_exp1 = parse_expr(expressions[0].replace("max", "Max"))
    str_exp2 = parse_expr(expressions[1].replace("max", "Max"))
    assert simplify(str_exp1 == str_exp2)

    # A dummy program to easily create the PSyIR for the
    # expressions we need. We just take the RHS of the assignments
    reader = FortranStringReader('''program test_prog
                                    use some_mod
                                    integer :: i, j, k, x
                                    type(my_mod_type) :: a, b
                                    x = {0}
                                    x = {1}
                                    end program test_prog
                                 '''.format(expressions[0],
                                            expressions[1]))

    sym_maths = SymbolicMaths.get()

    prog = parser(reader)
    psy = PSyFactory("nemo", distributed_memory=False).create(prog)
    schedule = psy.invokes.get("test_prog").schedule

    # Note we cannot use 'is False', since sym_maths returns an
    # instance of its own boolean type.
    if not sym_maths.equal(schedule[0].rhs, schedule[1].rhs):
        pytest.xfail("##### sympy does not yet handle known functions"
                     "with constant parameters correctly.")
