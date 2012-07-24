# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import os.path
import traceback

from pymake.builder import Makefile
from StringIO import StringIO

import mozbuild.buildconfig.data as data

from mozbuild.buildconfig.backend.base import BackendBase
from mozbuild.buildconfig.backend.utils import makefile_output_path
from mozbuild.buildconfig.backend.utils import substitute_makefile

class HybridMakeBackend(BackendBase):
    """The "hybrid make" backend.

    This backend combines the legacy recursive make files with non-recursive
    make files.

    The generation phase of this backend extracts data from Makefile.in's. For
    pieces it knows how to handle, it writes out an optimized, non-recursive
    .mk file in the output directory. It removes statements from the original
    Makefile.in that are now handled by the dynamically-created non-recursive
    .mk file and writes out the translated Makefile in the output directory,
    just like the legacy backend. It tops things off by writing out a single
    .mk file in the root directory of the object directory that includes all
    the non-recursive .mk files.

    The backend phase invokes both the legacy and non-recursive .mk files in
    the right order so things build properly.
    """
    def __init__(self, *args):
        BackendBase.__init__(self, *args)

        self.splendid_files = set()

    @property
    def makefiles(self):
        for makefile in self.frontend.makefiles.makefiles():
            substitute_makefile(makefile, self.frontend)
            yield makefile

    ############################
    # Generation Functionality #
    ############################

    def _generate(self):
        for makefile in self.makefiles:
            try:
                self._generate_makefile(makefile)
            except:
                print 'Error processing %s' % makefile.filename
                traceback.print_exc()

        hybrid_path = os.path.join(self.objdir, 'hybridmake.mk')
        with open(hybrid_path, 'wb') as fh:
            self.print_hybridmake(fh)

        dependencies = [m.filename for m in self.makefiles]
        self.add_generate_output_file(hybrid_path, dependencies)

    def _generate_makefile(self, original):
        # TODO MozillaMakefile should use proper statements API.
        output_path = makefile_output_path(self.srcdir, self.objdir, original)
        output_directory = os.path.dirname(output_path)
        original.directory = output_directory

        splendid_path = os.path.join(output_directory, 'splendid.mk')
        buf = StringIO()
        strip_variables = self.write_splendid_makefile(original, buf)

        # We don't always have content for the non-recursive file. Only write
        # if necessary.
        if len(buf.getvalue()):
            with open(splendid_path, 'wb') as fh:
                print >>fh, buf.getvalue()

            self.add_generate_output_file(splendid_path, [original.filename])
            self.splendid_files.add(splendid_path)

        makefile = Makefile(output_path)

        for statement in original.statements._statements:
            makefile.append(statement.statement)

        # Strip out variables we handle ourselves so the legacy build system
        # doesn't do anything.
        for name in strip_variables:
            makefile.remove_variable_assignment(name)

        with open(output_path, 'wb') as fh:
            fh.write(makefile.to_source())

        self.add_generate_output_file(output_path, [original.filename])

    def write_splendid_makefile(self, makefile, fh):
        """Writes a splendid, non-recursive make file."""

        strip_variables = set()

        for obj in makefile.get_data_objects():
            method = None
            if isinstance(obj, data.ExportsInfo):
                method = self._write_exports
            elif isinstance(obj, data.XPIDLInfo):
                method = self._write_idl

            if method:
                strip_variables |= method(makefile, fh, obj)

        return strip_variables

    def _write_exports(self, makefile, fh, obj):
        # Install exported files into proper location. These are
        # typically header files.

        inc_dir = os.path.join(self.objdir, 'dist', 'include')

        directories = sorted(obj.output_directories)
        out_directories = [os.path.join(inc_dir, d) for d in directories]
        self.output_directories |= set(out_directories)
        print >>fh, 'CREATE_DIRS += %s' % ' '.join(out_directories)

        output_filenames = []

        for input_filename, output_leaf in obj.filenames.iteritems():
            output_directory = os.path.join(inc_dir,
                os.path.dirname(output_leaf))
            output_filename = os.path.join(inc_dir, output_leaf)
            output_filenames.append(output_filename)

            print >>fh, '%s: %s' % (output_filename, input_filename)
            print >>fh, '\t$(INSTALL) -R -m 644 "%s" "%s"\n' % (input_filename,
                output_directory)

        print >>fh, 'EXPORT_TARGETS += %s\n' % ' \\\n  '.join(output_filenames)
        print >>fh, 'PHONIES += EXPORT_TARGETS'

        return obj.exclusive_variables

    def _write_idl(self, makefile, fh, obj):
        # IDLs are copied to a common idl directory then they are processed.
        # The copying must complete before processing starts.
        idl_output_directory = os.path.join(self.objdir, 'dist', 'idl')
        header_output_directory = os.path.join(self.objdir, 'dist', 'include')

        gen_directory = os.path.join(makefile.directory, '_xpidlgen')
        self.output_directories.add(gen_directory)

        for source in sorted(obj.sources):
            basename = os.path.basename(source)
            stripped_name = os.path.splitext(basename)[0]
            header_basename = stripped_name + '.h'
            xpt_basename = stripped_name + '.xpt'

            output_idl_path = os.path.join(idl_output_directory, basename)
            output_header_path = os.path.join(header_output_directory,
                header_basename)

            xpt_output_path = os.path.join(gen_directory, xpt_basename)

            # Record the final destination of this IDL in a variable so that
            # variable can be used as a prerequisite.
            print >>fh, 'IDL_DIST_FILES += %s' % output_idl_path
            print >>fh, 'IDL_H_FILES += %s' % output_header_path
            print >>fh, ''

            # Install the original IDL file into the IDL directory.
            print >>fh, '%s: %s' % (output_idl_path, source)
            print >>fh, '\t$(INSTALL) -R -m 664 "%s" "%s"\n' % (source,
                idl_output_directory)
            print >>fh, ''

            # TODO write out IDL dependencies file via rule and hook up to
            # prereqs for IDL generation. This requires a bit more code to be
            # written. For now, we omit the dependencies, which is very wrong.
            idl_deps_path = os.path.join(self.objdir, 'deps',
                '%s.deps' % basename)

            print >>fh, '%s: $(IDL_DIST_FILES)' % output_header_path
            print >>fh, '\t$(IDL_GENERATE_HEADER) -o $@ %s' % output_idl_path
            print >>fh, ''

            # Generate intermediate .xpt file.
            print >>fh, 'IDL_XPT_FILES += %s' % xpt_output_path
            print >>fh, '%s: %s' % (xpt_output_path, output_idl_path)
            print >>fh, '\t$(IDL_GENERATE_XPT) %s -o $@' % output_idl_path

        # Link .xpt files into final .xpt file.
        if obj.link_together:
            pass

        # Install final .xpt file into dist.
        # TODO

        return obj.exclusive_variables

    def print_hybridmake(self, fh):
        print >>fh, '# This file is automatically generated. Do NOT edit.'

        print >>fh, 'TOP_SOURCE_DIR := %s' % self.srcdir
        print >>fh, 'OBJECT_DIR := %s' % self.objdir

        print >>fh, 'DEPTH := .'
        print >>fh, 'topsrcdir := %s' % self.srcdir
        print >>fh, 'srcdir := %s' % self.srcdir
        print >>fh, 'include $(topsrcdir)/config/config.mk'

        print >>fh, 'default:'
        print >>fh, '\t@echo "Use mach to build with this file."; \\'
        print >>fh, '\texit 1;'
        print >>fh, '\n'

        for path in sorted(self.splendid_files):
            print >>fh, 'include %s' % path

        print >>fh, 'include $(TOP_SOURCE_DIR)/config/makefiles/nonrecursive.mk'

    #######################
    # Build Functionality #
    #######################

    def _build(self):
        for path in self.output_directories:
            self.mkdir(path)

        # We have to run all the tiers separately because the main Makefile's
        # default target removes output directories, which is silly.
        self._run_make(target='export_tier_base')
        self._run_make(filename='hybridmake.mk', target='export')
        self._run_make(target='tier_base')
        self._run_make(target='tier_nspr')
        self._run_make(target='tier_js')
        self._run_make(target='export_tier_platform')
        # self._run_make(filename='hybridmake.mk', target='libs')
        self._run_make(target='libs_tier_platform')
        self._run_make(target='tools_tier_platform')
        self._run_make(target='export_tier_app')
        self._run_make(target='libs_tier_app')
        self._run_make(target='tools_tier_app')

    def _clean(self):
        pass
