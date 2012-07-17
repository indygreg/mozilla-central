# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

from mozbuild.cli.base import ArgumentProvider
from mozbuild.base import Base

class Testing(Base, ArgumentProvider):
    def run_suite(self, suite):
        from mozbuild.testing.suite import Suite

        s = Suite(self.config)
        s.run_suite(suite)

    def run_mochitest_test(self, **params):
        from mozbuild.testing.mochitest import MochitestRunner

        mochitest = MochitestRunner(self.config)
        mochitest.run_mochitest_test(**params)

    def run_xpcshell_test(self, **params):
        from mozbuild.testing.xpcshell import XPCShellRunner

        xpcshell = XPCShellRunner(self.config)
        xpcshell.run_test(**params)

    @staticmethod
    def populate_argparse(parser):
        group = parser.add_parser('test',
                                  help="Perform tests.")

        group.set_defaults(cls=Testing, method='run_suite', suite='all')

        suites = set(['xpcshell', 'mochitest-plain',
            'mochitest-browser-chrome', 'all'])

        group.add_argument('suite', default='all', choices=suites, nargs='?',
                           help="Test suite to run.")

        mochitest_plain = parser.add_parser('mochitest-plain',
            help='Run a plain mochitest.')
        mochitest_plain.add_argument('test_file', default='all', nargs='?',
                metavar='TEST',
                help='Test to run. Can be specified as a single JS file, a '
                     'directory, or omitted. If omitted, all the tests are '
                     'executed.')
        mochitest_plain.set_defaults(cls=Testing, method='run_mochitest_test',
                plain=True)

        mochitest_chrome = parser.add_parser('mochitest-chrome',
            help='Run a chrome mochitest.')
        mochitest_chrome.add_argument('test_file', default='all', nargs='?',
                metavar='TEST',
                help='Test to run.')
        mochitest_chrome.set_defaults(cls=Testing, method='run_mochitest_test',
                chrome=True)

        mochitest_browser = parser.add_parser('mochitest-browser-chrome',
                help='Run a mochitest with browser chrome.')
        mochitest_browser.add_argument('test_file', default='all', nargs='?',
                metavar='TEST',
                help='Test to run.')
        mochitest_browser.set_defaults(cls=Testing,
                method='run_mochitest_test', browser=True)

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
