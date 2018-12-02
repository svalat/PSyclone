#!/usr/bin/env python
# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2018, Science and Technology Facilities Council
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
# Authors: R. W. Ford and A. R. Porter, STFC Daresbury Lab

'''A simple test script showing the introduction of the OpenACC
kernels directive with PSyclone.  In order to use it you must first
install PSyclone. See README.md in the top-level psyclone directory.

Once you have psyclone installed, this script may be run by doing (you may
need to make it executable first with chmod u+x ./runme_openacc.py):

 >>> ./runme_openacc.py

This should generate a lot of output, ending with generated
Fortran.

'''

from __future__ import print_function
from psyclone.parse import parse
from psyclone.psyGen import PSyFactory, TransInfo
from psyclone.nemo import NemoKern, NemoLoop

if __name__ == "__main__":
    API = "nemo"
    _, INVOKEINFO = parse("tra_adv.F90", api=API)
    PSY = PSyFactory(API).create(INVOKEINFO)
    print(PSY.gen)

    print("Invokes found:")
    print(PSY.invokes.names)

    SCHED = PSY.invokes.get('tra_adv').schedule
    SCHED.view()

    TRANS_INFO = TransInfo()
    print(TRANS_INFO.list)

    ACC_TRANS = TRANS_INFO.get_trans_name('ACCKernelsTrans')

    SCHED, _ = ACC_TRANS.apply(SCHED.children)

    SCHED.view()

    ACC_TRANS = TRANS_INFO.get_trans_name('ACCLoopTrans')

    # Add loop directives over latitude and collapse when they are
    # doubly nested with longitude inner. Default to independent. We
    # need to extend our dependence analysis to perform checks.
    count = 0 
    for loop in SCHED.loops():
        kernels = loop.walk(loop.children, NemoKern)
        if kernels and loop.loop_type == "lat":
            count += 1
            if count == 14:
                # puts ACC declation in the wrong place as the loop structures are the same.
                continue
            child = loop.children[0]
            if isinstance(child, NemoLoop) and child.loop_type == "lon":
                SCHED, _ = ACC_TRANS.apply(loop, collapse=2)
            else:
                SCHED, _ = ACC_TRANS.apply(loop)

    SCHED.view()

    ACC_TRANS = TRANS_INFO.get_trans_name('ACCParallelTrans')

    for loop in SCHED.loops():
        kernels = loop.walk(loop.children, NemoKern)
        if kernels and loop.loop_type == "levels":
            SCHED, _ = ACC_TRANS.apply(loop)

    SCHED.view()

    PSY.invokes.get('tra_adv').schedule = SCHED
    print(PSY.gen)
