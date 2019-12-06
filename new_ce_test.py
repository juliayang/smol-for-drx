from pymatgen.io.cif import CifParser
from pymatgen.core.structure import Structure
import numpy as np
from sklearn.linear_model import ElasticNetCV, LassoCV, Ridge, LinearRegression, BayesianRidge, ARDRegression
from smol.cofe import ClusterSubspace, StructureWrangler, ClusterExpansion, CVXEstimator
from smol.cofe.utils import StructureMatchError
from smol.cofe.configspace import EwaldTerm

import json

# Load and prep prim structure
prim = CifParser('/home/lbluque/Develop/daniil_CEMC_workshop/lno_prim.cif')
prim = prim.get_structures()[0]

# Create new ClusterSubspace :)
cs = ClusterSubspace.from_radii(structure=prim,
                                 radii={2: 5, 3: 4.1},
                                 ltol=0.15, stol=0.2, angle_tol=5,
                                 supercell_size='O2-',
                                 basis='legendress',
                                 orthonormal=False)

cs.add_external_term(EwaldTerm, use_inv_r=False, eta=None)

print('Here is the cluster subspace object: \n', cs)


# Open and clean fitting data
with open('/home/lbluque/Develop/daniil_CEMC_workshop/lno_fitting_data.json', 'r') as fin: calc_data = json.loads(fin.read())

valid_structs = [] 
for calc_i, calc in enumerate(calc_data):
    struct = Structure.from_dict(calc['s'])  
    valid_structs.append((struct, calc['toten']))
    #print('{}/{}'.format(calc_i, len(calc_data))) 
    continue
    try: 
        struct = Structure.from_dict(calc['s']) 
        cs.corr_from_structure(struct) 
        valid_structs.append((struct, calc['toten']))
    except StructureMatchError:
        continue 
        #print("\tToo far off lattice, throwing out.") 
    except AttributeError:
    	continue
    
 
print("{}/{} structures map to the lattice".format(len(valid_structs), len(calc_data))) 

print('Also here is a random corr_vector:\n', cs.corr_from_structure(valid_structs[10][0]))

# Create the data wrangler.
sw = StructureWrangler(cs, [(struct, e) for struct, e in valid_structs])
sw.filter_by_ewald(3)

# Create Estimator
#est = CVXEstimator()
est = LinearRegression(fit_intercept=False) 
#est = ElasticNetCV(fit_intercept=False, max_iter=5000, selection='random', tol=1E-4, eps=1E-7)
print('Estimator: ', est)


# Create a ClusterExpansion Object
ce = ClusterExpansion(sw, est, max_dielectric=100)
ce.fit()

err = ce.predict(sw.structures, normalized=True) - sw.normalized_properties
rmse = np.average(err**2)**0.5

struct = sw.structures[0]
#x = np.linalg.lstsq(sw.feature_matrix, sw.normalized_properties)[0]
#rmse = np.average((np.dot(sw.feature_matrix,x)-sw.normalized_properties)**2)**0.5
#print(f'NP RMSE: {rmse}')

print(f"ECIS: {ce.ecis}")
print(f"RMSE: {rmse} eV/prim")
print(f"Number non zero ECIs: {len([eci for eci in ce.ecis if np.abs(eci) > 1e-3])}") 
