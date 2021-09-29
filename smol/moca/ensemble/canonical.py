"""
Implementation of a Canonical Ensemble Class.

Used when running Monte Carlo simulations for fixed number of sites and fixed
concentration of species.
"""

__author__ = "Luis Barroso-Luque"


from monty.json import MSONable

from smol.moca.ensemble.base import Ensemble
from smol.moca.processor.base import Processor
from .sublattice import Sublattice


class CanonicalEnsemble(Ensemble, MSONable):
    """Canonical Ensemble class to run Monte Carlo Simulations."""

    valid_mcmc_steps = ('swap',)

    def __init__(self, processor, sublattices=None, all_sublattices=None):
        """Initialize CanonicalEnemble.

        Args:
            processor (Processor):
                A processor that can compute the change in a property given
                a set of flips.
            sublattices (list of Sublattice): optional
                list of Lattice objects representing sites in the processor
                supercell with same site spaces. Only active sublattices.
                Active means to allow multiple species occupy one sublattice.
            all_sublattices (list of Sublattice): optional
                All sublattices, including inactive ones. Needed when in
                some special cases when you want to sub-divide sublattices.
                For example, topotactic delitiation.
        """
        super().__init__(processor, sublattices=sublattices,
                         all_sublattices=all_sublattices)

    @property
    def natural_parameters(self):
        """Get the vector of exponential parameters."""
        return self.processor.coefs

    def compute_feature_vector(self, occupancy):
        """Compute the feature vector for a given occupancy.

        In the canonical case it is just the feature vector from the underlying
        processor.

        Args:
            occupancy (ndarray):
                encoded occupancy string

        Returns:
            ndarray: feature vector
        """
        return self.processor.compute_feature_vector(occupancy)

    def compute_feature_vector_change(self, occupancy, step):
        """Compute the change in the feature vector from a given step.

        Args:
            occupancy (ndarray):
                encoded occupancy string.
            step (list of tuple):
                A sequence of flips as given my the MCMCUsher.propose_step

        Returns:
            ndarray: difference in feature vector
        """
        return self.processor.compute_feature_vector_change(occupancy, step)

    @classmethod
    def from_dict(cls, d):
        """Instantiate a CanonicalEnsemble from dict representation.

        Args:
            d (dict):
                dictionary representation.
        Returns:
            CanonicalEnsemble
        """
        sl_dicts = d.get('sublattices')
        sublattices = ([Sublattice.from_dict(s) for s in sl_dicts] if
                       sl_dicts is not None else None)
        sl_dicts = d.get('all_sublattices')
        all_sublattices = ([Sublattice.from_dict(s) for s in sl_dicts] if
                           sl_dicts is not None else None)

        return cls(Processor.from_dict(d['processor']),
                   sublattices=sublattices,
                   all_sublattices=all_sublattices)
