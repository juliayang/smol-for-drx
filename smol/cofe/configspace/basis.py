"""Definitions for basis functions over a site function space.

The product of single site functions make up a cluster/orbit function used to
obtain correlation vectors. The domain of a site function is a site space,
which is defined by the allowed species at the site and their measures, which
is concentration of the species in the random structure)
"""

__author__ = "Luis Barroso-Luque"

import warnings
from abc import abstractmethod
from collections import OrderedDict
from collections.abc import Iterator
from functools import partial, wraps
import numpy as np
from numpy.polynomial.polynomial import polyval
from numpy.polynomial.chebyshev import chebval
from numpy.polynomial.legendre import legval

from .domain import SiteSpace
from smol.utils import derived_class_factory


class SiteBasis:
    """Class that represents the basis for a site function space.

    Note that all SiteBasis in theory have the first basis function
    :math:`\phi_0 = 1`, but this should not be defined since it is handled
    implicitly when computing bit_combos using total no. species - 1 in the
    Orbit class.

    The particular basis set is set by giving an iterable of basis functions.
    See BasisIterator classes for details.
    """

    def __init__(self, site_space, basis_functions):
        """Initialize a SiteBasis.

        Currently also accepts an OrderedDict but if you find yourself creating
        one like so for use in production and not debuging know that it will
        break MSONable methods in classes that use these, and at any point I
        could change this to not allow OrderedDicts.

        Args:
            site_space (OrderedDict or SiteSpace):
                Dict representing site space (Specie, measure) or a SiteSpace
                object.
            basis_functions (Sequence like):
                A Sequence of the nonconstant basis functions. Must take the
                valuves of species as input.
        """
        if isinstance(site_space, OrderedDict):
            if not np.allclose(sum(site_space.values()), 1):
                warnings.warn('The measure given does not sum to 1.'
                              'Are you sure this is what you want?',
                              RuntimeWarning)
        elif not isinstance(site_space, SiteSpace):
            raise TypeError('site_space argument must be a SiteSpaces or an '
                            'OrderedDict.')

        self.flavor = basis_functions.flavor
        self._domain = site_space
        # add non constant basis functions to array
        if len(basis_functions) != len(self.species) - 1:
            raise ValueError(f'Must provid {len(self.species) - 1 } total non-'
                             'constant basis functions.'
                             f' Got only {len(basis_functions)} basis '
                             'functions.')

        func_arr = np.array([[function(sp) for sp in self.species]
                             for function in basis_functions])
        # stack the constant basis function on there for proper normalization
        self._func_arr = np.vstack((np.ones_like(func_arr[0]), func_arr))
        self._r_array = None  # array from QR in basis orthonormalization

    @property
    def function_array(self):
        """Get array with the non-constant site functions as rows."""
        return self._func_arr[1:]

    @property
    def measure_array(self):
        """Get diagonal array with site species measures."""
        return np.diag(list(self._domain.values()))

    @property
    def measure_vector(self):
        """Get vector of site species measures."""
        return np.array(list(self._domain.values()))

    @property
    def orthonormalization_array(self):
        """Get R array from QR factorization."""
        return self._r_array

    @property
    def species(self):
        """Get list of allowed site species."""
        return list(self._domain.keys())

    @property
    def site_space(self):
        """Get dict of the site probability space.

        The site space refers to the probability space represented by the
        allowed species and their respective probabilities (concentration)
        over which the site functions are defined.
        """
        return self._domain

    @property
    def is_orthogonal(self):
        """Test if the basis is orthogonal."""
        # add the implicit 0th function
        prods = np.dot(np.dot(self.measure_array, self._func_arr.T).T,
                       self._func_arr.T)
        d_terms = all(not np.isclose(prods[i, i], 0)
                      for i in range(prods.shape[0]))
        x_terms = all(np.isclose(prods[i, j], 0)
                      for i in range(prods.shape[0])
                      for j in range(prods.shape[1])
                      if i != j)
        return x_terms and d_terms

    @property
    def is_orthonormal(self):
        """Test if the basis is orthonormal."""
        prods = np.dot(np.dot(self.measure_array, self._func_arr.T).T,
                       self._func_arr.T)
        identity = np.eye(*prods.shape)
        return np.allclose(identity, prods)

    def orthonormalize(self):
        """Orthonormalizes basis function set based on initial basis set.

        Functions are orthonormal w.r.t the measure given.
        (basis functions are also orthogonal to phi_0 = 1).

        Modified GS-QR factorization of function array (here we are using
        row vectors as opposed to the correct way of doing QR using columns.
        Due to how the func_arr is saved (rows are vectors/functions) this
        allows us to not sprinkle so many transposes.
        """
        Q = np.zeros_like(self._func_arr)
        R = np.zeros_like(self._func_arr)
        V = self._func_arr.copy()
        n = V.shape[0]
        for i, phi in enumerate(V):
            R[i, i] = np.sqrt(np.dot(self.measure_vector*phi, phi))
            Q[i] = phi/R[i, i]
            R[i, i+1:n] = np.dot(V[i+1:n], self.measure_vector*Q[i])
            V[i+1:n] = V[i+1:n] - np.outer(R[i, i+1:n], Q[i])

        self._r_array = R
        self._func_arr = Q


class BasisIterator(Iterator):
    """Abstract basis iterator class.

    A basis iterator iterates through all non-constant site basis functions.
    i.e. for basis :math:`\phi_0 = 1, \phi_1, ..., \phi_{n-1}`,
    the iterator will just iterate through :math:`\phi_1, ..., \phi_{n-1}`

    Attributes:
        flavor (str):
            Name specifying the type of basis that is generated.
    """

    flavor = 'abstract'

    def __init__(self, species):
        """Initialize a BasisIterator.

        Args:
            species (tuple):
                tuple of allowed species in site spaces
        """
        self.species_iter = iter(species[:-1])  # all but one species iterator
        self.species = species

    def __len__(self):
        """Get length of sequence."""
        return len(self.species) - 1


class IndicatorIterator(BasisIterator):
    """Iterator for cluster indicator site basis functions.

    The basis generated as defined is not orthogonal for any number of species.
    """

    flavor = 'indicator'

    def __next__(self):
        """Generate the next basis function."""
        func = partial(indicator, sp=next(self.species_iter))
        return func


class SinusoidIterator(BasisIterator):
    """Iterator for sinusoid (trig basis) as proposed by A. van de Walle.

    A. van de Walle, Calphad. 33, 266–278 (2009).

    This basis is properly orthogonal for any number of allowed species out of
    the box, but it is not orthonormal for allowed species > 2.
    """

    flavor = 'sinusoid'

    def __init__(self, species):
        """Initialize a SinusoidIterator.

        Args:
            species (tuple):
                tuple of allowed species in site spaces
        """
        super().__init__(species)
        self.encoding = {s: i for (i, s) in enumerate(self.species)}

    def __next__(self):
        """Generate the next basis function."""
        n = self.encoding[next(self.species_iter)] + 1
        func = encode_domain(self.encoding)(sinusoid_factory(n, len(self.species)))  # noqa
        return func


class NumpyPolyIterator(BasisIterator):
    """Class to quickly implement polynomial basis sets included in numpy."""

    def __init__(self, species, low=-1, high=1):
        """Initialize a NumpyPolyIterator.

        Args:
            species (tuple):
                tuple of allowed species in site spaces
            low (float): optional
                lower limit of interval for encoding
            high (float): optional
                higher limit of interval for encoding
        """
        super().__init__(species)
        enc = np.linspace(low, high, len(self.species))
        self.encoding = {s: i for (s, i) in zip(species, enc)}

    @property
    @abstractmethod
    def polyval(self):
        """Return a numpy polyval function."""
        return

    def __next__(self):
        """Generate the next basis function."""
        n = self.species.index(next(self.species_iter)) + 1
        coeffs = n*[0, ] + [1]
        func = encode_domain(self.encoding)(partial(self.polyval, c=coeffs))
        return func


class PolynomialIterator(NumpyPolyIterator):
    """A standard polynomial basis set iterator."""

    @property
    def polyval(self):
        """Return numpy Chebyshev polynomial eval."""
        return polyval


class ChebyshevIterator(NumpyPolyIterator):
    """Chebyshev polynomial basis set iterator."""

    @property
    def polyval(self):
        """Return numpy Chebyshev polynomial eval."""
        return chebval


class LegendreIterator(NumpyPolyIterator):
    """Legendre polynomial basis set iterator."""

    @property
    def polyval(self):
        """Return numpy Legendre polynomial eval."""
        return legval


# The actual definitions of the functions used as basis functions.
# These functions should simply define a univariate injective function for
# a finite set of species. If the function requires an encoding for the species
# simply use the encode_domain decorator.
# Definitions must be done outside of classes to prevent pickling problems.


def indicator(s, sp):
    """Singleton indicator function for elementary events."""
    return float(s == sp)


def sinusoid_factory(n, m):
    """Sine or cosine based on AVvW sinusoid site basis."""
    a = -(-n // 2)  # ceiling division
    if n % 2 == 0:
        return partial(sin_f, a=a, m=m)
    else:
        return partial(cos_f, a=a, m=m)


def sin_f(s, a, m):
    """Return basis function for even indices."""
    return -np.sin(2 * np.pi * a * s / m)


def cos_f(s, a, m):
    """Return basis function for odd indices."""
    return -np.cos(2 * np.pi * a * s / m)


def encode_domain(encoding):
    """Decorate a function with an encoding for its domain.

    Args:
        encoding (dict):
            dictionary for encoding.
    """
    def decorate_func(func):
        @wraps(func)
        def encoded(s, *args, **kwargs):
            return func(encoding[s], *args, **kwargs)
        return encoded
    return decorate_func


def basis_factory(basis_name, site_space):
    """Create a site basis for the given basis name.

    Args:
        basis_name (str):
            Name of the basis.
        site_space (Sequence or OrderedDict):
            Site space over which the basis set is defined.

    Returns:
        SiteBasis
    """
    if isinstance(site_space, OrderedDict):
        species = tuple(site_space.keys())
    else:
        species = tuple(site_space)
    iterator_name = basis_name.capitalize() + 'Iterator'
    basis_funcs = derived_class_factory(iterator_name, BasisIterator, species)
    return SiteBasis(site_space, basis_funcs)
