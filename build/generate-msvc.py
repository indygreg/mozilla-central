# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla build system.
#
# The Initial Developer of the Original Code is Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#  Gregory Szorc <gps@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisiwons above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

# This script generates Visual Studio files from a configured object directory.
# To run, point it at an object directory, specifying the full path. Relative
# paths will not work at this time.

import sys

# TODO these should magically come from the environment
sys.path.append('build/pymake')
sys.path.append('other-licenses/ply')
sys.path.append('xpcom/idl-parser')

import buildparser.extractor
import buildparser.makefile_generator

from optparse import OptionParser
from sys import argv, exit

op = OptionParser(usage='usage: %prog [options] /path/to/objdir/')
op.add_option('-v', '--version', dest='version', default='2008',
              help='Visual Studio version. One of 2005, 2008, 2010, or 2011')
op.add_option('-p', '--python', dest='python', default=None,
              help='Python executable runnable from Windows shell')
op.add_option('-m', '--makefile', dest='makefile', default=None,
              help='Makefile to output to')

(options, args) = op.parse_args()

if len(args) != 1:
    print 'Path not specified'
    exit(1)

path = args[0]

parser = buildparser.extractor.ObjectDirectoryParser(path)
print 'Parsing build tree...'
parser.load_tree()

if options.makefile:
    print 'Generating Makefile...'
    generator = buildparser.makefile_generator.MakefileGenerator(parser.tree)
    with open(options.makefile, 'w') as fh:
        generator.generate_makefile(fh)

#parser = BuildParser(path)
#parser.build_visual_studio_files(version=options.version, python=options.python)