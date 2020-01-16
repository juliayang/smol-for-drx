from __future__ import division
import numpy as np
from monty.json import MSONable
from pymatgen.util.coord import is_coord_subset
from pymatgen import Lattice

from ..utils import SITE_TOL, _repr


class Cluster(MSONable):
    """
    An undecorated (no occupancies) cluster
    """

    def __init__(self, sites, lattice):
        """
        Args:
            sites (list):
                list of frac coords for the sites
            lattice (pymatgen.Lattice):
                pymatgen Lattice object
        """
        sites = np.array(sites)
        centroid = np.average(sites, axis=0)
        shift = np.floor(centroid)
        self.centroid = centroid - shift
        self.sites = sites - shift
        self.lattice = lattice
        self.c_id = None

    @staticmethod
    def from_sites(sites):
        return Cluster([s.frac_coords for s in sites], sites[0].lattice)

    @property
    def size(self):
        return len(self.sites)

    @property
    def radius(self):
        coords = self.lattice.get_cartesian_coords(self.sites)
        all_d2 = np.sum((coords[None, :, :] - coords[:, None, :]) ** 2, axis=-1)
        return np.max(all_d2) ** 0.5

    def assign_ids(self, c_id):
        """
        Method to recursively assign ids to clusters after initialization.
        """
        self.c_id = c_id
        return c_id + 1

    def __eq__(self, other):
        try:
            if self.sites.shape != other.sites.shape:
                return False
            other_sites = other.sites + np.round(self.centroid - other.centroid)
            return is_coord_subset(self.sites, other_sites, atol=SITE_TOL)
        except AttributeError as e:
            print(str(e))
            raise NotImplementedError

    def __neq__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        points = str(np.round(self.sites, 2)).replace("\n", " ").ljust(len(self.sites) * 21)
        return f'[Cluster] id: {self.c_id}, Radius: {self.radius:<4.3}, Points: {points}, ' \
               f'Centroid: {np.round(self.centroid,2)}'

    def __repr__(self):
        return _repr(self, c_id=self.c_id, radius=self.radius, centroid=self.centroid, lattice=self.lattice)

    @classmethod
    def from_dict(cls, d):
        """
        Creates a cluster from serialized dict
        """
        return cls(d['sites'], Lattice.from_dict(d['lattice']))

    def as_dict(self):
        """
        Json-serialization dict representation

        Returns:
            MSONable dict
        """
        d = {"@module": self.__class__.__module__,
             "@class": self.__class__.__name__,
             "lattice": self.lattice.as_dict(),
             "sites": self.sites.tolist()}
        return d