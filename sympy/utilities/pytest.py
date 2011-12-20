"""py.test hacks to support XFAIL/XPASS"""

# XXX this should be integrated into py.test
# XXX but we can't force everyone to install py-lib trunk

import sys
import functools
import signal
import os

try:
    # tested with py-lib 0.9.0
    from py.__.test.outcome import Outcome, Passed, Failed, Skipped
    from py.__.test.terminal.terminal import TerminalSession
    from py.test import skip
    USE_PYTEST = True
except ImportError:
    USE_PYTEST = False

def raises(ExpectedException, code):
    """
    Tests that ``code`` raises the exception ``ExpectedException``.

    Does nothing if the right exception is raised, otherwise raises an
    AssertionError.

    Example:

    >>> from sympy.utilities.pytest import raises
    >>> raises(ZeroDivisionError, "1/0")
    >>> raises(ZeroDivisionError, "1/2")
    Traceback (most recent call last):
    ...
    AssertionError: DID NOT RAISE

    """
    if not isinstance(code, str):
        raise TypeError('raises() expects a code string for the 2nd argument.')
    frame = sys._getframe(1)
    loc = frame.f_locals.copy()
    try:
        exec code in frame.f_globals, loc
    except ExpectedException:
        return
    raise AssertionError("DID NOT RAISE")

if not USE_PYTEST:
    class XFail(Exception):
        pass

    class XPass(Exception):
        pass

    class Skipped(Exception):
        pass

    def XFAIL(func):
        def wrapper():
            try:
                func()
            except Exception, e:
                if sys.version_info[:2] < (2, 6):
                    message = getattr(e, 'message', '')
                else:
                    message = str(e)
                if message != "Timeout":
                    raise XFail(func.func_name)
                else:
                    raise Skipped("Timeout")
            raise XPass(func.func_name)

        wrapper = functools.update_wrapper(wrapper, func)
        return wrapper

    def skip(str):
        raise Skipped(str)
else:
    from time import time as now

    __all__ = ['XFAIL']

    class XFail(Outcome):
        pass

    class XPass(Outcome):
        pass

    TerminalSession.typemap[XFail] = 'f'
    TerminalSession.typemap[XPass] = 'X'

    TerminalSession.namemap[XFail] = 'XFAIL'
    TerminalSession.namemap[XPass] = '*** XPASS ***'


    def footer(self, colitems):
        super(TerminalSession, self).footer(colitems)
        self.endtime = now()
        self.out.line()
        self.skippedreasons()
        self.failures()
        self.xpasses()
        self.summaryline()


    def xpasses(self):
        """report unexpectedly passed tests"""
        texts = {}
        for colitem, outcome in self.getitemoutcomepairs(XPass):
            raisingtb = self.getlastvisible(outcome.excinfo.traceback)
            fn = raisingtb.frame.code.path
            lineno = raisingtb.lineno
            #d = texts.setdefault(outcome.excinfo.exconly(), {})
            d = texts.setdefault(outcome.msg, {})
            d[(fn,lineno)] = outcome

        if texts:
            self.out.line()
            self.out.sep('_', '*** XPASS ***')
            for text, dict in texts.items():
                #for (fn, lineno), outcome in dict.items():
                #    self.out.line('Skipped in %s:%d' %(fn, lineno+1))
                #self.out.line("reason: %s" % text)
                self.out.line("%s" % text)
                self.out.line()

    def summaryline(self):
        outlist = []
        sum = 0
        for typ in Passed, XPass, XFail, Failed, Skipped:
            l = self.getitemoutcomepairs(typ)
            if l:
                outlist.append('%d %s' % (len(l), typ.__name__.lower()))
            sum += len(l)
        elapsed = self.endtime-self.starttime
        status = "%s" % ", ".join(outlist)
        self.out.sep('=', 'tests finished: %s in %4.2f seconds' %
                         (status, elapsed))

        # SymPy specific
        if self.getitemoutcomepairs(Failed):
            self.out.line('DO *NOT* COMMIT!')

    TerminalSession.footer  = footer
    TerminalSession.xpasses = xpasses
    TerminalSession.summaryline = summaryline

    def XFAIL(func):
        """XFAIL decorator"""
        def func_wrapper():
            try:
                func()
            except Outcome:
                raise   # pass-through test outcome
            except XFail(Exception):
                raise XFail(func.func_name)
            else:
                raise XPass(func.func_name)

        func_wrapper = functools.update_wrapper(func_wrapper, func)
        return func_wrapper

def SKIP(reason):
    """Similar to :func:`skip`, but this is a decorator. """
    def wrapper(func):
        def func_wrapper():
            raise Skipped(reason)

        func_wrapper = functools.update_wrapper(func_wrapper, func)
        return func_wrapper

    return wrapper

def slow(func):
    func._slow = True
    def func_wrapper():
        func()

    func_wrapper = functools.update_wrapper(func_wrapper, func)
    return func_wrapper
