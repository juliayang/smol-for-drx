"""Test smol.moca.utils.occu_utils."""
import pytest

from smol.moca.utils.occu_utils import *
import numpy as np
import numpy.testing as npt
import itertools

from tests.utils import gen_random_occupancy


@pytest.fixture(scope="module")
def sublattices(ensemble):
    sublattices = ensemble.sublattices
    all_sites = [site for sublatt in sublattices for site in sublatt.sites]
    sites_to_restrict = np.random.choice(all_sites, size=len(all_sites) // 2, replace=False)
    ensemble.restrict_sites(sites_to_restrict)
    return ensemble.sublattices


@pytest.fixture(scope="module")
def bits(sublattices):
    return [sl.species for sl in sublattices]


@pytest.fixture(scope="module")
def dim_ids(bits):
    return get_dim_ids_by_sublattice(bits)


@pytest.fixture(scope="module")
def dim_ids_table_active(sublattices):
    return get_dim_ids_table(sublattices, active_only=True)


@pytest.fixture(scope="module")
def dim_ids_table_all(sublattices):
    return get_dim_ids_table(sublattices, active_only=False)


def test_dim_ids(dim_ids):
    d = sum(len(species) for species in dim_ids)
    for sl_id, dim_id in enumerate(dim_ids):
        assert len(dim_id) == bits[sl_id]
    npt.assert_array_equal(np.arange(d, type=int),
                           list(itertools.chain(*dim_ids)))


def test_table(sublattices, dim_ids, dim_ids_table_active, dim_ids_table_all):
    # Assert include all sites.
    n_sites = sum(sublatt.sites for sublatt in sublattices)
    n_codes = max(max(sublatt.encoding) for sublatt in sublattices) + 1
    npt.assert_array_equal(np.sort([site for sublatt in sublattices
                                    for site in sublatt.sites]),
                           np.arange(n_sites, dtype=int))
    assert dim_ids_table_all.shape == (n_sites, n_codes)
    assert dim_ids_table_active.shape == (n_sites, n_codes)
    for sublatt, dim_ids_sl in zip(sublattices, dim_ids):
        npt.assert_array_equal(dim_ids_table_all[sublatt.sites[:, None],
                                                 sublatt.encoding],
                               np.array(dim_ids_sl, dtype=int)[None, :])
        if not sublatt.is_active:
            npt.assert_array_equal(dim_ids_table_all[sublatt.sites, :], -1)
        npt.assert_array_equal(dim_ids_table_active[sublatt.active_sites
                                                    [:, None],
                                                    sublatt.encoding],
                               np.array(dim_ids_sl, dtype=int)[None, :])
        npt.assert_array_equal(dim_ids_table_active
                               [sublatt.restricted_sites, :],
                               -1)


def test_occu_conversion(sublattices,
                         dim_ids_table_all, dim_ids_table_active):
    for _ in range(10):
        occu = gen_random_occupancy(sublattices)
        list_all = occu_to_species_list(occu, dim_ids_table_all)
        list_active = occu_to_species_list(occu, dim_ids_table_active)
        n_all = occu_to_species_n(occu, dim_ids_table_all)
        n_active = occu_to_species_n(occu, dim_ids_table_active)
        npt.assert_array_equal(n_all,
                               [len(sites) for sites in list_all])
        npt.assert_array_equal(n_active,
                               [len(sites) for sites in list_active])
        dim_id = 0
        for sublatt in sublattices:
            for code in sublatt.encoding:
                sites_all = list_all[dim_id]
                sites_active = list_active[dim_id]
                assert np.all(site in sublatt.active_sites
                              for site in sites_active)
                npt.assert_array_equal(occu[sites_all], code)
                npt.assert_array_equal(occu[sites_active], code)
                if not sublatt.is_active:
                    assert len(sites_active) == 0
                dim_id += 1


def test_delta_n(sublattices, dim_ids_table_active):
    # Test a few good steps.
    occu = gen_random_occupancy(sublattices)
    all_sites = np.arange(len(occu), dtype=int)
    activeness = np.any(dim_ids_table_active >= 0, axis=-1)
    # An active site must have at least 2 species allowed.
    assert np.all(np.sum(dim_ids_table_active[all_sites[activeness], :]
                         >= 0, axis=-1) >= 2)
    active_sites = all_sites[activeness]
    for _ in range(10):
        site = np.random.choice(active_sites)
        code_ori = occu[site]
        table_site = dim_ids_table_active[site, :]
        code_nex = np.random.choice(set(np.arange(len(table_site), dtype=int)
                                    [table_site >= 0]) - {code_ori})
        step1 = [(site, code_nex)]
        step2 = [(site, code_nex), (site, code_ori)]
        step3 = [(site, code_nex), (site, code_nex)]
        dim_id_ori = dim_ids_table_active[site, code_ori]
        dim_id_nex = dim_ids_table_active[site, code_nex]

        dn1 = delta_n_from_step(occu, step1, dim_ids_table_active)
        dn1_std = np.zeros(len(dn1))
        dn1_std[dim_id_nex] = 1
        dn1_std[dim_id_ori] = -1
        dn2 = delta_n_from_step(occu, step2, dim_ids_table_active)
        dn2_std = np.zeros(len(dn2))
        dn3 = delta_n_from_step(occu, step3, dim_ids_table_active)
        npt.assert_array_equal(dn1, dn1_std)
        npt.assert_array_equal(dn2, dn2_std)
        npt.assert_array_equal(dn3, dn1_std)

    # Test bad steps.
    site = np.random.choice(active_sites)
    table_site = dim_ids_table_active[site, :]
    bad_codes = np.arange(len(table_site), dtype=int)[table_site < 0]
    if len(bad_codes) > 0:
        bad_code = np.random.choice(bad_codes)
        bad_step = [(site, bad_code)]
        with pytest.raises(ValueError):
            _ = delta_n_from_step(occu, bad_step, dim_ids_table_active)
    inactive_sites = np.setdiff1d(all_sites, active_sites)
    bad_site = np.random.choice(inactive_sites)
    rand_code = np.random.choice(np.arange(len(table_site), dtype=int))
    bad_step = [(bad_site, rand_code)]
    with pytest.raises(ValueError):
        _ = delta_n_from_step(occu, bad_step, dim_ids_table_active)