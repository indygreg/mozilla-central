# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

# This file defines routines that interact with autoconf and configure.

import glob
import logging
import os.path
import sys

from mozbuild.base import Base


class Configure(Base):
    """Provides an interface to configuring a source and object tree.

    Yes, a lot of the code here duplicates functionality in client.mk. This is
    arguably necessary evil. It was originally implemented like this because
    mozbuild was completely outside the build system and making it work with
    client.mk would require hacking client.mk to support some "odd" scenarios.
    This would have made an already difficult-to-read makefile even more
    complicated.

    If there is a will, the duplication of functionality could be consolidated.
    The configure logic could be moved into a standalone .mk file and that
    could be consumed by both client.mk and in this module. Or, we could nuke
    client.mk altogether and this would be the definitive source of truth.
    Whatever happens, that's in the future.

    We are also missing some functionality from client.mk, such as the
    check-sync-dirs target. We can add this if there is desire. Although, that
    may live in a higher-level build frontend driver/module.
    """
    AUTOCONFS = ['autoconf-2.13', 'autoconf2.13', 'autoconf213']

    def __init__(self, settings, log_manager):
        Base.__init__(self, settings, log_manager)

        # False is used as a semaphore to prevent multiple lookups since None
        # means no executable was found.
        self._autoconf = False

    @property
    def configure_scripts(self):
        """The set of configure scripts generated by autoconf."""
        paths = ['configure', 'js/src/configure']

        return [self._get_srcdir_path(p) for p in paths]

    @property
    def autoconf(self):
        """Find the path to autoconf or raise if not found."""
        if self._autoconf is False:
            self._autoconf = self._find_executable_in_path(Configure.AUTOCONFS)

        if not self._autoconf:
            raise Exception('Could not find autoconf 2.13')

        return self._autoconf

    @property
    def configure_mtime(self):
        """Returns the modified time of the generated configure script.

        There are actually multiple configure scripts. We stat them both and
        choose the oldest time.
        """
        return min(os.path.getmtime(p) for p in self.configure_scripts)

    def run_configure(self):
        """Runs configure."""

        self._ensure_objdir_exists()

        args = [os.path.join(self.srcdir, 'configure')]
        args.extend(self.config.configure_args)

        env = self.config.get_environment_variables()

        # configure calls out to things that expect MAKE to be defined.
        # We must use the same heuristic as Base._run_make to determine which
        # path to specify.
        if self._is_windows():
            pymake = os.path.join(self.srcdir, 'build', 'pymake', 'make.py')

            # We need the Python path in the environment variable and to use
            # UNIX-style paths, even on Windows, otherwise things break.
            env['MAKE'] = ' '.join([sys.executable, pymake]).replace('\\', '/')
        else:
            env['MAKE'] = self._find_executable_in_path(['gmake', 'make'])
            assert env['MAKE'] is not None

        self._run_command_in_objdir(args=args, env=env,
                require_unix_environment=True,
                log_name='configure_output')

    def run_autoconfs(self):
        """Runs all necessary autoconf invocations to generate configures."""
        for configure in self.configure_scripts:
            self.run_autoconf(os.path.dirname(configure))

    def run_autoconf(self, directory):
        """Runs autoconf on a file."""

        autoconf = self.autoconf

        self.log(logging.INFO, 'autoconf', {'directory': directory},
                'Running autoconf in {directory} to generate configure')

        self._run_command([autoconf], cwd=directory, log_name='autoconf',
                require_unix_environment=True)

    @property
    def autoconf_dependencies(self):
        """The set of files that trigger a new autoconf run.

        This is equivalent to EXTRA_CONFIG_DEPS in client.mk.
        """
        paths = []

        for configure in self.configure_scripts:
            paths.append(configure + '.in')

        paths.append(self._get_srcdir_path('aclocal.m4'))
        paths.append(self._get_srcdir_path('js/src/aclocal.m4'))

        for path in os.listdir(self._get_srcdir_path('build/autoconf')):
            if not path.endswith('.m4'):
                continue

            paths.append(self._get_srcdir_path('build/autoconf/%s' % path))

        return paths

    @property
    def configure_dependencies(self):
        """The set of files that trigger a new configure run.

        This is equivalent to CONFIG_STATUS_DEPS in client.mk.
        """
        paths = []
        paths.extend(self.configure_scripts)

        simple_paths = [
            'allmakefiles.sh',
            'nsprpub/configure',
            'config/milestone.txt',
            'js/src/config/milestone.txt',
            'browser/config/version.txt',
            'build/virtualenv/packages.txt',
            'build/virtualenv/populate_virtualenv.py',
        ]
        for p in simple_paths:
            paths.append(self._get_srcdir_path(p))

        for p in glob.glob('%s/*/confvars.sh' % self.srcdir):
            paths.append(p)

        paths.extend(self.settings.loaded_files())

        return paths

    def ensure_configure(self):
        """Ensures configure is in a good state and run if out of date.

        This should be called in the course of normal build activities to
        ensure the build environment is up to date.

        This emulates logic from client.mk.

        Returns boolean indicating whether configure was actually executed.
        """
        self.ensure_autoconf()

        makefile_path = self._get_objdir_path('Makefile')

        if not os.path.exists(makefile_path):
            self.run_configure()
            return True

        output_mtime = os.path.getmtime(makefile_path)

        for dependency in self.configure_dependencies:
            dependency_mtime = os.path.getmtime(dependency)

            if output_mtime < dependency_mtime:
                self.run_configure()
                return True

        return False

    def ensure_autoconf(self):
        """Ensures autoconf's output is up-to-date.

        This is called by ensure_configure() and probably has little relevance
        outside of this module.
        """
        did_autoconf = False
        for configure in self.configure_scripts:
            if not os.path.exists(configure):
                self.log(logging.DEBUG, 'trigger_autoconf_no_configure',
                    {'configure_path': configure},
                    'Running autoconf because configure missing: '
                        '{configure_path}')
                self.run_autoconf(os.path.dirname(configure))
                did_autoconf = True

        if did_autoconf:
            return

        configure_mtime = self.configure_mtime

        for dependency in self.autoconf_dependencies:
            dependency_mtime = os.path.getmtime(dependency)

            if dependency_mtime > configure_mtime:
                self.log(logging.DEBUG, 'trigger_autoconfs_mtime',
                    {'dependency': dependency},
                    'Running autoconf because dependency is newer than '
                        'configure: {dependency}')
                self.run_autoconfs()
                return
