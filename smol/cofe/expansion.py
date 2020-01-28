"""
This module implements the ClusterExpansion class, which holds the necessary
attributes to fit a set of orbit functions to a dataset of structures and
a corresponding property (most usually energy).
"""

from __future__ import division
import warnings
import numpy as np
from collections.abc import Sequence
from monty.json import MSONable
from pymatgen import Structure
from smol.cofe.configspace.clusterspace import ClusterSubspace
from smol.cofe.wrangler import StructureWrangler
from smol.cofe.regression.estimator import BaseEstimator, CVXEstimator
from smol.exceptions import NotFittedError


class ClusterExpansion(MSONable):
    """
    Class for the ClusterExpansion proper needs a structurewrangler to supply
    fitting data and an estimator to provide the fitting method.
    This is the class that is used to predict as well.
    (i.e. to use in Monte Carlo and beyond)
    """

    def __init__(self, structurewrangler, estimator=None, ecis=None):
        """
        Represents a cluster expansion. The main methods to use this class are
        the fit and predict

        Args:
            structurewrangler (StructureWrangler):
                A StructureWrangler object to provide the fitting data and
                processing
            max_dielectric (float):
                Constrain the dielectric constant to be positive and below the
                supplied value (note that this is also affected by whether the
                primitive cell is the correct size)
            estimator:
                Estimator or sklearn model. Needs to have a fit and predict
                method, fitted coefficients must be stored in _coeffs
                attribute (usually these are the ECI).
            ecis (array):
                ecis for cluster expansion. This should only be used if the
                expansion was already fitted. Make sure the supplied eci
                correspond to the correlation vector terms (length and order)
        """

        self.wrangler = structurewrangler

        # Expose some functionality directly to cluster expansion
        self.add_data = self.wrangler.add_data

        self.estimator = estimator
        self.ecis = ecis

        if self.estimator is None:
            if self.ecis is None:
                raise AttributeError('No estimator or ECIs were given. '
                                     'One of them needs to be provided')
            self.estimator = BaseEstimator()
            self.estimator.coef_ = self.ecis

    @classmethod
    def from_radii(cls, structure, radii, ltol=0.2, stol=0.1, angle_tol=5,
                   supercell_size='volume', basis='indicator',
                   orthonormal=False, externalterms=None, estimator=None,
                   ecis=None, data=None, verbose=False, weights=None):
        """
        Args:
            structure:
                disordered structure to build a cluster expansion for.
                Typically the primitive cell
            radii:
                dict of {cluster_size: max_radius}. Radii should be strictly
                decreasing. Typically something like {2:5, 3:4}
            ltol, stol, angle_tol, supercell_size: parameters to pass through
                to the StructureMatcher. Structures that don't match to the
                primitive cell under these tolerances won't be included in the
                expansion. Easiest option for supercell_size is usually to use
                a species that has a constant amount per formula unit.
            basis (str):
                a string specifying the site basis functions
            orthonormal (bool):
                wether to enforece an orthonormal basis. From the current
                available bases only the indicator basis is not orthogonal out
                of the box
            externalterms (object):
                any external terms to add to the cluster subspace
                Currently only an EwaldTerm
            estimator:
                Estimator or sklearn model. Needs to have a fit and predict
                method, fitted coefficients must be stored in _coeffs
                attribute (usually these are the ECI).
            ecis (array):
                ecis for cluster expansion. This should only be used if the
                expansion was already fitted. Make sure the supplied eci
                correspond to the correlation vector terms (length and order)
            data (list):
                list of (structure, property) data
            verbose (bool):
                if True then print structures that fail in StructureMatcher
            weights (str, list/tuple or array):
                str specifying type of weights (i.e. 'hull') OR
                list/tuple with two elements (name, kwargs) were name specifies
                the type of weights as above, and kwargs are a dict of
                keyword arguments to obtain the weights OR
                array directly specifying the weights
        Returns:
            ClusterExpansion (not automatically fitted)
        """

        cs = ClusterSubspace.from_radii(structure, radii, ltol, stol,
                                        angle_tol, supercell_size, basis,
                                        orthonormal)
        if externalterms is not None:
            # at some point we should loop through this if more than 1 term
            kwargs = {}
            if isinstance(externalterms, Sequence):
                externalterms, kwargs = externalterms
            cs.add_external_term(externalterms, **kwargs)

        wrangler = StructureWrangler(cs)

        if data is not None:
            wrangler.add_data(data, verbose=verbose, weights=weights)
        elif isinstance(weights, str):
            if weights not in wrangler.get_weights.keys():
                raise AttributeError(f'Weight str provided {weights} is not'
                                     f'valid. Choose one of '
                                     f'{wrangler.weights.keys()}')
            wrangler.weight_type = weights
        if estimator is None and ecis is None:
            estimator = CVXEstimator()

        return cls(wrangler, estimator=estimator, ecis=ecis)

    def fit(self, *args, **kwargs):
        """
        Fits the cluster expansion using the given estimator's fit function
        args, kwargs are the arguments and keyword arguments taken by the
        Estimator.fit function
        """
        A_in = self.wrangler.feature_matrix.copy()
        y_in = self.wrangler.normalized_properties.copy()

        if self.wrangler.weight_type is not None:
            self.estimator.fit(A_in, y_in,
                               self.wrangler.weights.copy(),
                               *args, **kwargs)
        else:
            self.estimator.fit(A_in, y_in, *args, **kwargs)

        try:
            self.ecis = self.estimator.coef_
        except AttributeError:
            warnings.warn(f'The provided estimator does not provide fit '
                          f'coefficients for ECIS: {self.estimator}')
            return

    def predict(self, structures, normalized=False):
        if isinstance(structures, Structure):
            structures = [structures]

        corrs = []
        for structure in structures:
            corr, size = self.wrangler.subspace.corr_from_structure(structure,
                                                                    return_size=True)
            if not normalized:
                corr *= size
            corrs.append(corr)

        return self.estimator.predict(np.array(corrs))

    # TODO change this to  __str__
    def print_ecis(self):
        if self.ecis is None:
            raise NotFittedError('This ClusterExpansion has no ECIs available.'
                                 'If it has not been fitted yet, run'
                                 'ClusterExpansion.fit to do so.'
                                 'Otherwise you may have chosen an estimator'
                                 'that does not provide them:'
                                 f'{self.estimator}.')

        corr = np.zeros(self.wrangler.subspace.n_bit_orderings)
        corr[0] = 1  # zero point cluster
        cluster_std = np.std(self.wrangler.feature_matrix, axis=0)
        for orbit in self.wrangler.subspace.iterorbits():
            print(orbit, len(orbit.bits) - 1, orbit.orb_b_id)
            print('bit    eci    cluster_std    eci*cluster_std')
            for i, bits in enumerate(orbit.bit_combos):
                eci = self.ecis[orbit.orb_b_id + i]
                c_std = cluster_std[orbit.orb_b_id + i]
                print(bits, eci, c_std, eci * c_std)
        print(self.ecis)

    # TODO save the estimator and parameters?
    @classmethod
    def from_dict(cls, d):
        """
        Creates ClusterExpansion from serialized MSONable dict
        """
        return cls(StructureWrangler.from_dict(d['wrangler']), ecis=d['ecis'])

    def as_dict(self):
        """
        Json-serialization dict representation

        Returns:
            MSONable dict
        """

        d = {'@module': self.__class__.__module__,
             '@class': self.__class__.__name__,
             'wrangler': self.wrangler.as_dict(),
             'estimator': self.estimator.__class__.__name__,
             'ecis': self.ecis.tolist()}
        return d
