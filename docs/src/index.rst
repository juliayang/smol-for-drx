:notoc:

.. toctree::
   :maxdepth: 1
   :hidden:

   getting_started
   user_guide/index
   api_reference/index
   citing
   developer_guide/index

=================================
Statistical Mechanics on Lattices
=================================

*Lighthweight but caffeinated Python implementation of computational methods
for statistical mechanical calculations of configurational states in
crystalline material systems.*

.. image:: https://github.com/CederGroupHub/smol/actions/workflows/test.yml/badge.svg
      :alt: Test Status
      :target: https://github.com/CederGroupHub/smol/actions/workflows/test.yml

-------------------------------------------------------------------------------

.. warning::
    **smol** is still under substantial development and may possibly include
    changes that break backwards compatibility for the near future.

**smol** is a minimal implementation of computational methods to calculate
statistical mechanical and thermodynamic properties of crystalline
material systems based on the *cluster expansion* method from alloy theory and
related methods. Although **smol** is intentionally lightweight---in terms of
dependencies and built-in functionality---it has a modular design that closely
follows underlying mathematical formalism and provides useful abstractions to
easily extend existing methods or implement and test new ones. Finally,
although conceived mainly for method development, **smol** can (and is being)
used in production for materials science reasearch applications.

Functionality
=============
**smol** currently includes the following functionality:

- Defining cluster expansion terms for a given disordered structure using a
  variety of available site basis functions with and without explicit
  redundancy.
- Option to include explicit electrostatics using the Ewald summation method.
- Computing correlation vectors for a set of training structures with a variety
  of functionality to inspect the resulting feature matrix.
- Defining cluster expansions for subsequent property prediction.
- Fast evaluation of correlation vectors and differences in correlation vectors
  from local updates in order to quickly compute properties and changes in
  properties for specified supercells.
- Flexible toolset to sample cluster expansions using Monte Carlo with
  Canonical and Semigrand Canonical ensembles using a Metropolis sampler.

**smol** is built on top of `pymatgen <https://pymatgen.org/>`_ so any pre/post
structure analysis can be done seamlessly using the various functionality
supported there.

Citing
======
If you find **smol** useful please cite the following publication,

    Barroso-Luque, L., Yang, J.H., Xie, F., Chen T., Zhong, P. & Ceder, G.
    **smol**: A Python package for cluster expansions and beyond
    (submitted)

Since **smol** is based on **pymatgen**, please also cite this publication,

    Ong, S. P. et al. Python Materials Genomics (pymatgen):
    `A robust, open-source python library for materials analysis
    <https://doi.org/10.1016/j.commatsci.2012.10.028>`_.
    ComputationalMaterials Science 68, 314–319 (2013).

Additionally, several of the functionality included in **smol** is based on
methodology developed by various researchers. Please see the
:doc:`citing page </citing>` for additional refrences.
