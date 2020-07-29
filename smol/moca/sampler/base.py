"""Implementation of base sampler classes.

A sampler essentially is an implementation of the MCMC algorithm that is used
by the corresponding ensemble to generate Monte Carlo samples.
"""

__author__ = "Luis Barroso-Luque"

from abc import ABC, abstractmethod
import random
from warnings import warn
import numpy as np

from smol.moca.container import SampleContainer


class Sampler(ABC):
    """Abtract base class for sampler.

    A sampler is used to implement a specific MCMC algorithm used to sample
    the ensemble classes.
    """

    def __init__(self, ensemble, usher, num_walkers=1, container=None,
                 seed=None):
        """Initialize BaseSampler.

        Args:
            ensemble (Ensemble):
                an Ensemble instance to sample from.
            usher (MCUsher)
                MC Usher to suggest MCMC steps.
            num_walkers (int):
                Number of walkers used to generate chain. Default is 1
            container (SampleContainer)
                A containter to store samples. If given num_walkers is taken
                from the container.
            seed (int): optional
                seed for random number generator.
        """
        # Set and save the seed for random. This allows reproducible results.
        self._ensemble = ensemble
        self._usher = usher
        if container is None:
            ensemble_metadata = {'name': type(ensemble).__name__}
            ensemble_metadata.update(ensemble.thermo_boundaries)
            container = SampleContainer(ensemble.temperature,
                                        ensemble.system_size,
                                        ensemble.sublattices,
                                        ensemble.natural_parameters,
                                        ensemble_metadata, num_walkers)
        self._container = container

        if seed is None:
            seed = random.randint(1, 1E24)

        self.__seed = seed
        random.seed(seed)

    @property
    def ensemble(self):
        """Get the underlying ensemble."""
        return self._ensemble

    @property
    def seed(self):
        """Seed for the random number generator."""
        return self.__seed
    
    @seed.setter
    def seed(self, seed):
        """Set the seed for the PRNG."""
        random.seed(seed)
        self.__seed = seed

    @property
    def samples(self):
        return self._container

    @abstractmethod
    def _attempt_step(self, occupancy):
        """Attempts a MC step.

        Returns the next state in the chain and if the attempted step was
        successful.

        Args:
            occupancy (ndarray):
                encoded occupancy.

        Returns:
            tuple: (acceptance, occupancy, features, enthalpy)
        """
        return tuple()

    def sample(self, nsteps, initial_occupancies, thin_by=1):
        """Generate samples

        Yield a sample state every thin_by iterations. A state is give by
        a tuple of (occupanices, feature_blob, enthalpies)

        Args:
            nsteps (int):
                Number of iterations to run.
            initial_occupancies (ndarray):
                array of occupancies
            thin_by (int): optional
                Number to thin iterations by and provide samples.

        Yields:
            tuple: accepted, occupancies, feature_blob, enthalpies
        """
        occupancies = initial_occupancies.copy()
        if initial_occupancies.shape != self.samples.shape:
            if len(initial_occupancies.shape) == 1:
                occupancies = np.reshape(occupancies, (1, len(occupancies)))
            else:
                raise AttributeError('The given initial occcupancies have '
                                     'incompompatible dimensions. Shape should'
                                     f' be {self.samples.shape}')
        if nsteps % thin_by != 0:
            warn(f'The number of steps {nsteps} is not a multiple of thin_by '
                 f' {thin_by}. The last {nsteps % thin_by} will be ignored.',
                 category=RuntimeWarning)
        # TODO check that initial states are independent if num_walkers > 1

        # allocate arrays for states
        occupancies = np.ascontiguousarray(occupancies, dtype=int)
        accepted = np.zeros(occupancies.shape[0], dtype=int)
        enthalpies = np.empty(occupancies.shape[0])
        feature_blob = np.empty((occupancies.shape[0],
                                len(self.ensemble.natural_parameters)))

        for _ in range(nsteps // thin_by):
            for _ in range(thin_by):
                for i, (accept, occupancy, features, enthalpy) in \
                  enumerate(map(self._attempt_step, occupancies)):
                    accepted[i] += accept
                    occupancies[i] = occupancy
                    feature_blob[i] = features
                    enthalpies[i] = enthalpy
            # yield copies
            yield (accepted.copy(), occupancies.copy(), feature_blob.copy(),
                   enthalpies.copy())

    # TODO add progress option and streaming
    def run(self, nsteps, initial_occupancies=None, thin_by=1):
        """Run an MCMC sampling simulations.

        Args:
            nsteps (int):
                number of total MC steps.
            initial_occupancies (ndarray):
                array of occupancies. If None, the last sample will be taken.
            thin_by (int): optional
                the amount to thin by for saving samples.
        """
        if initial_occupancies is None:
            try:
                initial_occupancies = self.samples.get_occupancy_chain()[-1]
            except IndexError:
                raise RuntimeError('There are no saved samples to obtain the '
                                   'initial occupancies. These must be '
                                   'provided.')

        for result in self.sample(nsteps, initial_occupancies,
                                  thin_by=thin_by):
            self.samples.save_sample(*result)
