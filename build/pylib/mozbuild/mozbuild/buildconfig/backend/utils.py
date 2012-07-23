# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# This file provides common utility functions used by multiple backends.

import os.path


def makefile_output_path(srcdir, objdir, makefile):
    """Obtain the output path for a Makefile.in."""

    assert makefile.filename.endswith('.in')
    assert makefile.filename.startswith(srcdir)

    basename = os.path.basename(makefile.filename).rstrip('.in')
    input_directory = makefile.directory
    leaf = input_directory[len(srcdir) + 1:]

    return os.path.join(objdir, leaf, basename)

def substitute_makefile(makefile, frontend):
    assert makefile.filename.endswith('.in')

    variables = dict(frontend.autoconf)
    variables['top_srcdir'] = frontend.srcdir
    variables['srcdir'] = makefile.directory

    makefile.perform_substitutions(variables, raise_on_missing=True)
