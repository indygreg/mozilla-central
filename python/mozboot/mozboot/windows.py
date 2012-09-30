# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import stat
import tempfile
import urllib2

from mozboot.base import BaseBootstrapper


class WindowsBootstrapper(BaseBootstrapper):
    def install_system_packages(self):
        # TODO pass these in.
        base_uri = 'https://hg.mozilla.org/mozilla-build/raw-file/default'
        mb_path = 'c:\\mozilla-build'

        installers = {
            '7z442.exe': (False, ['/S', '/D=%s\\7zip' % mb_path]),
        }

        for installer, options in installers.items():
            use_msiexec, args = options

            suffix = os.path.splitext(installer)[1]
            url = '%s/%s' % (base_uri, installer)
            req = urllib2.urlopen(url=url, timeout=300)

            tf_fd, tf_name = tempfile.mkstemp(suffix=suffix)
            try:
                os.write(tf_fd, req.read())
                os.close(tf_fd)
                tf_fd = None

                mode = os.stat(tf_name).st_mode
                os.chmod(tf_name, mode | stat.S_IXUSR)

                command = [tf_name] + args

                if use_msiexec:
                    pass

                self.check_output(command)
            finally:
                if tf_fd is not None:
                    os.close(tf_fd)
                os.unlink(tf_name)