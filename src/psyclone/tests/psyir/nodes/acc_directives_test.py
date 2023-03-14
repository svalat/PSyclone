# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021-2022, Science and Technology Facilities Council.
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
# Authors R. W. Ford, A. R. Porter, S. Siso and N. Nobre, STFC Daresbury Lab
# Modified I. Kavcic, Met Office
# Modified A. B. G. Chalk, STFC Daresbury Lab
# -----------------------------------------------------------------------------

''' Performs py.test tests on the OpenACC PSyIR Directive nodes. '''

from __future__ import absolute_import
import os
import pytest

from psyclone.configuration import Config
from psyclone.core import Signature
from psyclone.errors import GenerationError
from psyclone.f2pygen import ModuleGen
from psyclone.parse.algorithm import parse
from psyclone.psyGen import PSyFactory
from psyclone.psyir.nodes import ACCRoutineDirective, \
    ACCKernelsDirective, Schedule, ACCUpdateDirective, ACCLoopDirective, \
    ACCWaitDirective, Routine, ACCParallelDirective
from psyclone.psyir.symbols import SymbolTable
from psyclone.transformations import ACCEnterDataTrans, ACCParallelTrans, \
    ACCKernelsTrans

BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "test_files", "dynamo0p3")


@pytest.fixture(scope="module", autouse=True)
def setup():
    '''Make sure that all tests here use a new Config instance.'''
    Config._instance = None
    yield
    Config._instance = None

# Class ACCEnterDataDirective start

# (1/4) Method gen_code
def test_accenterdatadirective_gencode_1():
    '''Test that an OpenACC Enter Data directive, when added to a schedule
    with a single loop, raises the expected exception as there is no
    following OpenACC Parallel or OpenACC Kernels directive as at
    least one is required. This test uses the dynamo0.3 API.

    '''
    acc_enter_trans = ACCEnterDataTrans()
    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0_testkern_type').schedule
    acc_enter_trans.apply(sched)
    with pytest.raises(GenerationError) as excinfo:
        str(psy.gen)
    assert ("ACCEnterData directive did not find any data to copyin. Perhaps "
            "there are no ACCParallel or ACCKernels directives within the "
            "region?" in str(excinfo.value))

    # Test that the same error is produced by the begin_string() which is used
    # by the PSyIR backend
    sched[0].lower_to_language_level()
    with pytest.raises(GenerationError) as excinfo:
        sched[0].begin_string()
    assert ("ACCEnterData directive did not find any data to copyin. Perhaps "
            "there are no ACCParallel or ACCKernels directives within the "
            "region?" in str(excinfo.value))


# (2/4) Method gen_code
def test_accenterdatadirective_gencode_2():
    '''Test that an OpenACC Enter Data directive, when added to a schedule
    with multiple loops, raises the expected exception, as there is no
    following OpenACC Parallel or OpenACCKernels directive and at
    least one is required. This test uses the dynamo0.3 API.

    '''
    acc_enter_trans = ACCEnterDataTrans()
    _, info = parse(os.path.join(BASE_PATH, "1.2_multi_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0').schedule
    acc_enter_trans.apply(sched)
    with pytest.raises(GenerationError) as excinfo:
        str(psy.gen)
    assert ("ACCEnterData directive did not find any data to copyin. Perhaps "
            "there are no ACCParallel or ACCKernels directives within the "
            "region?" in str(excinfo.value))


# (3/4) Method gen_code
@pytest.mark.parametrize("trans", [ACCParallelTrans, ACCKernelsTrans])
def test_accenterdatadirective_gencode_3(trans):
    '''Test that an OpenACC Enter Data directive, when added to a schedule
    with a single loop, produces the expected code (there should be
    "copy in" data as there is a following OpenACC parallel or kernels
    directive). This test uses the dynamo0.3 API.

    '''
    acc_trans = trans()
    acc_enter_trans = ACCEnterDataTrans()
    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0_testkern_type').schedule
    acc_trans.apply(sched.children)
    acc_enter_trans.apply(sched)
    code = str(psy.gen)
    assert (
        "      !$acc enter data copyin(f1_proxy,f1_proxy%data,"
        "f2_proxy,f2_proxy%data,m1_proxy,m1_proxy%data,m2_proxy,"
        "m2_proxy%data,map_w1,map_w2,map_w3,ndf_w1,ndf_w2,ndf_w3,nlayers,"
        "undf_w1,undf_w2,undf_w3)\n" in code)


# (4/4) Method gen_code
@pytest.mark.parametrize("trans1,trans2",
                         [(ACCParallelTrans, ACCParallelTrans),
                          (ACCParallelTrans, ACCKernelsTrans),
                          (ACCKernelsTrans, ACCParallelTrans),
                          (ACCKernelsTrans, ACCKernelsTrans)])
def test_accenterdatadirective_gencode_4(trans1, trans2):
    '''Test that an OpenACC Enter Data directive, when added to a schedule
    with multiple loops and multiple OpenACC parallel and/or Kernel
    directives, produces the expected code (when the same argument is
    used in multiple loops there should only be one entry). This test
    uses the dynamo0.3 API.

    '''
    acc_trans1 = trans1()
    acc_trans2 = trans2()
    acc_enter_trans = ACCEnterDataTrans()
    _, info = parse(os.path.join(BASE_PATH, "1.2_multi_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0').schedule
    acc_trans1.apply([sched.children[1]])
    acc_trans2.apply([sched.children[0]])
    acc_enter_trans.apply(sched)
    code = str(psy.gen)
    assert (
        "      !$acc enter data copyin(f1_proxy,f1_proxy%data,"
        "f2_proxy,f2_proxy%data,f3_proxy,f3_proxy%data,m1_proxy,m1_proxy%data,"
        "m2_proxy,m2_proxy%data,map_w1,map_w2,map_w3,ndf_w1,ndf_w2,ndf_w3,"
        "nlayers,undf_w1,undf_w2,undf_w3)\n" in code)

# (3/4) Method gen_code
def test_accenterdatadirective_gencode_3_async():
    '''Test that we can acc the async directive on enter data.
    '''
    acc_trans = ACCKernelsTrans()
    acc_enter_trans = ACCEnterDataTrans()
    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0_testkern_type').schedule
    acc_trans.apply(sched.children)
    acc_enter_trans.apply(sched, options = {"async_queue": 3})
    code = str(psy.gen)
    assert (
        "      !$acc enter data copyin(f1_proxy,f1_proxy%data,"
        "f2_proxy,f2_proxy%data,m1_proxy,m1_proxy%data,m2_proxy,"
        "m2_proxy%data,map_w1,map_w2,map_w3,ndf_w1,ndf_w2,ndf_w3,nlayers,"
        "undf_w1,undf_w2,undf_w3) async(3)\n" in code)

# Class ACCLoopDirective start

def test_accloopdirective_node_str(monkeypatch):
    ''' Test the node_str() method of ACCLoopDirective node '''
    directive = ACCLoopDirective()

    # Mock the coloured name as this is tested elsewhere
    monkeypatch.setattr(directive, "coloured_name",
                        lambda x: "ACCLoopDirective")

    # Default value output
    expected = ("ACCLoopDirective[sequential=False,collapse=None,"
                "independent=True]")
    assert directive.node_str() == expected
    assert str(directive) == expected

    # Non-default value output
    directive._sequential = True
    directive._collapse = 2
    directive._independent = False
    expected = ("ACCLoopDirective[sequential=True,collapse=2,"
                "independent=False]")
    assert directive.node_str() == expected
    assert str(directive) == expected


def test_accloopdirective_collapse_getter_and_setter():
    ''' Test the ACCLoopDirective collapse property setter and getter.'''
    target = ACCLoopDirective()
    assert target.collapse is None
    target.collapse = 3
    assert target.collapse == 3
    target.collapse = None
    assert target.collapse is None

    with pytest.raises(ValueError) as err:
        target.collapse = 0
    assert ("The ACCLoopDirective collapse clause must be a positive integer "
            "or None, but value '0' has been given." in str(err.value))

    with pytest.raises(TypeError) as err:
        target.collapse = 'a'
    assert ("The ACCLoopDirective collapse clause must be a positive integer "
            "or None, but value 'a' has been given." in str(err.value))


def test_accloopdirective_equality():
    ''' Test the __eq__ method of ACCLoopDirective node. '''
    # We need to manually set the same SymbolTable instance in both directives
    # for their equality to be True
    symboltable = SymbolTable()
    directive1 = ACCLoopDirective()
    directive2 = ACCLoopDirective()
    directive1.children[0]._symbol_table = symboltable
    directive2.children[0]._symbol_table = symboltable
    assert directive1 == directive2

    # Check equality fails when collapse is different
    directive2._collapse = 2
    assert directive1 != directive2

    # Check equality fails when independent is different
    directive2._collapse = directive1.collapse
    directive2._independent = False
    assert directive1 != directive2

    # Check equality fails when sequential is different
    directive2._independent = directive1.independent
    directive2._sequential = not directive1._sequential
    assert directive1 != directive2

# Class ACCLoopDirective end


# Class ACCKernelsDirective start

# (1/1) Method __init__
def test_acckernelsdirective_init():
    '''Test an ACCKernelsDirective can be created and that the optional
    arguments are set and can be set as expected.

    '''
    directive = ACCKernelsDirective()
    assert directive._default_present
    assert directive.parent is None
    assert len(directive.children) == 1
    assert isinstance(directive.children[0], Schedule)
    directive = ACCKernelsDirective(default_present=False)
    assert not directive._default_present


# (1/1) Method gen_code
@pytest.mark.parametrize("default_present", [False, True])
def test_acckernelsdirective_gencode(default_present):
    '''Check that the gen_code method in the ACCKernelsDirective class
    generates the expected code. Use the dynamo0.3 API.

    '''
    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0_testkern_type').schedule

    trans = ACCKernelsTrans()
    trans.apply(sched, {"default_present": default_present})

    code = str(psy.gen)
    string = ""
    if default_present:
        string = " default(present)"
    assert (
        f"      !$acc kernels{string}\n"
        f"      DO cell=loop0_start,loop0_stop\n" in code)
    assert (
        "      END DO\n"
        "      !$acc end kernels\n" in code)

# (1/1) Method gen_code
@pytest.mark.parametrize("async_queue", [False, 1, Signature('stream1')])
def test_acckernelsdirective_gencode(async_queue):
    '''Check that the gen_code method in the ACCKernelsDirective class
    generates the expected code. Use the dynamo0.3 API.

    '''
    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    sched = psy.invokes.get('invoke_0_testkern_type').schedule

    trans = ACCKernelsTrans()
    trans.apply(sched, {"async_queue": async_queue})

    code = str(psy.gen)
    string = ""
    if async_queue:
        if isinstance(async_queue, int):
            string = " async(1)"
        elif isinstance(async_queue, Signature):
            string = " async(stream1)"
    assert (
        f"      !$acc kernels{string}\n"
        f"      DO cell=loop0_start,loop0_stop\n" in code)
    assert (
        "      END DO\n"
        "      !$acc end kernels\n" in code)

def test_acckerneldirective_equality():
    ''' Test the __eq__ method of ACCKernelsDirective node. '''
    # We need to manually set the same SymbolTable instance in both directives
    # for their equality to be True
    symboltable = SymbolTable()
    directive1 = ACCKernelsDirective()
    directive2 = ACCKernelsDirective()
    directive1.children[0]._symbol_table = symboltable
    directive2.children[0]._symbol_table = symboltable
    assert directive1 == directive2

    # Check equality fails when default_present is different
    directive2._default_present = not directive1._default_present
    assert directive1 != directive2

# Class ACCRoutineDirective


def test_acc_routine_directive_constructor_and_strings():
    ''' Test the ACCRoutineDirective constructor and its output
    strings.'''
    target = ACCRoutineDirective()
    assert target.begin_string() == "acc routine"
    assert str(target) == "ACCRoutineDirective[]"

    temporary_module = ModuleGen("test")
    target.gen_code(temporary_module)
    assert "!$acc routine\n" in str(temporary_module.root)


# Class ACCUpdateDirective

def test_accupdatedirective_init():
    ''' Test the constructor of ACCUpdateDirective node. '''

    # Check argument validations
    with pytest.raises(TypeError) as err:
        _ = ACCUpdateDirective({"invalid"}, "host")
    assert ("The ACCUpdateDirective signatures argument must be a "
            "set of signatures but got {'str'}"
            in str(err.value))

    sig = {Signature("x")}
    with pytest.raises(ValueError) as err:
        _ = ACCUpdateDirective(sig, "invalid")
    assert ("The ACCUpdateDirective direction argument must be a string with "
            "any of the values in '('self', 'host', 'device')' but found "
            "'invalid'." in str(err.value))

    with pytest.raises(TypeError) as err:
        _ = ACCUpdateDirective(sig, "host", if_present=1)
    assert ("The ACCUpdateDirective if_present argument must be a "
            "boolean but got int"
            in str(err.value))

    # Successful init
    directive = ACCUpdateDirective(sig, "host")
    assert directive.sig_set == sig
    assert directive.direction == "host"
    assert directive.if_present is True

    directive = ACCUpdateDirective(sig, "host", if_present=False)
    assert directive.if_present is False
    assert directive.async_queue is False

    directive = ACCUpdateDirective(sig, "host", async_queue=True)
    assert directive.async_queue is True

    directive = ACCUpdateDirective(sig, "host", async_queue=1)
    assert directive.async_queue == 1

    directive = ACCUpdateDirective(sig, "host", async_queue=Signature("var"))
    assert directive.async_queue == Signature("var")


def test_accupdatedirective_begin_string():
    ''' Test the begin_string method of ACCUpdateDirective. '''

    sig = {Signature("x")}
    directive_host = ACCUpdateDirective(sig, "host", if_present=False)
    directive_device = ACCUpdateDirective(sig, "device")
    directive_empty = ACCUpdateDirective(set(), "host", if_present=False)
    directive_async_default = ACCUpdateDirective(sig, "device", async_queue=True)
    directive_async_queue_int = ACCUpdateDirective(sig, "device", async_queue=1)
    directive_async_queue_str = ACCUpdateDirective(sig, "device", async_queue=Signature("var"))

    assert directive_host.begin_string() == "acc update host(x)"
    assert directive_device.begin_string() == "acc update if_present device(x)"
    assert directive_async_default.begin_string() == "acc update if_present device(x) async()"
    assert directive_async_queue_int.begin_string() == "acc update if_present device(x) async(1)"
    assert directive_async_queue_str.begin_string() == "acc update if_present device(x) async(var)"

    with pytest.raises(GenerationError) as err:
        directive_empty.begin_string()
    assert ("ACCUpdate directive did not find any data to update."
            in str(err.value))


def test_accupdatedirective_equality():
    ''' Test the __eq__ method of ACCUpdateDirective node. '''
    sig = {Signature("x")}
    directive1 = ACCUpdateDirective(sig, "device")
    directive2 = ACCUpdateDirective(sig, "device")
    assert directive1 == directive2

    # Check equality fails when different signatures
    directive3 = ACCUpdateDirective({Signature("t")}, "device")
    assert directive1 != directive3

    # Check equality fails when different directions
    directive4 = ACCUpdateDirective(sig, "host")
    assert directive1 != directive4

    # Check equality fails when different if_present settings
    directive5 = ACCUpdateDirective(sig, "device", if_present=False)
    assert directive1 != directive5


# Class ACCWaitDirective

def test_accwaitdirective_init():
    '''Test init of ACCWaitDirective.'''

    directive1 = ACCWaitDirective(None)
    assert directive1.wait_queue == None

    directive2 = ACCWaitDirective(None)
    assert directive2.wait_queue == None

    directive4 = ACCWaitDirective(1)
    assert directive4.wait_queue == 1

    directive4 = ACCWaitDirective(Signature("variable_name"))
    assert directive4.wait_queue == Signature("variable_name")

    with pytest.raises(TypeError):
        directive5 = ACCWaitDirective(3.5)

def test_accwaitdirective_begin_string():
    '''Test begin_string of ACCWaitDirective.'''

    directive1 = ACCWaitDirective(None)
    assert directive1.begin_string() == "acc wait"

    directive2 = ACCWaitDirective(None)
    assert directive2.begin_string() == "acc wait"

    directive3 = ACCWaitDirective(1)
    assert directive3.begin_string() == "acc wait (1)"

    directive4 = ACCWaitDirective(Signature("variable_name"))
    assert directive4.begin_string() == "acc wait (variable_name)"

def test_accwaitdirective_gencode():
    '''Test gen code of ACCWaitDirective'''

    _, info = parse(os.path.join(BASE_PATH, "1_single_invoke.f90"))
    psy = PSyFactory(distributed_memory=False).create(info)
    routines = psy.container.walk(Routine)
    routines[0].children.append(ACCWaitDirective(1))
    code = str(psy.gen)
    assert '$acc wait (1)' in code

def test_accwaitdirective_eq():
    '''Test the __eq__ implementation of ACCWaitDirective.'''

    # build some
    directive1 = ACCWaitDirective(1)
    directive2 = ACCWaitDirective(1)
    directive3 = ACCWaitDirective(Signature('stream1'))

    # check equality
    assert directive1 == directive2
    assert not (directive1 == directive3)

# async keyword on all classes

@pytest.mark.parametrize("directive_type", [ACCKernelsDirective, ACCParallelDirective, ACCUpdateDirective])
def test_directives_async_queue(directive_type):
    '''Validate the various usage of async_queue parameter'''

    # args
    args = []
    if directive_type == ACCUpdateDirective:
        args = [[Signature('x')], 'host']

    # set value at init
    directive = directive_type(*args, async_queue=1)
    assert directive.async_queue == 1
    assert 'async(1)' in directive.begin_string()

    # change value to true
    directive.async_queue = True
    assert directive.async_queue == True
    assert 'async()' in directive.begin_string()

    # change value to False
    directive.async_queue = False
    assert directive.async_queue == False
    assert not 'async()' in directive.begin_string()

    # change value to None
    directive.async_queue = None
    assert directive.async_queue == None
    assert not 'async()' in directive.begin_string()

    # change value afterward
    directive.async_queue = Signature("stream")
    assert directive.async_queue == Signature("stream")
    assert 'async(stream)' in directive.begin_string()

    # put wrong type
    with pytest.raises(TypeError) as error:
        directive.async_queue = 3.5
    assert "Invalid async_queue" in str(error)
