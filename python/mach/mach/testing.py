# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mach.base import ArgumentProvider
from mozbuild.base import Base

class Testing(Base, ArgumentProvider):
    """Provides commands for running tests."""

    def run_suite(self, suite):
        from mozbuild.testing.suite import Suite

        s = Suite(self.config)
        s.run_suite(suite)

    def run_mochitest_plain(self, test_file):
        from mozbuild.testing.mochitest import MochitestRunner

        mochitest = MochitestRunner(self.config)
        mochitest.run_mochitest_test(test_file, 'plain')

    def run_mochitest_chrome(self, test_file):
        from mozbuild.testing.mochitest import MochitestRunner

        mochitest = MochitestRunner(self.config)
        mochitest.run_mochitest_test(test_file, 'chrome')

    def run_mochitest_browser(self, test_file):
        from mozbuild.testing.mochitest import MochitestRunner

        mochitest = MochitestRunner(self.config)
        mochitest.run_mochitest_test(test_file, 'browser')

    def run_xpcshell_test(self, **params):
        from mozbuild.testing.xpcshell import XPCShellRunner

        xpcshell = XPCShellRunner(self.config)
        xpcshell.run_test(**params)

    @staticmethod
    def populate_argparse(parser):
        # Whole suites.
        group = parser.add_parser('test',
                                  help="Perform tests.")

        suites = set(['xpcshell', 'mochitest-plain', 'mochitest-chrome',
            'mochitest-browser', 'all'])

        group.add_argument('suite', default='all', choices=suites, nargs='?',
            help="Test suite to run.")

        group.set_defaults(cls=Testing, method='run_suite', suite='all')

        # Mochitests.
        mochitest_plain = parser.add_parser('mochitest-plain',
            help='Run a plain mochitest.')
        mochitest_plain.add_argument('test_file', default='all', nargs='?',
            metavar='TEST',
            help='Test to run. Can be specified as a single JS file, a '
                 'directory, or omitted. If omitted, all the tests are '
                 'executed.')
        mochitest_plain.set_defaults(cls=Testing, method='run_mochitest_plain')

        mochitest_chrome = parser.add_parser('mochitest-chrome',
            help='Run a chrome mochitest.')
        mochitest_chrome.add_argument('test_file', default='all', nargs='?',
            metavar='TEST', help='Test to run.')
        mochitest_chrome.set_defaults(cls=Testing,
            method='run_mochitest_chrome')

        mochitest_browser = parser.add_parser('mochitest-browser',
            help='Run a mochitest with browser chrome.')
        mochitest_browser.add_argument('test_file', default='all', nargs='?',
            metavar='TEST', help='Test to run.')
        mochitest_browser.set_defaults(cls=Testing,
            method='run_mochitest_browser')

        # XPCshell tests.
        xpcshell = parser.add_parser('xpcshell-test',
            help="Run an individual xpcshell test.")

        xpcshell.add_argument('test_file', default='all', nargs='?',
            metavar='TEST',
            help='Test to run. Can be specified as a single '
                 'JS file, an xpcshell.ini manifest file, '
                 'a directory, or omitted. If omitted, the '
                 'entire xpcshell suite is executed.')

        xpcshell.add_argument('--debug', '-d', action='store_true',
            help='Run test in debugger.')

        xpcshell.set_defaults(cls=Testing, method='run_xpcshell_test')
