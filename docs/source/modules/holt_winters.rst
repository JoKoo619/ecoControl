====================
Holt-Winters Methods
====================

.. automodule:: server.forecasting.statistical.holt_winters
    :members:
    :member-order: bysource


:mod:`Choltwinters` --- Holt-Winters Extensions
-----------------------------------------------

.. py:module:: Choltwinters
        :synopsis: Optimized Holt-Winters Methods.


This module contains an optimized version of the Holt-Winters double-seasonal method and the multiplicative method.


The functions in this module should deliver the same results as the unoptimized version in :mod:`~server.forecasting.statistical.holt_winters`. Just import the :func:`double_seasonal` from this module instead of the one in holt_winters.py. This module has to be compiled with `Cython <http://cython.org/>`_, it introduces statically typed variables and optimizes array usage
and can therefore get speedups up to 100x. 
Note that the optimizing function differs from the normal version, as it first searches the global boundaries and then
does a extremely accurate local search. 
This leads to results very close to the absolute optimum.

To build this module, use the :func:`~server.forecasting.statistical.build_holtwinters_extension` function.
If it suceeds, a .pyd extension is built, which can be used like a normal python module.
An example for importing and building the extension can be seen in :mod:`server.forecasting.forecasting` (source).
