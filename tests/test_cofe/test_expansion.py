import unittest
import warnings
import numpy as np
from ..data import lno_prim, lno_data
from smol.cofe import StructureWrangler, ClusterSubspace, ClusterExpansion
from smol.cofe.configspace import EwaldTerm
from smol.cofe.regression import constrain_dielectric
from smol.cofe.regression.estimator import CVXEstimator, BaseEstimator

class TestClusterExpansion(unittest.TestCase):
    def setUp(self) -> None:
        self.cs = ClusterSubspace.from_radii(lno_prim, {2: 5, 3: 4.1}, ltol=0.15, stol=0.2,
                                             angle_tol=5, supercell_size='O2-')
        self.sw = StructureWrangler(self.cs)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')  #  Supress warnings for structures not mapped to prim
            self.sw.add_data(lno_data)

    def test_cvxestimator(self):
        ce = ClusterExpansion(self.sw, estimator=CVXEstimator())
        self.assertRaises(AttributeError, ce.predict, self.sw.structures[:10])
        ce.fit(mu=5)
        self.assertIsNotNone(ce.ecis)
        self.assertEqual(len(ce.ecis), self.cs.n_bit_orderings)
        self.sw.set_weights('hull')
        ce.fit()

    def test_sklearn(self):
        try:
            from sklearn.linear_model import Ridge, LassoCV
        except ImportError:
            return

        ce = ClusterExpansion(self.sw, estimator=Ridge())
        self.assertRaises(AttributeError, ce.predict, self.sw.structures[:10])
        ce.fit()
        self.assertIsNotNone(ce.ecis)
        self.assertEqual(len(ce.ecis), self.cs.n_bit_orderings)
        ce.estimator = LassoCV()
        ce.fit()
        self.assertIsNotNone(ce.ecis)
        self.assertEqual(len(ce.ecis), self.cs.n_bit_orderings)

    def test_numpy(self):
        estimator = BaseEstimator()
        estimator._solve = lambda X, y: np.linalg.lstsq(X, y)[0]
        ce = ClusterExpansion(self.sw, estimator=estimator)
        self.assertRaises(AttributeError, ce.predict, self.sw.structures[:10])
        ce.fit()
        self.assertIsNotNone(ce.ecis)
        self.assertEqual(len(ce.ecis), self.cs.n_bit_orderings)

    def test_no_estimator(self):
        ecis = np.ones((self.cs.n_bit_orderings))
        ce = ClusterExpansion(self.sw, ecis=ecis)
        structs = self.sw.structures[:10]
        p = np.array([sum(self.cs.corr_from_structure(s)) for s in structs])
        self.assertTrue(np.allclose(ce.predict(structs, normalized=True), p))

    def test_constrain_dielectric(self):
        self.cs.add_external_term(EwaldTerm)
        ce = ClusterExpansion(self.sw, estimator=CVXEstimator())
        ce.fit()
        constrain_dielectric(ce, 15)
        self.assertEqual(ce.ecis[-1], 1/15)

    def test_msonable(self):
        ecis = np.ones((self.cs.n_bit_orderings))
        ce = ClusterExpansion(self.sw, ecis=ecis)
        ce.print_ecis()
        d = ce.as_dict()
        ce1 = ClusterExpansion.from_dict(d)
        self.assertTrue(np.array_equal(ce.ecis, ce1.ecis))
        self.assertIsInstance(ce.wrangler, StructureWrangler)
        self.assertIsInstance(ce.estimator, BaseEstimator)