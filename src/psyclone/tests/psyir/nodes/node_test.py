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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab
#         I. Kavcic, Met Office
#         J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' Performs py.test tests on the Node PSyIR node. '''

from __future__ import absolute_import
import sys
import os
import re
import pytest
from psyclone.psyir.nodes.node import (ChildrenList, Node,
                                       _graphviz_digraph_class)
from psyclone.psyir.nodes import Schedule, Reference, Container, \
    Assignment, Return, Loop, Literal, Statement, node, KernelSchedule
from psyclone.psyir.symbols import DataSymbol, SymbolError, \
    INTEGER_TYPE, REAL_TYPE, SymbolTable
from psyclone.psyGen import PSyFactory, OMPDoDirective, Kern
from psyclone.errors import InternalError, GenerationError
from psyclone.parse.algorithm import parse
from psyclone.transformations import DynamoLoopFuseTrans
from psyclone.tests.utilities import get_invoke
# pylint: disable=redefined-outer-name
from psyclone.psyir.nodes.node import colored

BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "test_files", "dynamo0p3")


def test_node_abstract_methods():
    ''' Tests that the abstract methods of the Node class raise appropriate
    errors. '''
    _, invoke = get_invoke("single_invoke.f90", "gocean1.0", idx=0,
                           dist_mem=False)
    sched = invoke.schedule
    loop = sched.children[0].loop_body[0]
    with pytest.raises(NotImplementedError) as err:
        Node.gen_code(loop, parent=None)
    assert "Please implement me" in str(err.value)


def test_node_coloured_name():
    ''' Tests for the coloured_name method of the Node class. '''
    tnode = Node()
    # Node is an abstract class
    with pytest.raises(NotImplementedError) as err:
        tnode.node_str()
    assert ("_text_name is an abstract attribute which needs to be given a "
            "string value in the concrete class 'Node'." in str(err.value))

    # Exception as _colour has not been set
    tnode._text_name = "ATest"
    with pytest.raises(NotImplementedError) as err:
        _ = tnode.coloured_name()
    assert ("The _colour attribute is abstract so needs to be given a string "
            "value in the concrete class 'Node'." in str(err.value))
    # Exception as _colour has an invalid value (if the termcolor
    # module has been installed) otherwise silently ignore.
    # pylint: disable=reimported
    # pylint: disable=import-outside-toplevel
    tnode._colour = "invalid"
    try:
        from termcolor import colored
        with pytest.raises(InternalError) as err:
            _ = tnode.coloured_name()
        assert ("The _colour attribute in class 'Node' has been set to an "
                "unsupported colour 'invalid'." in str(err.value))
    except ImportError:
        _ = tnode.coloured_name()
    # reset import for further tests
    from psyclone.psyir.nodes.node import colored
    # Check that we can change the name of the Node and the colour associated
    # with it
    tnode._colour = "white"
    assert tnode.coloured_name(False) == "ATest"
    assert tnode.coloured_name(True) == colored("ATest", "white")


def test_node_str():
    ''' Tests for the Node.node_str method. '''
    tnode = Node()
    # Node is an abstract class
    with pytest.raises(NotImplementedError) as err:
        tnode.node_str()
    assert ("_text_name is an abstract attribute which needs to be given a "
            "string value in the concrete class 'Node'." in str(err.value))

    # Manually set the _text_name and _colour for this node to
    # something that will result in coloured output (if requested
    # *and* termcolor is installed).
    tnode._text_name = "FakeName"
    tnode._colour = "green"
    assert tnode.node_str(False) == "FakeName[]"
    assert tnode.node_str(True) == colored("FakeName", "green") + "[]"


def test_node_depth():
    '''
    Test that the Node class depth method returns the correct value for a
    Node in a tree. The start depth to determine a Node's depth is set to
    0. Depth of a Schedule is 1 and increases for its descendants.
    '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    # Assert that start_depth of any Node (including Schedule) is 0
    assert schedule.START_DEPTH == 0
    # Assert that Schedule depth is 1
    assert schedule.depth == 1
    # Depth increases by 1 for descendants at each level
    for child in schedule.children:
        assert child.depth == 2
    for child in schedule.children[3].children:
        assert child.depth == 3


def test_node_position():
    '''
    Test that the Node class position and abs_position methods return
    the correct value for a Node in a tree. The start position is
    set to 0. Relative position starts from 0 and absolute from 1.
    '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4.7_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    child = schedule.children[6]
    # Assert that position of a Schedule (no parent Node) is 0
    assert schedule.position == 0
    # Assert that start_position of any Node is 0
    assert child.START_POSITION == 0
    # Assert that relative and absolute positions return correct values
    assert child.position == 6
    assert child.abs_position == 7
    # Test InternalError for _find_position with an incorrect position
    with pytest.raises(InternalError) as excinfo:
        _, _ = child._find_position(child.root.children, -2)
    assert "started from -2 instead of 0" in str(excinfo.value)
    # Test InternalError for abs_position with a Node that does
    # not belong to the Schedule
    ompdir = OMPDoDirective()
    with pytest.raises(InternalError) as excinfo:
        _ = ompdir.abs_position
    assert ("PSyclone internal error: Error in search for Node position "
            "in the tree") in str(excinfo.value)


def test_node_root():
    '''
    Test that the Node class root method returns the correct instance
    for a Node in a tree.
    '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4.7_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    ru_schedule = invoke.schedule
    # Select a loop and the kernel inside
    ru_loop = ru_schedule.children[1]
    ru_kern = ru_loop.children[0]
    # Assert that the absolute root is a Schedule
    assert isinstance(ru_kern.root, Schedule)


def test_node_annotations():
    '''Test that an instance of the Node class raises an exception if an
    annotation is invalid. Note, any annotation will be invalid here
    as Node does not set a list of valid annotations (this is the job
    of the subclass).

    '''
    with pytest.raises(InternalError) as excinfo:
        _ = Node(annotations=["invalid"])
    assert (
        "Node with unrecognised annotation 'invalid', valid annotations are: "
        "()." in str(excinfo.value))


def test_node_args():
    '''Test that the Node class args method returns the correct arguments
    for Nodes that do not have arguments themselves'''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    loop1 = schedule.children[0]
    kern1 = loop1.loop_body[0]
    loop2 = schedule.children[1]
    kern2 = loop2.loop_body[0]
    # 1) Schedule (not that this is useful)
    all_args = kern1.arguments.args
    all_args.extend(kern2.arguments.args)
    schedule_args = schedule.args
    for idx, arg in enumerate(all_args):
        assert arg == schedule_args[idx]
    # 2) Loop1
    loop1_args = loop1.args
    for idx, arg in enumerate(kern1.arguments.args):
        assert arg == loop1_args[idx]
    # 3) Loop2
    loop2_args = loop2.args
    for idx, arg in enumerate(kern2.arguments.args):
        assert arg == loop2_args[idx]
    # 4) Loop fuse
    ftrans = DynamoLoopFuseTrans()
    ftrans.same_space = True
    schedule, _ = ftrans.apply(schedule.children[0], schedule.children[1])
    loop = schedule.children[0]
    kern1 = loop.loop_body[0]
    kern2 = loop.loop_body[1]
    loop_args = loop.args
    kern_args = kern1.arguments.args
    kern_args.extend(kern2.arguments.args)
    for idx, arg in enumerate(kern_args):
        assert arg == loop_args[idx]


def test_node_forward_dependence():
    '''Test that the Node class forward_dependence method returns the
    closest dependent Node after the current Node in the schedule or
    None if none are found.'''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.1_multi_aX_plus_Y_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    read4 = schedule.children[4]
    # 1: returns none if none found
    # a) check many reads
    assert not read4.forward_dependence()
    # b) check no dependencies for a call
    assert not read4.children[0].forward_dependence()
    # 2: returns first dependent kernel arg when there are many
    # dependencies
    # a) check first read returned
    writer = schedule.children[3]
    next_read = schedule.children[4]
    assert writer.forward_dependence() == next_read
    # a) check writer returned
    first_loop = schedule.children[0]
    assert first_loop.forward_dependence() == writer
    # 3: haloexchange dependencies
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4.5_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    prev_loop = schedule.children[7]
    halo_field = schedule.children[8]
    next_loop = schedule.children[9]
    # a) previous loop depends on halo exchange
    assert prev_loop.forward_dependence() == halo_field
    # b) halo exchange depends on following loop
    assert halo_field.forward_dependence() == next_loop

    # 4: globalsum dependencies
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.3_sum_setval_field_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    prev_loop = schedule.children[0]
    sum_loop = schedule.children[1]
    global_sum_loop = schedule.children[2]
    next_loop = schedule.children[3]
    # a) prev loop depends on sum loop
    assert prev_loop.forward_dependence() == sum_loop
    # b) sum loop depends on global sum loop
    assert sum_loop.forward_dependence() == global_sum_loop
    # c) global sum loop depends on next loop
    assert global_sum_loop.forward_dependence() == next_loop


def test_node_backward_dependence():
    '''Test that the Node class backward_dependence method returns the
    closest dependent Node before the current Node in the schedule or
    None if none are found.'''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.1_multi_aX_plus_Y_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    # 1: loop no backwards dependence
    loop3 = schedule.children[2]
    assert not loop3.backward_dependence()
    # 2: loop to loop backward dependence
    # a) many steps
    last_loop_node = schedule.children[6]
    prev_dep_loop_node = schedule.children[3]
    assert last_loop_node.backward_dependence() == prev_dep_loop_node
    # b) previous
    assert prev_dep_loop_node.backward_dependence() == loop3
    # 3: haloexchange dependencies
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4.5_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    loop2 = schedule.children[7]
    halo_exchange = schedule.children[8]
    loop3 = schedule.children[9]
    # a) following loop node depends on halo exchange node
    result = loop3.backward_dependence()
    assert result == halo_exchange
    # b) halo exchange node depends on previous loop node
    result = halo_exchange.backward_dependence()
    assert result == loop2
    # 4: globalsum dependencies
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.3_sum_setval_field_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    loop1 = schedule.children[0]
    loop2 = schedule.children[1]
    global_sum = schedule.children[2]
    loop3 = schedule.children[3]
    # a) loop3 depends on global sum
    assert loop3.backward_dependence() == global_sum
    # b) global sum depends on loop2
    assert global_sum.backward_dependence() == loop2
    # c) loop2 (sum) depends on loop1
    assert loop2.backward_dependence() == loop1


def test_node_is_valid_location():
    ''' Test that the Node class is_valid_location method returns True if
    the new location does not break any data dependencies, otherwise it
    returns False.

    '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    # 1: new node argument is invalid
    anode = schedule.children[0]
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location("invalid_node_argument")
    assert "argument is not a Node, it is a 'str'." in str(excinfo.value)
    # 2: optional position argument is invalid
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(anode, position="invalid_node_argument")
    assert "The position argument in the psyGen" in str(excinfo.value)
    assert "method must be one of" in str(excinfo.value)
    # 3: parents of node and new_node are not the same
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(schedule.children[4].children[0])
    assert ("the node and the location do not have the same "
            "parent") in str(excinfo.value)
    # 4: positions are the same
    prev_node = schedule.children[0]
    anode = schedule.children[1]
    next_node = schedule.children[2]
    # a) before this node
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(anode, position="before")
    assert "the node and the location are the same" in str(excinfo.value)
    # b) after this node
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(anode, position="after")
    assert "the node and the location are the same" in str(excinfo.value)
    # c) after previous node
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(prev_node, position="after")
    assert "the node and the location are the same" in str(excinfo.value)
    # d) before next node
    with pytest.raises(GenerationError) as excinfo:
        anode.is_valid_location(next_node, position="before")
    assert "the node and the location are the same" in str(excinfo.value)
    # 5: valid no previous dependency
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.1_multi_aX_plus_Y_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    # 6: valid no prev dep
    anode = schedule.children[2]
    assert anode.is_valid_location(schedule.children[0])
    # 7: valid prev dep (after)
    anode = schedule.children[6]
    assert anode.is_valid_location(schedule.children[3], position="after")
    # 8: invalid prev dep (before)
    assert not anode.is_valid_location(schedule.children[3], position="before")
    # 9: valid no following dep
    anode = schedule.children[4]
    assert anode.is_valid_location(schedule.children[6], position="after")
    # 10: valid following dep (before)
    anode = schedule.children[0]
    assert anode.is_valid_location(schedule.children[3], position="before")
    # 11: invalid following dep (after)
    anode = schedule.children[0]
    assert not anode.is_valid_location(schedule.children[3], position="after")


def test_node_ancestor():
    ''' Test the Node.ancestor() method. '''
    _, invoke = get_invoke("single_invoke.f90", "gocean1.0", idx=0,
                           dist_mem=False)
    sched = invoke.schedule
    kern = sched[0].loop_body[0].loop_body[0]
    anode = kern.ancestor(Node)
    assert isinstance(anode, Schedule)
    # If 'excluding' is supplied then it can only be a single type or a
    # tuple of types
    anode = kern.ancestor(Node, excluding=Schedule)
    assert anode is sched[0].loop_body[0]
    anode = kern.ancestor(Node, excluding=(Schedule,))
    assert anode is sched[0].loop_body[0]
    with pytest.raises(TypeError) as err:
        kern.ancestor(Node, excluding=[Schedule])
    assert ("argument to ancestor() must be a type or a tuple of types but "
            "got: 'list'" in str(err.value))
    # Check that the include_self argument behaves as expected
    anode = kern.ancestor(Kern, excluding=(Schedule,), include_self=True)
    assert anode is kern


def test_dag_names():
    ''' Test that the dag_name method returns the correct value for the
    node class and its specialisations. '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    assert super(Schedule, schedule).dag_name == "node_0"
    assert schedule.dag_name == "routine_invoke_0_testkern_type_0"
    assert schedule.children[0].dag_name == "checkHaloExchange(f1)_0"
    assert schedule.children[4].dag_name == "loop_5"
    schedule.children[4].loop_type = "colour"
    assert schedule.children[4].dag_name == "loop_[colour]_5"
    schedule.children[4].loop_type = ""
    assert (schedule.children[4].loop_body[0].dag_name ==
            "kernel_testkern_code_10")
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "15.14.3_sum_setval_field_builtin.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3", distributed_memory=True).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    global_sum = schedule.children[2]
    assert global_sum.dag_name == "globalsum(asum)_2"
    builtin = schedule.children[1].loop_body[0]
    assert builtin.dag_name == "builtin_sum_x_12"


def test_node_digraph_no_graphviz(monkeypatch):
    ''' Test that the function to get the graphviz Digraph class type returns
    None if graphviz is not installed. We monkeypatch sys.modules to ensure
    that it always appears that graphviz is not installed on this system. '''
    monkeypatch.setitem(sys.modules, 'graphviz', None)
    dag_class = _graphviz_digraph_class()
    assert dag_class is None


def test_node_dag_no_graphviz(tmpdir, monkeypatch):
    ''' Test that the dag generation returns None (and that no file is created)
    when graphviz is not installed. We make this test independent of whether or
    not graphviz is installed by monkeypatching sys.modules. '''
    monkeypatch.setitem(sys.modules, 'graphviz', None)
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3",
                     distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    my_file = tmpdir.join('test')
    dag = invoke.schedule.dag(file_name=my_file.strpath)
    assert dag is None
    assert not os.path.exists(my_file.strpath)


def test_node_dag_returns_digraph(monkeypatch):
    ''' Test that the dag generation returns the expected Digraph object. We
    make this test independent of whether or not graphviz is installed by
    monkeypatching the psyir.nodes.node._graphviz_digraph_class function to
    return a fake digraph class type. '''
    class FakeDigraph(object):
        ''' Fake version of graphviz.Digraph class with key methods
        implemented as noops. '''
        # pylint: disable=redefined-builtin
        def __init__(self, format=None):
            ''' Fake constructor. '''

        def node(self, _name):
            ''' Fake node method. '''

        def edge(self, _name1, _name2, color="red"):
            ''' Fake edge method. '''

        def render(self, filename):
            ''' Fake render method. '''

    monkeypatch.setattr(node, "_graphviz_digraph_class", lambda: FakeDigraph)
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3",
                     distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    dag = schedule.dag()
    assert isinstance(dag, FakeDigraph)


def test_node_dag_wrong_file_format(monkeypatch):
    ''' Test the handling of the error raised by graphviz when it is passed
    an invalid file format. We make this test independent of whether or not
    graphviz is actually available by monkeypatching the
    psyir.nodes.node._graphviz_digraph_class function to return a fake digraph
    class type that mimics the error. '''
    class FakeDigraph(object):
        ''' Fake version of graphviz.Digraph class that raises a ValueError
        when instantiated. '''
        # pylint: disable=redefined-builtin
        def __init__(self, format=None):
            raise ValueError(format)

    monkeypatch.setattr(node, "_graphviz_digraph_class", lambda: FakeDigraph)
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "1_single_invoke.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3",
                     distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    with pytest.raises(GenerationError) as err:
        invoke.schedule.dag()
    assert "unsupported graphviz file format 'svg' provided" in str(err.value)


# Use a regex to allow for whitespace differences between graphviz
# versions. Need a raw-string (r"") to get new-lines handled nicely.
EXPECTED2 = re.compile(
    r"digraph {\n"
    r"\s*routine_invoke_0_0_start\n"
    r"\s*routine_invoke_0_0_end\n"
    r"\s*loop_1_start\n"
    r"\s*loop_1_end\n"
    r"\s*loop_1_end -> loop_7_start \[color=green\]\n"
    r"\s*routine_invoke_0_0_start -> loop_1_start \[color=blue\]\n"
    r"\s*schedule_5_start\n"
    r"\s*schedule_5_end\n"
    r"\s*schedule_5_end -> loop_1_end \[color=blue\]\n"
    r"\s*loop_1_start -> schedule_5_start \[color=blue\]\n"
    r"\s*kernel_testkern_qr_code_6\n"
    r"\s*kernel_testkern_qr_code_6 -> schedule_5_end \[color=blue\]\n"
    r"\s*schedule_5_start -> kernel_testkern_qr_code_6 \[color=blue\]\n"
    r"\s*loop_7_start\n"
    r"\s*loop_7_end\n"
    r"\s*loop_7_end -> routine_invoke_0_0_end \[color=blue\]\n"
    r"\s*loop_1_end -> loop_7_start \[color=red\]\n"
    r"\s*schedule_11_start\n"
    r"\s*schedule_11_end\n"
    r"\s*schedule_11_end -> loop_7_end \[color=blue\]\n"
    r"\s*loop_7_start -> schedule_11_start \[color=blue\]\n"
    r"\s*kernel_testkern_qr_code_12\n"
    r"\s*kernel_testkern_qr_code_12 -> schedule_11_end \[color=blue\]\n"
    r"\s*schedule_11_start -> kernel_testkern_qr_code_12 \[color=blue\]\n"
    r"}")
# pylint: enable=anomalous-backslash-in-string


def test_node_dag(tmpdir, have_graphviz):
    ''' Test that dag generation works correctly. Skip the test if
    graphviz is not installed. '''
    if not have_graphviz:
        return
    # We may not have graphviz installed so disable pylint error
    # pylint: disable=import-error
    # pylint: disable=import-outside-toplevel
    import graphviz
    _, invoke_info = parse(
        os.path.join(BASE_PATH, "4.1_multikernel_invokes.f90"),
        api="dynamo0.3")
    psy = PSyFactory("dynamo0.3",
                     distributed_memory=False).create(invoke_info)
    invoke = psy.invokes.invoke_list[0]
    schedule = invoke.schedule
    my_file = tmpdir.join('test')
    dag = schedule.dag(file_name=my_file.strpath)
    assert isinstance(dag, graphviz.Digraph)

    result = my_file.read()
    assert EXPECTED2.match(result)
    my_file = tmpdir.join('test.svg')
    result = my_file.read()
    for name in ["<title>routine_invoke_0_0_start</title>",
                 "<title>routine_invoke_0_0_end</title>",
                 "<title>loop_1_start</title>",
                 "<title>loop_1_end</title>",
                 "<title>kernel_testkern_qr_code_6</title>",
                 "<title>kernel_testkern_qr_code_12</title>",
                 "<svg", "</svg>", ]:
        assert name in result
    for colour_name, colour_code in [("blue", "#0000ff"),
                                     ("green", "#00ff00"),
                                     ("red", "#ff0000")]:
        assert colour_name in result or colour_code in result

    with pytest.raises(GenerationError) as excinfo:
        schedule.dag(file_name=my_file.strpath, file_format="rubbish")
    assert "unsupported graphviz file format" in str(excinfo.value)


def test_scope():
    '''Test that the scope method in a Node instance returns the closest
    ancestor Schedule or Container Node (including itself) or raises
    an exception if one does not exist.

    '''
    kernel_symbol_table = SymbolTable()
    symbol = DataSymbol("tmp", REAL_TYPE)
    kernel_symbol_table.add(symbol)
    ref = Reference(symbol)
    assign = Assignment.create(ref, Literal("0.0", REAL_TYPE))
    kernel_schedule = KernelSchedule.create("my_kernel", kernel_symbol_table,
                                            [assign])
    container = Container.create("my_container", SymbolTable(),
                                 [kernel_schedule])
    assert ref.scope is kernel_schedule
    assert assign.scope is kernel_schedule
    assert kernel_schedule.scope is kernel_schedule
    assert container.scope is container

    anode = Literal("x", INTEGER_TYPE)
    with pytest.raises(SymbolError) as excinfo:
        _ = anode.scope
    assert ("Unable to find the scope of node "
            "'Literal[value:'x', Scalar<INTEGER, UNDEFINED>]' as "
            "none of its ancestors are Container or Schedule nodes."
            in str(excinfo.value))


def test_children_validation():
    ''' Test that nodes are validated when inserted as children of other
    nodes. For simplicity we use Node subclasses to test this functionality
    across a range of possible operations.

    The specific logic of each validate method will be tested individually
    inside each Node test file.
    '''
    assignment = Assignment()
    return_stmt = Return()
    reference = Reference(DataSymbol("a", INTEGER_TYPE))

    assert isinstance(assignment.children, (ChildrenList, list))

    # Try adding a invalid child (e.g. a return_stmt into an assingment)
    with pytest.raises(GenerationError) as error:
        assignment.addchild(return_stmt)
    assert "Item 'Return' can't be child 0 of 'Assignment'. The valid format" \
        " is: 'DataNode, DataNode'." in str(error.value)

    # The same behaviour occurs when list insertion operations are used.
    with pytest.raises(GenerationError):
        assignment.children.append(return_stmt)

    with pytest.raises(GenerationError):
        assignment.children[0] = return_stmt

    with pytest.raises(GenerationError):
        assignment.children.insert(0, return_stmt)

    with pytest.raises(GenerationError):
        assignment.children.extend([return_stmt])

    with pytest.raises(GenerationError):
        assignment.children = assignment.children + [return_stmt]

    # Valid nodes are accepted
    assignment.addchild(reference)

    # Check displaced items are also be checked when needed
    start = Literal("0", INTEGER_TYPE)
    stop = Literal("1", INTEGER_TYPE)
    step = Literal("2", INTEGER_TYPE)
    child_node = Assignment.create(Reference(DataSymbol("tmp", REAL_TYPE)),
                                   Reference(DataSymbol("i", REAL_TYPE)))
    loop_variable = DataSymbol("idx", INTEGER_TYPE)
    loop = Loop.create(loop_variable, start, stop, step, [child_node])
    with pytest.raises(GenerationError):
        loop.children.insert(1, Literal("0", INTEGER_TYPE))

    with pytest.raises(GenerationError):
        loop.children.remove(stop)

    with pytest.raises(GenerationError):
        del loop.children[2]

    with pytest.raises(GenerationError):
        loop.children.pop(2)

    with pytest.raises(GenerationError):
        loop.children.reverse()

    # But the in the right circumstances they work fine
    assert isinstance(loop.children.pop(), Schedule)
    loop.children.reverse()
    assert loop.children[0].value == "2"


def test_children_setter():
    ''' Test that the children setter sets-up accepts lists or None or raises
    the appropriate issue. '''
    testnode = Schedule()

    # children is initialised as a ChildrenList
    assert isinstance(testnode.children, ChildrenList)

    # When is set up with a list, this becomes a ChildrenList
    testnode.children = [Statement(), Statement()]
    assert isinstance(testnode.children, ChildrenList)

    # It also accepts None
    testnode.children = None
    assert testnode.children is None

    # Other types are not accepted
    with pytest.raises(TypeError) as error:
        testnode.children = Node()
    assert "The 'my_children' parameter of the node.children setter must be" \
           " a list or None." in str(error.value)


def test_lower_to_language_level(monkeypatch):
    ''' Test that Node has a lower_to_language_level() method that \
    recurses to the same method of its children. '''

    # Monkeypatch the lower_to_language_level to just mark a flag
    def visited(self):
        self._visited_flag = True
    monkeypatch.setattr(Statement, "lower_to_language_level", visited)

    testnode = Schedule()
    node1 = Statement()
    node2 = Statement()
    testnode.children = [node1, node2]

    # Execute method
    testnode.lower_to_language_level()

    # Check all children have been visited
    for child in testnode.children:
        # This member only exists in the monkeypatched version
        # pylint:disable=no-member
        assert child._visited_flag
