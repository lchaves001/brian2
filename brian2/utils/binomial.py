'''
Implementation of `BinomialFunction`
'''
import numpy as np

from brian2.core.base import Nameable
from brian2.core.functions import Function, DEFAULT_FUNCTIONS
from brian2.units.fundamentalunits import check_units
from .stringtools import replace


__all__ = ['BinomialFunction']


class BinomialFunction(Function, Nameable):
    '''
    BinomialFunction(n, p, approximate=True, name='_binomial*')

    A function that generates samples from a binomial distribution.

    Parameters
    ----------
    n : int
        Number of samples
    p : float
        Probablility
    approximate : bool, optional
        Whether to approximate the binomial with a normal distribution if
        :math:`n p > 5 \wedge n (1 - p) > 5`. Defaults to ``True``.
    '''
    @check_units(n=1, p=1)
    def __init__(self, n, p, approximate=True, name='_binomial*'):
        Nameable.__init__(self, name)

        #Python implementation
        use_normal = approximate and (n*p > 5) and n*(1-p) > 5
        if use_normal:
            loc = n*p
            scale = np.sqrt(n*p*(1-p))
            def sample_function(vectorisation_idx):
                try:
                    N = len(vectorisation_idx)
                except TypeError:
                    N = int(vectorisation_idx)
                return np.random.normal(loc, scale, size=N)
        else:
            def sample_function(vectorisation_idx):
                try:
                    N = len(vectorisation_idx)
                except TypeError:
                    N = int(vectorisation_idx)
                return np.random.binomial(n, p, size=N)

        Function.__init__(self, pyfunc=lambda: sample_function(1),
                          arg_units=[], return_unit=1, stateless=False)
        self.implementations.add_implementation('numpy', sample_function)

        # Common pre-calculations for C++ and Cython
        if use_normal:
            loc = n*p
            scale = np.sqrt(n*p*(1-p))
        else:
            reverse = p > 0.5
            if reverse:
                P = 1.0 - p
            else:
                P = p
            q = 1.0 - P
            qn = np.exp(n * np.log(q))
            bound = min(n, n*P + 10.0*np.sqrt(n*P*q + 1))

        # C++ implementation
        # Inversion transform sampling
        if use_normal:
            loc = n*p
            scale = np.sqrt(n*p*(1-p))
            cpp_code = '''
            float %NAME%(const int vectorisation_idx)
            {
                return _randn(vectorisation_idx) * %SCALE% + %LOC%;
            }
            '''
            cpp_code = replace(cpp_code, {'%SCALE%': '%.15f' % scale,
                                          '%LOC%': '%.15f' % loc,
                                          '%NAME%': self.name})
            dependencies = {'_randn': DEFAULT_FUNCTIONS['randn']}
        else:
            # The following code is an almost exact copy of numpy's
            # rk_binomial_inversion function
            # (numpy/random/mtrand/distributions.c)
            cpp_code = '''
            long %NAME%(const int vectorisation_idx)
            {
                long X = 0;
                double px = %QN%;
                double U = _rand(vectorisation_idx);
                while (U > px)
                {
                    X++;
                    if (X > %BOUND%)
                    {
                        X = 0;
                        px = %QN%;
                        U = _rand(vectorisation_idx);
                    } else
                    {
                        U -= px;
                        px = ((%N%-X+1) * %P% * px)/(X*%Q%);
                    }
                }
                return %RETURN_VALUE%;
            }
            '''
            cpp_code = replace(cpp_code, {'%N%': '%d' % n,
                                          '%P%': '%.15f' % P,
                                          '%Q%': '%.15f' % q,
                                          '%QN%': '%.15f' % qn,
                                          '%BOUND%': '%.15f' % bound,
                                          '%RETURN_VALUE%': '%d-X' % n if reverse else 'X',
                                          '%NAME%': self.name})
            dependencies = {'_rand': DEFAULT_FUNCTIONS['rand']}

        self.implementations.add_implementation('cpp', {'support_code': cpp_code},
                                                dependencies=dependencies,
                                                name=self.name)

        # Cython implementation
        # Inversion transform sampling
        if use_normal:
            cython_code = '''
            cdef float %NAME%(const int vectorisation_idx):
                return _randn(vectorisation_idx) * %SCALE% + %LOC%
            '''
            cython_code = replace(cython_code, {'%SCALE%': '%.15f' % scale,
                                                '%LOC%': '%.15f' % loc,
                                                '%NAME%': self.name})
            dependencies = {'_randn': DEFAULT_FUNCTIONS['randn']}
        else:
            # The following code is an almost exact copy of numpy's
            # rk_binomial_inversion function
            # (numpy/random/mtrand/distributions.c)
            cython_code = '''
            cdef long %NAME%(const int vectorisation_idx):
                cdef long X = 0
                cdef double px = %QN%
                cdef double U = _rand(vectorisation_idx)
                while U > px:
                    X += 1
                    if X > %BOUND%:
                        X = 0
                        px = %QN%
                        U = _rand(vectorisation_idx)
                    else:
                        U -= px
                        px = ((%N%-X+1) * %P% * px)/(X*%Q%)
                return %RETURN_VALUE%
            '''
            cython_code = replace(cython_code, {'%N%': '%d' % n,
                                                '%P%': '%.15f' % p,
                                                '%Q%': '%.15f' % q,
                                                '%QN%': '%.15f' % qn,
                                                '%BOUND%': '%.15f' % bound,
                                                '%RETURN_VALUE%': '%d-X' % n if reverse else 'X',
                                                '%NAME%': self.name})
            dependencies = {'_rand': DEFAULT_FUNCTIONS['rand']}

        self.implementations.add_implementation('cython', cython_code,
                                                dependencies=dependencies,
                                                name=self.name)