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

# This file contains classes used to extract metadata from the Mozilla build
# system.

from . import config
from . import data
from . import makefile

import os
import os.path
import sys
import traceback
import xpidl

class MozillaMakefile(makefile.Makefile):
    """A Makefile with knowledge of Mozilla's build system.

    This is the class used to extract metadata from the Makefiles.
    """

    """Traits that can identify a Makefile"""
    MODULE       = 1
    LIBRARY      = 2
    DIRS         = 3
    XPIDL        = 4
    EXPORTS      = 5
    TEST         = 6
    PROGRAM      = 7

    """Variables common in most Makefiles that aren't really that special.

    This list is used to help identify variables we don't do anything with."""
    COMMON_VARIABLES = [
        'DEPTH',            # Defined at top of file
        'topsrcdir',        # Defined at top of file
        'srcdir',           # Defined at top of file
        'VPATH',            # Defined at top of file
        'relativesrcdir',   # Defined at top of file. # TODO is this used by anything?
        'DIRS',             # Path traversal
        'PARALLEL_DIRS',    # Path traversal
        'TOOL_DIRS',        # Path traversal
    ]

    """This list tracks all variables that are still in the wild but aren't used"""
    UNUSED_VARIABLES = []

    def __init__(self, filename):
        makefile.Makefile.__init__(self, filename)

        self.traits = None

    def get_traits(self):
        """Obtain traits of the Makefile.

        Traits are recognized patterns that invoke special functionality in
        Mozilla's Makefiles. Traits are identified by the presence of specific
        named variables."""
        if self.traits is not None:
            return self.traits

        self.traits = set()
        variable_names = self.get_own_variable_names(include_conditionals=True)
        for name in variable_names:
            if name == 'MODULE':
                self.traits.add(self.MODULE)
            elif name == 'LIBRARY_NAME':
                self.traits.add(self.LIBRARY)
            elif name == 'DIRS' or name == 'PARALLEL_DIRS':
                self.traits.add(self.DIRS)
            elif name in ('XPIDL_MODULE', 'XPIDLSRCS', 'SDK_XPIDLSRCS'):
                self.traits.add(self.XPIDL)
            elif name in ('EXPORTS', 'EXPORTS_NAMESPACES'):
                self.traits.add(self.EXPORTS)
            elif name in ('_TEST_FILES', 'XPCSHELL_TESTS', '_BROWSER_TEST_FILES', '_CHROME_TEST_FILES'):
                self.traits.add(self.TEST)
            elif name in ('PROGRAM'):
                self.traits.add(self.PROGRAM)

        return self.traits

    def get_dirs(self):
        dirs = self.get_variable_split('DIRS')
        dirs.extend(self.get_variable_split('PARALLEL_DIRS'))

        return dirs

    def is_module(self):
        return self.MODULE in self.get_traits()

    def is_xpidl_module(self):
        return self.XPIDL_MODULE in self.get_traits()

    def get_module(self):
        return self.get_variable_string('MODULE')

    def get_reldir(self):
        absdir = os.path.abspath(self.dir)

        return absdir[len(self.get_objtop())+1:]

    def get_objtop(self):
        depth = self.get_variable_string('DEPTH')
        if not depth:
            depth = self.get_variable_string('MOD_DEPTH')

        return os.path.abspath(os.path.join(self.dir, depth))

    def get_top_source_dir(self):
        return self.get_variable_string('topsrcdir')

    def get_source_dir(self):
        return self.get_variable_string('srcdir')

    def get_transformed_reldir(self):
        return self.get_reldir().replace('\\', '_').replace('/', '_')

    def get_library_info(self):
        """Obtain information for the library defined by this Makefile.

        Returns a data.LibraryInfo instance"""
        l = data.LibraryInfo(self)

        # It is possible for the name to be not defined if the trait was
        # in a conditional that wasn't true.
        l.add_used_variable('LIBRARY_NAME')
        name = self.get_variable_string('LIBRARY_NAME')
        l.name = name

        l.add_used_variable('DEFINES')
        for define in self.get_variable_split('DEFINES'):
            if define[0:2] == '-D':
                l.defines.add(define[2:])
            else:
                l.defines.add(define)

        l.add_used_variable('CFLAGS')
        for f in self.get_variable_split('CFLAGS'):
            l.c_flags.add(f)

        l.add_used_variable('CXXFLAGS')
        for f in self.get_variable_split('CXXFLAGS'):
            l.cxx_flags.add(f)

        l.add_used_variable('CPPSRCS')
        for f in self.get_variable_split('CPPSRCS'):
            l.cpp_sources.add(f)

        # LIBXUL_LIBRARY implies static library generation and presence in
        # libxul.
        l.add_used_variable('LIBXUL_LIBRARY')
        if self.has_own_variable('LIBXUL_LIBRARY'):
            l.is_static = True

        # FORCE_STATIC_LIB forces generation of a static library
        l.add_used_variable('FORCE_STATIC_LIB')
        if self.has_own_variable('FORCE_STATIC_LIB'):
            l.is_static = True

        l.add_used_variable('FORCE_SHARED_LIB')
        if self.has_own_variable('FORCE_SHARED_LIB'):
            l.is_shared = True

        l.add_used_variable('USE_STATIC_LIBS')
        if self.has_own_variable('USE_STATIC_LIBS'):
            l.use_static_libs = True

        # IS_COMPONENT is used for verification. It also has side effects for
        # linking flags.
        l.add_used_variable('IS_COMPONENT')
        if self.has_own_variable('IS_COMPONENT'):
            l.is_component = self.get_variable_string('IS_COMPONENT') == '1'

        l.add_used_variable('EXPORT_LIBRARY')
        if self.has_own_variable('EXPORT_LIBRARY'):
            l.export_library = self.get_variable_string('EXPORT_LIBRARY') == '1'

        l.add_used_variable('INCLUDES')
        for s in self.get_variable_split('INCLUDES'):
            if s[0:2] == '-I':
                l.includes.add(s[2:])
            else:
                l.includes.add(s)

        l.add_used_variable('LOCAL_INCLUDES')
        for s in self.get_variable_split('LOCAL_INCLUDES'):
            if s[0:2] == '-I':
                l.local_includes.add(s[2:])
            else:
                l.local_includes.add(s)

        # SHORT_LIBNAME doesn't appears to be used, but we preserve it anyway.
        l.add_used_variable('SHORT_LIBNAME')
        if self.has_own_variable('SHORT_LIBNAME'):
            l.short_libname = self.get_variable_string('SHORT_LIBNAME')

        l.add_used_variable('SHARED_LIBRARY_LIBS')
        for lib in self.get_variable_split('SHARED_LIBRARY_LIBS'):
            l.shared_library_libs.add(lib)

        return l

    def get_data_objects(self):
        """Retrieve data objects derived from the Makefile.

        This is the main function that extracts metadata from individual
        Makefiles and turns them into Python data structures.

        This method emits a set of MakefileDerivedObjects which describe the
        Makefile. These objects each describe an individual part of the
        build system, e.g. libraries, IDL files, tests, etc. These emitted
        objects can be fed into another system for conversion to another
        build system, fed into a monolithic data structure, etc.
        """
        misc = data.MiscInfo(self)
        tracker = data.UsedVariableInfo(self)
        for v in self.COMMON_VARIABLES:
            tracker.add_used_variable(v)

        for v in self.UNUSED_VARIABLES:
            tracker.add_used_variable(v)

        traits = self.get_traits()

        if self.MODULE in traits:
            tracker.add_used_variable('MODULE')
            # TODO emit MakefileDerivedObject instance
            #tree.register_module(self.get_module(), self.dir)

        if self.LIBRARY in traits:
            li = self.get_library_info()
            yield li

        if self.PROGRAM in traits:
            # TODO capture programs. Executables and libraries are two sides of
            # the same coin. How should this be captured?
            pass

        # MODULE_NAME is only used for error checking, it appears.
        tracker.add_used_variable('MODULE_NAME')

        # EXPORTS and friends holds information on what files to copy
        # to an output directory.
        if self.EXPORTS in traits:
            exports = data.ExportsInfo(self)
            exports.add_used_variable('EXPORTS')
            for export in self.get_variable_split('EXPORTS'):
                exports.add_export(export, namespace=None)

            exports.add_used_variable('EXPORTS_NAMESPACES')
            for namespace in self.get_variable_split('EXPORTS_NAMESPACES'):
                varname = 'EXPORTS_%s' % namespace
                exports.add_used_variable(varname)
                for s in self.get_variable_split(varname):
                    exports.add_export(s, namespace=namespace)

            yield exports

        # XP IDL file generation
        if self.XPIDL in traits:
            idl = data.XPIDLInfo(self)
            idl.add_used_variable('XPIDL_MODULE')
            idl.add_used_variable('MODULE')
            if self.has_own_variable('XPIDL_MODULE'):
                idl.module = self.get_variable_string('XPIDL_MODULE')
            elif self.has_own_variable('MODULE'):
                idl.module = self.get_variable_string('MODULE')
            else:
                raise Exception('XPIDL trait without XPIDL_MODULE or MODULE defined')

            idl.add_used_variable('XPIDLSRCS')
            if self.has_own_variable('XPIDLSRCS'):
                for f in self.get_variable_split('XPIDLSRCS'):
                    idl.sources.add(f)

            # rules.mk merges SDK_XPIDLSRCS together, so we treat as the same
            if self.has_own_variable('SDK_XPIDLSRCS'):
                for f in self.get_variable_split('SDK_XPIDLSRCS'):
                    idl.sources.add(f)

            yield idl

        # Test definitions
        if self.TEST in traits:
            ti = data.TestInfo(self)

            # Regular test files
            ti.add_used_variable('_TEST_FILES')
            if self.has_own_variable('_TEST_FILES'):
                for f in self.get_variable_split('_TEST_FILES'):
                    ti.test_files.add(f)

            # Identifies directories holding xpcshell test files
            ti.add_used_variable('XPCSHELL_TESTS')
            if self.has_own_variable('XPCSHELL_TESTS'):
                for dir in self.get_variable_split('XPCSHELL_TESTS'):
                    ti.xpcshell_test_dirs.add(dir)

            # Files for browser tests
            ti.add_used_variable('_BROWSER_TEST_FILES')
            if self.has_own_variable('_BROWSER_TEST_FILES'):
                for f in self.get_variable_split('_BROWSER_TEST_FILES'):
                    ti.browser_test_files.add(f)

            # Files for chrome tests
            ti.add_used_variable('_CHROME_TEST_FILES')
            if self.has_own_variable('_CHROME_TEST_FILES'):
                for f in self.get_variable_split('_CHROME_TEST_FILES'):
                    ti.chrome_test_files.add(f)

            yield ti

        misc.add_used_variable('GRE_MODULE')
        if self.has_own_variable('GRE_MODULE'):
            misc.is_gre_module = True

        #misc.add_used_variable('PLATFORM_DIR')
        #for d in self.get_variable_split('PLATFORM_DIR'):
        #    misc.platform_dirs.add(d)

        #misc.add_used_variable('CHROME_DEPS')
        #for d in self.get_variable_split('CHROME_DEPS'):
        #    misc.chrome_dependencies.add(d)

        # DEFINES is used by JarMaker too. Unfortunately, we can't detect
        # when to do JarMaker from Makefiles (bug 487182 might fix it), so
        # we just pass it along.
        misc.add_used_variable('DEFINES')
        if self.has_own_variable('DEFINES'):
            for define in self.get_variable_split('DEFINES'):
                if define[0:2] == '-D':
                    misc.defines.add(define[2:])
                else:
                    misc.defines.add(define)

        # TODO add an info object for JavaScript-related
        misc.add_used_variable('EXTRA_JS_MODULES')
        if self.has_own_variable('EXTRA_JS_MODULES'):
            for js in self.get_variable_split('EXTRA_JS_MODULES'):
                misc.extra_js_module.add(js)

        misc.add_used_variable('EXTRA_COMPONENTS')
        if self.has_own_variable('EXTRA_COMPONENTS'):
            for c in self.get_variable_split('EXTRA_COMPONENTS'):
                misc.extra_components.add(c)

        misc.add_used_variable('GARBAGE')
        if self.has_own_variable('GARBAGE'):
            for g in self.get_variable_split('GARBAGE'):
                misc.garbage.add(g)

        misc.included_files = [t[0] for t in self.statements.includes]

        yield tracker
        yield misc

class MakefileCollection(object):
    """Holds APIs for interacting with multiple Makefiles.

    This is a convenience class so all methods interacting with sets of
    Makefiles reside in one location.
    """
    __slots__ = (
        # Set of paths to all the Makefiles.
        'all_paths',

        'source_directory',
        'object_directory',

        # Dictionary of paths to makefile.Makefile instances (cache)
        '_makefiles',
    )

    def __init__(self, source_directory, object_directory):
        assert(os.path.isabs(source_directory))
        assert(os.path.isabs(object_directory))

        self.source_directory = source_directory
        self.object_directory = object_directory

        self.all_paths = set()
        self._makefiles = {}

    def add(self, path):
        """Adds a Makefile at a path to this collection."""
        self.all_paths.add(path)

    def makefiles(self):
        """A generator for Makefile instances from the configured paths.

        Returns instances of makefile.Makefile.
        """
        for path in sorted(self.all_paths):
            m = self._makefiles.get(path, None)
            if m is None:
                m = makefile.Makefile(path)
                self._makefiles[path] = m

            yield m

    def includes(self):
        """Obtain information about all the includes in the Makefiles.

        This is a generator of tuples. Eah tuple has the items:

          ( makefile, statement, conditions, path )
        """
        for m in self.makefiles():
            for statement, conditions, path in m.statements.includes():
                yield (m, statement, conditions, path)

    def variable_assignments(self):
        """A generator of variable assignments.

        Each returned item is a tuple of:

          ( makefile, statement, conditions, name, value, type )
        """
        for m in self.makefiles():
            for statement, conditions, name, value, type in m.statements.variable_assignments():
                yield (makefile, statement, conditions, name, value, type)

    def rules(self):
        """A generator for rules in all the Makefiles.

        Each returned item is a tuple of:

          ( makefile, statement, conditions, target, prerequisite, commands )
        """
        for m in self.makefiles():
            for statement, conditions, target, prerequisites, commands in m.statements.rules():
                yield (makefile, statement, conditions, target, prerequisites, commands)

    def static_pattern_rules(self):
        """A generator for static pattern rules in all the Makefiles.

        Each returned item is a tuple of:

          ( makefile, statement, conditions, target, pattern, prerequisite, commands )
        """
        for m in self.makefiles():
            for statement, conditions, target, pattern, prerequisites, commands in m.statements.rules():
                yield (makefile, statement, conditions, target, pattern, prerequisites, commands)

class BuildSystemExtractor(object):
    """The entity that extracts information from the build system.

    This is the thing that turns Makefiles and other signals into data
    structures. If you are looking for the core of the build system, you've
    found it!
    """

    BUILD_FILE_INPUT = 1
    BUILD_FILE_MAKEFILE = 2
    BUILD_FILE_MK = 3

    # These relative paths are not managed by us, so we can ignore them
    EXTERNALLY_MANAGED_PATHS = (
        'js/src',
        'nsprpub',
    )

    __slots__ = (
        # BuildConfig instance
        'config',

        # MakefileCollection for the currently loaded Makefiles
        'makefiles',
    )

    def __init__(self, conf):
        assert(isinstance(conf, config.BuildConfig))

        self.config = conf
        self.makefiles = MakefileCollection(conf.source_directory, conf.object_directory)

    def load_all_object_directory_makefiles(self):
        """Convenience method to load all Makefiles in the object directory.

        This pulls in *all* the Makefiles. You probably want to pull in a
        limited set instead.
        """
        for reldir, name, type in self.object_directory_build_files():
            if type != self.BUILD_FILE_MAKEFILE:
                continue

            path = os.path.join(self.config.object_directory, reldir, name)
            self.makefiles.add(path)

    def source_directory_build_files(self):
        """Obtain all build files in the source directory."""
        it = BuildSystemExtractor.get_build_files_in_tree(
            self.config.source_directory,
            ignore_full=[self.config.object_directory]
        )
        for t in it: yield t

    def object_directory_build_files(self):
        """Obtain all build files in the object directory."""
        it = BuildSystemExtractor.get_build_files_in_tree(self.config.object_directory)
        for t in it: yield t

    def relevant_makefiles(self):
        """Obtains the set of relevant Makefiles for the current build
        configuration.

        This looks at the various DIRs variables and assembles the set of
        consulted Makefiles.
        """
        pass

    @staticmethod
    def get_build_files_in_tree(path, ignore_relative=None, ignore_full=None):
        """Find all build files in the directory tree under the given path.

        This is a generator of tuples. Each tuple is of the form:

          ( reldir, filename, type )

        Where reldir is the relative directory from the path argument,
        filename is the str of the build filename, and type is a
        BuildSystemExtractor.BUILD_FILE_* constant.

        Arguments:

          path - Path to directory to recurse.
          ignore_relative - Iterable of relative directory names to ignore.
          ignore_full - Iterable of full paths to ignore.
        """
        assert(os.path.isabs(path))

        if ignore_relative is None:
            ignore_relative = []

        if ignore_full is None:
            ignore_full = []

        for root, dirs, files in os.walk(path):
            relative = root[len(path)+1:]

            # Filter out ignored directories
            ignored = False
            for ignore in ignore_relative:
                if relative.find(ignore) == 0:
                    ignored = True
                    break

            if ignored:
                continue

            for ignore in ignore_full:
                if root.find(ignore) == 0:
                    ignored = True
                    break

            if ignored:
                continue

            for name in files:
                if name[-3:] == '.in':
                    yield (relative, name, BuildSystemExtractor.BUILD_FILE_INPUT)
                elif name == 'Makefile':
                    yield (relative, name, BuildSystemExtractor.BUILD_FILE_MAKEFILE)
                elif name[-3:] == '.mk':
                    yield (relative, name, BuildSystemExtractor.BUILD_FILE_MK)

class ObjectDirectoryParser(object):
    """A parser for an object directory.

    This holds state for a specific build instance. It is constructed from an
    object directory and gathers information from the files it sees.
    """

    __slots__ = (
        'dir',                      # Directory data was extracted from.
        'parsed',
        'top_makefile',
        'top_source_dir',
        'retain_metadata',          # Boolean whether Makefile metadata is being
                                    # retained.
        'all_makefile_paths',       # List of all filesystem paths discovered
        'relevant_makefile_paths',  # List of all Makefiles relevant to our interest
        'ignored_makefile_paths',   # List of Makefile paths ignored
        'handled_makefile_paths',   # Set of Makefile paths which were processed
        'error_makefile_paths',     # Set of Makefile paths experiencing an error
                                    # during processing.
        'included_files',           # Dictionary defining which makefiles were
                                    # included from where. Keys are the included
                                    # filename and values are sets of paths that
                                    # included them.
        'variables',                # Dictionary holding details about variables.
        'ifdef_variables',          # Dictionary holding info on variables used
                                    # in ifdefs.
        'rules',                    # Dictionary of all rules encountered. Keys
                                    # Makefile paths. Values are lists of dicts
                                    # describing each rule.
        'unhandled_variables',

        'tree', # The parsed build tree
    )

    def __init__(self, directory):
        """Construct an instance from a directory.

        The given path must be absolute and must be a directory.
        """
        if not os.path.isabs(directory):
            raise Exception('Path is not absolute: %s' % directory)

        if not os.path.isdir(directory):
            raise Exception('Path is not a directory: %s' % directory)

        self.dir = os.path.normpath(directory)
        self.parsed = False

        top_makefile_path = os.path.join(directory, 'Makefile')

        self.top_makefile = MozillaMakefile(top_makefile_path)
        self.top_source_dir = self.top_makefile.get_top_source_dir()

        # The following hold data once we are parsed.
        self.retain_metadata         = False
        self.all_makefile_paths      = None
        self.relevant_makefile_paths = None
        self.ignored_makefile_paths  = None
        self.handled_makefile_paths  = None
        self.error_makefile_paths    = None
        self.included_files          = {}
        self.unhandled_variables     = {}
        self.rules                   = {}
        self.variables               = {}
        self.ifdef_variables         = {}

    def load_tree(self, retain_metadata=False):
        """Loads data from the entire build tree into the instance."""

        self.retain_metadata = retain_metadata

        self.top_source_dir = self.top_makefile.get_variable_string('topsrcdir')

        # First, collect all the Makefiles that we can find.

        all_makefiles = set()

        for root, dirs, files in os.walk(self.dir):
            for name in files:
                if name == 'Makefile' or name[-3:] == '.mk':
                    all_makefiles.add(os.path.normpath(os.path.join(root, name)))

        # manually add other, special .mk files
        # TODO grab these automatically
        for path in self.SOURCE_DIR_MAKEFILES:
            all_makefiles.add(os.path.normpath(
                os.path.join(self.top_source_dir, path))
            )

        self.all_makefile_paths = sorted(all_makefiles)

        # Prune out the directories that have known problems.
        self.relevant_makefile_paths = []
        self.ignored_makefile_paths = []
        for path in self.all_makefile_paths:
            subpath = path[len(self.dir)+1:]

            relevant = True
            for ignore in self.IGNORE_DIRECTORIES:
                if subpath.find(ignore) == 0:
                    relevant = False
                    break

            if relevant:
                self.relevant_makefile_paths.append(path)
            else:
                self.ignored_makefile_paths.append(path)

        self.handled_makefile_paths = set()
        self.error_makefile_paths   = set()

        self.tree = data.TreeInfo()
        self.tree.object_directory = self.dir
        self.tree.top_source_directory = self.top_source_dir

        # Traverse over all relevant Makefiles
        for path in self.relevant_makefile_paths:
            try:
                self.load_makefile(path, retain_metadata=retain_metadata)
            except Exception, e:
                print 'Exception loading Makefile: %s' % path
                traceback.print_exc()
                self.error_makefile_paths.add(path)

        # Look for JAR Manifests in source directories and extract data from
        # them.
        for d in self.tree.source_directories:
            jarfile = os.path.normpath(os.path.join(d, 'jar.mn'))

            if os.path.exists(jarfile):
                self.tree.jar_manifests[jarfile] = self.parse_jar_manifest(jarfile)

        # Parse the IDL files.
        for m, d in self.tree.xpidl_modules.iteritems():
            for f in d['sources']:
                try:
                    filename = os.path.normpath(os.path.join(d['source_dir'], f))
                    self.tree.idl_sources[filename] = self.parse_idl_file(filename)
                except Exception, e:
                    print 'Error parsing IDL file: %s' % filename
                    print e

    def load_makefile(self, path, retain_metadata=False):
        """Loads an indivudal Makefile into the instance."""
        assert(os.path.normpath(path) == path)
        assert(os.path.isabs(path))

        self.handled_makefile_paths.add(path)
        m = MozillaMakefile(path)

        own_variables = set(m.get_own_variable_names(include_conditionals=True))

        if retain_metadata:
            self.collect_makefile_metadata(m)

        # We don't perform additional processing of included files. This
        # assumes that .mk means included, which appears to currently be fair.
        if path[-3:] == '.mk':
            return

        # prune out lowercase variables, which are defined as local
        lowercase_variables = set()
        for v in own_variables:
            if v.islower():
                lowercase_variables.add(v)

        used_variables = set()

        # We now register this Makefile with the monolithic data structure
        for obj in m.get_data_objects():
            used_variables |= obj.used_variables

            if obj.source_dir is not None:
                self.tree.source_directories.add(obj.source_dir)

            if isinstance(obj, data.XPIDLInfo):
                module = obj.module
                assert(module is not None)

                self.tree.xpidl_modules[module] = {
                    'source_dir': obj.source_dir,
                    'module':     module,
                    'sources':    obj.sources,
                }

                self.tree.idl_directories.add(obj.source_dir)

            elif isinstance(obj, data.ExportsInfo):
                for k, v in obj.exports.iteritems():
                    k = '/%s' % k

                    if k not in self.tree.exports:
                        self.tree.exports[k] = {}

                    for f in v:
                        #if f in v:
                        #    print 'WARNING: redundant exports file: %s (from %s)' % ( f, obj.source_dir )

                        search_paths = [obj.source_dir]
                        search_paths.extend(obj.vpath)

                        found = False

                        for path in search_paths:
                            filename = os.path.join(path, f)
                            if not os.path.exists(filename):
                                continue

                            found = True
                            self.tree.exports[k][f] = filename
                            break

                        if not found:
                            print 'Could not find export file: %s from %s' % ( f, obj.source_dir )

            elif isinstance(obj, data.LibraryInfo):
                name = obj.name

                if name in self.tree.libraries:
                    print 'WARNING: library already defined: %s' % name
                    continue

                def normalize_include(path):
                    if os.path.isabs(path):
                        return path

                    return os.path.normpath(os.path.join(obj.directory, path))

                includes = []
                for path in obj.includes:
                    includes.append(normalize_include(path))
                for path in obj.local_includes:
                    includes.append(normalize_include(path))

                self.tree.libraries[name] = {
                    'c_flags':     obj.c_flags,
                    'cpp_sources': obj.cpp_sources,
                    'cxx_flags':   obj.cxx_flags,
                    'defines':     obj.defines,
                    'includes':    includes,
                    'pic':         obj.pic,
                    'is_static':   obj.is_static,
                    'source_dir':  obj.source_dir,
                    'output_dir':  obj.directory,
                }

            elif isinstance(obj, data.MiscInfo):
                if obj.included_files is not None:
                    for path in obj.included_files:
                        v = self.included_files.get(path, set())
                        v.add(m.filename)
                        self.included_files[path] = v

        unused_variables = own_variables - used_variables - lowercase_variables
        for var in unused_variables:
            entry = self.unhandled_variables.get(var, set())
            entry.add(path)
            self.unhandled_variables[var] = entry

    def collect_makefile_metadata(self, m):
        """Collects metadata from a Makefile into memory."""
        assert(isinstance(m, MozillaMakefile))

        own_variables = set(m.get_own_variable_names(include_conditionals=True))
        own_variables_unconditional = set(m.get_own_variable_names(include_conditionals=False))

        for v in own_variables:
            if v not in self.variables:
                self.variables[v] = {
                    'paths':               set(),
                    'conditional_paths':   set(),
                    'unconditional_paths': set(),
                }

            info = self.variables[v]
            info['paths'].add(m.filename)
            if v in own_variables_unconditional:
                info['unconditional_paths'].add(m.filename)
            else:
                info['conditional_paths'].add(m.filename)

        for (name, expected, is_conditional, (path, line, column)) in m.statements.ifdefs:
            if name not in self.variables:
                self.variables[name] = {
                    'paths':               set(),
                    'conditional_paths':   set(),
                    'unconditional_paths': set(),
                }

            self.variables[name]['paths'].add(m.filename)

            if name not in self.ifdef_variables:
                self.ifdef_variables[name] = {}

            d = self.ifdef_variables[name]
            if m.filename not in d:
                d[m.filename] = []

            d[m.filename].append((expected, line))

        if m.filename not in self.rules:
            self.rules[m.filename] = []

        rules = self.rules[m.filename]

        for rule in m.statements.rules:
            rule['condition_strings'] = [m.condition_to_string(c) for c in rule['conditions']]
            rules.append(rule)

    def parse_jar_manifest(self, filename):
        """Parse the contents of a JAR manifest filename into a data structure."""

        # TODO hook into JarMaker.py to parse the JAR
        return {}

    def parse_idl_file(self, filename):
        idl_data = open(filename).read()
        p = xpidl.IDLParser()
        idl = p.parse(idl_data, filename=filename)

        # TODO it probably isn't correct to search *all* idl directories
        # because the same file may be defined multiple places.
        idl.resolve(self.tree.idl_directories, p)

        return {
            'filename':     filename,
            'dependencies': [os.path.normpath(dep) for dep in idl.deps],
        }

    def get_rules_for_makefile(self, path):
        """Obtain all the rules for a Makefile at a path."""

        if not self.retain_metadata:
            raise Exception('Metadata is not being retained. Refusing to proceed.')

        return self.rules.get(path, [])

    def get_target_names_from_makefile(self, path):
        """Obtain a set of target names from a Makefile."""
        if not self.retain_metadata:
            raise Exception('Metadata is not being retained. Refusing to proceed.')

        targets = set()

        for rule in self.rules.get(path, []):
            targets |= set(rule['targets'])

        return targets