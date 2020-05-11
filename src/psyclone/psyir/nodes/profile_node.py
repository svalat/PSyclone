# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2018-2020, Science and Technology Facilities Council.
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
# Author J. Henrichs, Bureau of Meteorology
# Modified by A. R. Porter and S. Siso, STFC Daresbury Lab
# -----------------------------------------------------------------------------

''' This module provides support for adding profiling to code
    generated by PSyclone. '''

from __future__ import absolute_import, print_function

from psyclone.psyir.nodes.psy_data_node import PSyDataNode


class ProfileNode(PSyDataNode):
    '''This class can be inserted into a schedule to create profiling code.

    :param ast: reference into the fparser2 parse tree corresponding to \
        this node.
    :type ast: sub-class of :py:class:`fparser.two.Fortran2003.Base`
    :param children: a list of child nodes for this node. These will be made \
        children of the child Schedule of this Profile Node.
    :type children: list of :py::class::`psyclone.psyir.nodes.Node` \
        or derived classes
    :param parent: the parent of this node in the PSyIR.
    :type parent: :py:class:`psyclone.psyir.nodes.Node`
    :param options: a dictionary with options for transformations.
    :type options: dictionary of string:values or None
    :param str options["prefix"]: The PSyData prefix to use. This string \
        is a prefix attached to all PSyData-related symbols. Defaults \
        to "profile".
    :param (str,str) options["region_name"]: an optional name for this \
        profile region provided as a 2-tuple containing a module name \
        followed by a local name. The pair of strings should uniquely \
        identify a region unless aggregate information is required.

    '''
    _text_name = "Profile"
    _colour_key = "Profile"

    def __init__(self, ast=None, children=None, parent=None, options=None):
        if options:
            my_options = options.copy()
        else:
            my_options = {}
        # If there is no value specified in the constructor, default
        # to the "profile" prefix.
        my_options["prefix"] = my_options.get("prefix", "profile")

        super(ProfileNode, self).__init__(ast=ast, children=children,
                                          parent=parent, options=my_options)

    # -------------------------------------------------------------------------
    def __str__(self):
        ''' Returns a string representation of the subtree starting at
        this node. '''
        result = "ProfileStart[var={0}]\n".format(self._var_name)
        for child in self.profile_body.children:
            result += str(child)+"\n"
        return result+"ProfileEnd"

    # -------------------------------------------------------------------------
    @property
    def profile_body(self):
        '''
        :returns: the Schedule associated with this Profiling region.
        :rtype: :py:class:`psyclone.psyir.nodes.Schedule`

        :raises InternalError: if this Profile node does not have a Schedule \
                               as its one and only child.
        '''
        from psyclone.psyir.nodes import Schedule
        from psyclone.errors import InternalError
        if len(self.children) != 1 or not \
           isinstance(self.children[0], Schedule):
            raise InternalError(
                "ProfileNode malformed or incomplete. It should have a single "
                "Schedule as a child but found: {0}".format(
                    [type(child).__name__ for child in self.children]))
        return super(ProfileNode, self).psy_data_body

    # -------------------------------------------------------------------------
    def gen_code(self, parent):
        # pylint: disable=arguments-differ
        '''Creates the profile start and end calls, surrounding the children
        of this node.

        :param parent: the parent of this node.
        :type parent: :py:class:`psyclone.psyir.nodes.Node`

        '''
        options = {'pre_var_list': [],
                   'post_var_list': []}

        super(ProfileNode, self).gen_code(parent, options)

    # -------------------------------------------------------------------------
    def gen_c_code(self, indent=0):
        '''
        Generates a string representation of this Node using C language
        (currently not supported).

        :param int indent: Depth of indent for the output string.
        :raises NotImplementedError: Not yet supported for profiling.
        '''
        raise NotImplementedError("Generation of C code is not supported "
                                  "for profiling")
