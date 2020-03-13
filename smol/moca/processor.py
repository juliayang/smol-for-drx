"""
Implementation of a processor for a fixed size Super Cell optimized to compute
correlation vectors and local changes in correlation vectors. This class allows
the use a cluster expansion hamiltonian to run Monte Carlo based simulations.
"""

import numpy as np
from collections import defaultdict
from monty.json import MSONable
from pymatgen import Structure, PeriodicSite
from smol.cofe import ClusterExpansion
from smol.cofe.configspace.utils import get_bits
from src.ce_utils import corr_from_occupancy, delta_corr_single_flip


class ClusterExpansionProcessor(MSONable):
    """
    A processor allows an ensemble class to to generate Markov processes (chain
    really) for sampling thermodynamic properties from a cluster expansion
    Hamiltonian.
    Think of this as fixed size supercell optimized to calculate correlation
    vectors and local changes to correlation vectors from site flips.
    """

    def __init__(self, cluster_expansion, supercell_matrix):

        # the only reason to keep the CE is for the MSONable from_dict
        self.cluster_expansion = cluster_expansion

        self.ecis = cluster_expansion.ecis.copy()
        self.subspace = cluster_expansion.subspace
        self.structure = self.subspace.structure.copy()
        self.structure.make_supercell(supercell_matrix)
        self.supercell_matrix = supercell_matrix

        # this can be used (maybe should) to check if a flip is valid
        expansion_bits = get_bits(cluster_expansion.expansion_structure)
        self.unique_bits = tuple(set(tuple(bits)for bits in expansion_bits))

        self.bits = get_bits(self.structure)
        self.size = self.subspace.num_prims_from_matrix(supercell_matrix)
        self.n_orbit_functions = self.subspace.n_bit_orderings
        orbit_inds = self.subspace.supercell_orbit_mappings(supercell_matrix)

        # List of orbit information and supercell site indices to compute corr
        self.orbit_list = []
        # Dictionary of orbits by site index and information
        # necessary to compute local changes in correlation vectors from flips
        self.orbits_by_sites = defaultdict(list)
        # Store the orbits grouped by site index in the structure,
        # to be used by delta_corr. We also store a reduced index array,
        # where only the rows with the site index are stored. The ratio is
        # needed because the correlations are averages over the full inds
        # array.
        for orbit, inds in orbit_inds:
            self.orbit_list.append((orbit.bit_id, orbit.bit_combos,
                                    orbit.bases_array, inds))
            for site_ind in np.unique(inds):
                in_inds = np.any(inds == site_ind, axis=-1)
                ratio = len(inds) / np.sum(in_inds)
                self.orbits_by_sites[site_ind].append((orbit.bit_id, ratio,
                                                       orbit.bit_combos,
                                                       orbit.bases_array,
                                                       inds[in_inds]))

    def compute_property(self, occu):
        """
        Computes the total value of the property corresponding to the CE
        for the given occupancy vector

        Args:
            occu (array):
                encoded occupancy array
        Returns: predicted property
            float
        """
        return np.dot(self.compute_correlation(occu), self.ecis) * self.size

    def compute_property_change(self, occu, flips):
        """
        Compute change in property from a set of flips
        Args:
            occu (array):
                encoded occupancy array
            flips (list):
                list of tuples for (index of site, specie code to set)

        Returns:
            float
        """
        return np.dot(self.delta_corr(flips, occu), self.ecis) * self.size

    def compute_correlation(self, occu):
        """
        Computes the correlation vector for a given occupancy vector.
        Each entry in the correlation vector corresponds to a particular
        symmetrically distinct bit ordering.

        Args:
            occu (array):
                encoded occupation vector

        Returns: Correlation vector
            array
        """
        return corr_from_occupancy(occu, self.n_orbit_functions,
                                   self.orbit_list)

    def occupancy_from_structure(self, structure):
        """
        Gets the occupancy vector for a given structure. The structure must
        strictly be a supercell of the prim according to the processor's
        supercell matrix

        Args:
            structure (Structure):
                A pymatgen structure (related to the cluster-expansion prim
                by the supercell matrix passed to the processor)
        Returns: encoded occupancy vector
            list
        """
        occu = self.subspace.occupancy_from_structure(structure,
                                                      self.supercell_matrix)
        return self.encode_occupancy(occu)

    def structure_from_occupancy(self, occu):
        """
        Get pymatgen.Structure from an occupancy vector

        Args:
            occu (array):
                encoded occupancy array

        Returns:
            Structure
        """
        occu = self.decode_occupancy(occu)
        sites = []
        for sp, s in zip(occu, self.structure):
            if sp != 'Vacancy':
                site = PeriodicSite(sp, s.frac_coords, self.structure.lattice)
                sites.append(site)
        return Structure.from_sites(sites)

    def encode_occupancy(self, occu):
        """
        Encode occupancy vector of species str to ints.
        """
        ec_occu = np.array([bit.index(sp) for bit, sp in zip(self.bits, occu)])
        return ec_occu

    def decode_occupancy(self, enc_occu):
        """
        Decode encoded occupancy vector of int to species str
        """
        occu = [bit[i] for i, bit in zip(enc_occu, self.bits)]
        return occu

    def delta_corr(self, flips, occu, debug=False):
        occu_i = occu.copy()
        delta_corr = np.zeros(self.n_orbit_functions)
        for f in flips:
            occu_f = occu_i.copy()
            occu_f[f[0]] = f[1]
            orbits = self.orbits_by_sites[f[0]]
            delta_corr += delta_corr_single_flip(occu_f, occu_i,
                                                 self.n_orbit_functions,
                                                 orbits)
            occu_i = occu_f

        return delta_corr

    @classmethod
    def from_dict(cls, d):
        """
        Creates CEProcessor from serialized MSONable dict
        """
        return cls(ClusterExpansion.from_dict(d['cluster_expansion']),
                   np.array(d['supercell_matrix']))

    def as_dict(self) -> dict:
        """
        Json-serialization dict representation

        Returns:
            MSONable dict
        """
        d = {'@module': self.__class__.__module__,
             '@class': self.__class__.__name__,
             'cluster_expansion': self.cluster_expansion.as_dict(),
             'supercell_matrix': self.supercell_matrix.tolist()}
        return d