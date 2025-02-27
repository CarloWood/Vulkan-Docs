#!/usr/bin/python3 -i
#
# Copyright 2013-2021 The Khronos Group Inc.
#
# SPDX-License-Identifier: Apache-2.0

from generator import OutputGenerator, write
from spec_tools.attributes import ExternSyncEntry
from spec_tools.util import getElemName

import pdb

def makeLink(link, altlink = None):
    """Create an asciidoctor link, optionally with altlink text
       if provided"""

    if altlink is not None:
        return '<<{},{}>>'.format(link, altlink)
    else:
        return '<<{}>>'.format(link)

class SpirvCapabilityOutputGenerator(OutputGenerator):
    """SpirvCapabilityOutputGenerator - subclass of OutputGenerator.
    Generates AsciiDoc includes of the SPIR-V capabilities table for the
    features chapter of the API specification.

    ---- methods ----
    SpirvCapabilityOutputGenerator(errFile, warnFile, diagFile) - args as for
      OutputGenerator. Defines additional internal state.
    ---- methods overriding base class ----
    genCmd(cmdinfo)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def beginFile(self, genOpts):
        OutputGenerator.beginFile(self, genOpts)

        # Accumulate SPIR-V capability and feature information
        self.spirv = []

    def getCondition(self, enable, parent):
        """Return a strings which is the condition under which an
           enable is supported.

         - enable - ElementTree corresponding to an <enable> XML tag for a
           SPIR-V capability or extension
         - parent - Parent <spirvcapability> or <spirvenable> ElementTree,
           used for error reporting"""

        if enable.get('version'):
            return enable.get('version')
        elif enable.get('extension'):
            return enable.get('extension')
        elif enable.get('struct') or enable.get('property'):
            return enable.get('requires')
        else:
            self.logMsg('error', f"<{parent.tag} name=\"{parent.get('name')}\"> is missing a required attribute for an <enable>")
            return ''

    def getConditions(self, enables):
        """Return a sorted list of strings which are conditions under which
           one or more of the enables is supported.

         - enables - ElementTree corresponding to a <spirvcapability> or
           <spirvextension> XML tag"""

        conditions = set()
        for enable in enables.findall('enable'):
            condition = self.getCondition(enable, parent=enables)
            if condition != None:
                conditions.add(condition)
        return sorted(conditions)

    def endFile(self):
        captable = []
        exttable = []

        # How to "indent" a pseudo-column for better use of space.
        # {captableindent} is defined in appendices/spirvenv.txt
        indent = '{captableindent}'

        for elem in self.spirv:
            conditions = self.getConditions(elem)

            # Combine all conditions for enables and surround the row with
            # them
            if len(conditions) > 0:
                condition_string = ','.join(conditions)
                prefix = [ 'ifdef::{}[]'.format(condition_string) ]
                suffix = [ 'endif::{}[]'.format(condition_string) ]
            else:
                prefix = []
                suffix = []

            body = []

            # Generate an anchor for each capability
            if elem.tag == 'spirvcapability':
                anchor = '[[spirvenv-capabilities-table-{}]]'.format(
                    elem.get('name'))
            else:
                # <spirvextension> entries don't get anchors
                anchor = ''

            # First "cell" in a table row, and a break for the other "cells"
            body.append('| {}code:{} +'.format(anchor, elem.get('name')))

            # Iterate over each enable emitting a formatting tag for it
            # Protect the term if there is a version or extension
            # requirement, and if there are multiple enables (otherwise,
            # the ifdef protecting the entire row will suffice).

            enables = [e for e in elem.findall('enable')]

            remaining = len(enables)
            for subelem in enables:
                remaining -= 1

                # Sentinel value
                linktext = None
                if subelem.get('version'):
                    version = subelem.get('version')

                    # Convert API enum to anchor for version appendices (versions-m.n)
                    # version must be the spec conditional macro VK_VERSION_m_n, not
                    # the API version macro VK_API_VERSION_m_n.
                    enable = version
                    link = 'versions-' + version[-3:].replace('_', '.')
                    altlink = version

                    linktext = makeLink(link, altlink)
                elif subelem.get('extension'):
                    extension = subelem.get('extension')

                    enable = extension
                    link = extension
                    altlink = None

                    # This uses the extension name macro, rather than
                    # asciidoc markup
                    linktext = '`apiext:{}`'.format(extension)
                elif subelem.get('struct'):
                    struct = subelem.get('struct')
                    feature = subelem.get('feature')
                    requires = subelem.get('requires')
                    alias = subelem.get('alias')

                    link_name = feature
                    # For cases, like bufferDeviceAddressEXT where need manual help
                    if alias:
                        link_name = alias

                    enable = requires
                    link = 'features-' + link_name
                    altlink = 'sname:{}::pname:{}'.format(struct, feature)

                    linktext = makeLink(link, altlink)
                else:
                    property = subelem.get('property')
                    member = subelem.get('member')
                    requires = subelem.get('requires')
                    value = subelem.get('value')

                    enable = requires
                    # Properties should have a "feature" prefix
                    link = 'limits-' + member
                    # Display the property value by itself if it is not a boolean (matches original table)
                    # DenormPreserve is an example where it makes sense to just show the
                    #   member value as it is just a boolean and the name implies "true"
                    # GroupNonUniformVote is an example where the whole name is too long
                    #   better to just display the value
                    if value == "VK_TRUE":
                        altlink = 'sname:{}::pname:{}'.format(property, member)
                    else:
                        altlink = '{}'.format(value)

                    linktext = makeLink(link, altlink)

                # If there are no more enables, don't continue the last line
                if remaining > 0:
                    continuation = ' +'
                else:
                    continuation = ''

                # condition_string != enable is a small optimization
                if enable is not None and condition_string != enable:
                    body.append('ifdef::{}[]'.format(enable))
                body.append('{} {}{}'.format(indent, linktext, continuation))
                if enable is not None and condition_string != enable:
                    body.append('endif::{}[]'.format(enable))

            if elem.tag == 'spirvcapability':
                captable += prefix + body + suffix
            else:
                exttable += prefix + body + suffix

        # Generate the asciidoc include files
        self.writeBlock('captable.txt', captable)
        self.writeBlock('exttable.txt', exttable)

        # Finish processing in superclass
        OutputGenerator.endFile(self)

    def writeBlock(self, basename, contents):
        """Generate an include file.

        - directory - subdirectory to put file in
        - basename - base name of the file
        - contents - contents of the file (Asciidoc boilerplate aside)"""

        filename = self.genOpts.directory + '/' + basename
        self.logMsg('diag', '# Generating include file:', filename)
        with open(filename, 'w', encoding='utf-8') as fp:
            write(self.genOpts.conventions.warning_comment, file=fp)

            if len(contents) > 0:
                for str in contents:
                    write(str, file=fp)
            else:
                self.logMsg('diag', '# No contents for:', filename)

    def paramIsArray(self, param):
        """Check if the parameter passed in is a pointer to an array."""
        return param.get('len') is not None

    def paramIsPointer(self, param):
        """Check if the parameter passed in is a pointer."""
        tail = param.find('type').tail
        return tail is not None and '*' in tail

    def makeThreadSafetyBlocks(self, cmd, paramtext):
        # See also makeThreadSafetyBlock in validitygenerator.py - similar but not entirely identical
        protoname = cmd.find('proto/name').text

        # Find and add any parameters that are thread unsafe
        explicitexternsyncparams = cmd.findall(paramtext + "[@externsync]")
        if explicitexternsyncparams is not None:
            for param in explicitexternsyncparams:
                self.makeThreadSafetyForParam(protoname, param)

        # Find and add any "implicit" parameters that are thread unsafe
        implicitexternsyncparams = cmd.find('implicitexternsyncparams')
        if implicitexternsyncparams is not None:
            for elem in implicitexternsyncparams:
                entry = ValidityEntry()
                entry += elem.text
                entry += ' in '
                entry += self.makeFLink(protoname)
                self.threadsafety['implicit'] += entry

        # Add a VU for any command requiring host synchronization.
        # This could be further parameterized, if a future non-Vulkan API
        # requires it.
        if self.genOpts.conventions.is_externsync_command(protoname):
            entry = ValidityEntry()
            entry += 'The sname:VkCommandPool that pname:commandBuffer was allocated from, in '
            entry += self.makeFLink(protoname)
            self.threadsafety['implicit'] += entry

    def makeThreadSafetyForParam(self, protoname, param):
        """Create thread safety validity for a single param of a command."""
        externsyncattribs = ExternSyncEntry.parse_externsync_from_param(param)
        param_name = getElemName(param)

        for attrib in externsyncattribs:
            entry = ValidityEntry()
            is_array = False
            if attrib.entirely_extern_sync:
                # "true" or "true_with_children"
                if self.paramIsArray(param):
                    entry += 'Each element of the '
                    is_array = True
                elif self.paramIsPointer(param):
                    entry += 'The object referenced by the '
                else:
                    entry += 'The '

                entry += self.makeParameterName(param_name)
                entry += ' parameter'

                if attrib.children_extern_sync:
                    entry += ', and any child handles,'

            else:
                # parameter/member reference
                readable = attrib.get_human_readable(make_param_name=self.makeParameterName)
                is_array = (' element of ' in readable)
                entry += readable

            entry += ' in '
            entry += self.makeFLink(protoname)

            if is_array:
                self.threadsafety['parameterlists'] += entry
            else:
                self.threadsafety['parameters'] += entry

    def genSpirv(self, capinfo, name, alias):
        """Generate SPIR-V capabilities

        capinfo - dictionary entry for an XML <spirvcapability> or
            <spirvextension> element
        name - name attribute of capinfo.elem"""

        OutputGenerator.genSpirv(self, capinfo, name, alias)

        # Just accumulate each element, process in endFile
        self.spirv.append(capinfo.elem)
