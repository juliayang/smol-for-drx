"""Functions to filter data in a StructureWrangler."""

from collections import defaultdict

import numpy as np
from pymatgen.analysis.phase_diagram import PDEntry, PhaseDiagram
from pymatgen.core import Composition

from smol.cofe.extern import EwaldTerm

__author__ = "Luis Barroso-Luque, William Davidson Richard"

from smol.constants import kB


def unique_corr_vector_indices(
    wrangler, property_key, filter_by="min", cutoffs=None, return_compliment=False
):
    """Return index set of structures with unique correlation vectors.

    Keep structures with the min or max value of the given property.
    Note correlation vectors exclude external terms such that even if the
    external term is different for the structure but all correlations are
    the same the structures will be considered duplicates.

    Args:
        wrangler (StructureWrangler):
            A StructureWrangler containing data to be filtered.
        property_key (str):
            Name of property to consider when returning structure indices
            for the feature matrix with duplicate corr vectors removed.
        filter_by (str)
            The criteria for the property value to keep. Options are min
            or max.
        cutoffs (dict): optional
            dictionary with cluster diameter cutoffs for correlation
            functions to consider in correlation vectors.
        return_compliment (bool): optional
            If True will return the compliment of the unique indices
    Returns:
        indices, compliment
    """
    if filter_by not in ("max", "min"):
        raise ValueError(f"Filtering by {filter_by} is not an option.")

    choose_val = np.argmin if filter_by == "min" else np.argmax

    property_vector = wrangler.get_property_vector(property_key)
    dupe_inds = wrangler.get_duplicate_corr_indices(cutoffs=cutoffs)
    indices = {inds[choose_val(property_vector[inds])] for inds in dupe_inds}
    duplicates = {i for inds in dupe_inds for i in inds} - indices
    indices = list(set(range(wrangler.num_structures)) - duplicates)

    if return_compliment:
        return indices, list(duplicates)
    return indices


def max_ewald_energy_indices(wrangler, max_relative_energy, return_compliment=False):
    """Return index set of structures by electrostatic interaction energy.

    Filter the input structures to only use those with low electrostatic
    energies (no large charge separation in cell). This energy is
    referenced to the lowest value at that composition. Note that this is
    before the division by the relative dielectric constant and is per
    primitive cell in the cluster expansion -- 1.5 eV/atom seems to be a
    reasonable value for dielectric constants around 10.

    Args:
        wrangler (StructureWrangler):
            A StructureWrangler containing data to be filtered.
        max_relative_energy (float):
            Ewald threshold. The maximum Ewald energy relative to minumum
            energy at composition of structure (normalized by prim).
        return_compliment (bool): optional
            If True will return the compliment of the unique indices.
    Returns:
        indices, compliment
    """
    ewald_energy = None
    for term in wrangler.cluster_subspace.external_terms:
        if isinstance(term, EwaldTerm):
            ewald_energy = [i["features"][-1] for i in wrangler.data_items]
    if ewald_energy is None:
        ewald_energy = []
        for item in wrangler.data_items:
            struct = item["structure"]
            matrix = item["scmatrix"]
            mapp = item["mapping"]
            occu = wrangler.cluster_subspace.occupancy_from_structure(
                struct, encode=True, scmatrix=matrix, site_mapping=mapp
            )

            supercell = wrangler.cluster_subspace.structure.copy()
            supercell.make_supercell(matrix)
            size = wrangler.cluster_subspace.num_prims_from_matrix(matrix)
            term = EwaldTerm().value_from_occupancy(occu, supercell) / size
            ewald_energy.append(term)

    min_energy_by_comp = defaultdict(lambda: np.inf)
    for energy, item in zip(ewald_energy, wrangler.data_items):
        comp = item["structure"].composition.reduced_composition
        if energy < min_energy_by_comp[comp]:
            min_energy_by_comp[comp] = energy

    indices, compliment = [], []
    for i, (energy, item) in enumerate(zip(ewald_energy, wrangler.data_items)):
        min_energy = min_energy_by_comp[
            item["structure"].composition.reduced_composition
        ]
        rel_energy = energy - min_energy
        if rel_energy < max_relative_energy:
            indices.append(i)
        else:
            compliment.append(i)

    if return_compliment:
        return indices, compliment
    return indices


def weights_energy_above_composition(structures, energies, temperature=2000):
    """Compute weights for energy above the minimum reduced composition energy.

    Args:
        structures (list):
            list of pymatgen.Structures
        energies (ndarray):
            energies of corresponding structures.
        temperature (float):
            temperature to used in boltzmann weight

    Returns: weights for each structure.
        array
    """
    e_above_comp = _energies_above_composition(structures, energies)
    return np.exp(-e_above_comp / (kB * temperature))


def weights_energy_above_hull(structures, energies, cs_structure, temperature=2000):
    """Compute weights for structure energy above the hull of given structures.

    Args:
        structures (list):
            list of pymatgen.Structures
        energies (ndarray):
            energies of corresponding structures.
        cs_structure (Structure):
            The pymatgen.Structure used to define the cluster subspace
        temperature (float):
            temperature to used in boltzmann weight.

    Returns: weights for each structure.
        array
    """
    e_above_hull = _energies_above_hull(structures, energies, cs_structure)
    return np.exp(-e_above_hull / (kB * temperature))


def _energies_above_hull(structures, energies, ce_structure):
    """Compute energies above hull.

    Hull is constructed from phase diagram of the given structures.
    """
    phase_diagram = _pd(structures, energies, ce_structure)
    e_above_hull = []
    for structure, energy in zip(structures, energies):
        entry = PDEntry(structure.composition.element_composition, energy)
        e_above_hull.append(phase_diagram.get_e_above_hull(entry))
    return np.array(e_above_hull)


def _pd(structures, energies, cs_structure):
    """Generate a phase diagram with the structures and energies."""
    entries = []

    for structure, energy in zip(structures, energies):
        entries.append(PDEntry(structure.composition.element_composition, energy))

    max_e = max(entries, key=lambda e: e.energy_per_atom).energy_per_atom
    max_e += 1000
    for element in cs_structure.composition.keys():
        entry = PDEntry(Composition({element: 1}).element_composition, max_e)
        entries.append(entry)

    return PhaseDiagram(entries)


def _energies_above_composition(structures, energies):
    """Compute structure energies above reduced composition."""
    min_e = defaultdict(lambda: np.inf)
    for structure, energy in zip(structures, energies):
        comp = structure.composition.reduced_composition
        if energy / len(structure) < min_e[comp]:
            min_e[comp] = energy / len(structure)
    e_above = []
    for structure, energy in zip(structures, energies):
        comp = structure.composition.reduced_composition
        e_above.append(energy / len(structure) - min_e[comp])
    return np.array(e_above)
