import pandas as pd
import random as rand

import numpy as np

from numbers import Real
from numbers import Number

from functools import reduce
from functools import singledispatch

from plio.io import io_spectral_profiler


from . import _index as _idx

from ..transform.continuum import lincorr

from libpysat.utils.utils import linear_correction
from libpysat.utils.utils import method_singledispatch




class Spectra(pd.DataFrame):
    """
    A pandas derived DataFrame used to store spectral and hyper-spectral observations.

    attributes
    ----------

    wavelengths : pandas.Float64Index
                  The wavelengths store as a pandas index

    get : PandasLocIndexer
          Indexing object, maps wavelengths to indices enabling access a tolerance for
          floating point labels.

    ----------
    """

    # attributes that carry over on operations
    _metadata = ['_get', '_iget', 'wavelengths', 'metadata']


    def __init__(self, *args, wavelengths = [], metadata = [], tolerance=0, **kwargs):
        super(_Spectra_DataFrame, self).__init__(*args, **kwargs)

        get_name = self.loc.name
        iget_name = self.iloc.name
        self._iget = _idx.SpectrumiLocIndexer(name=iget_name, obj=self)
        self._get = _idx.SpectrumLocIndexer(name=get_name, obj=self)

        self._get._tolerance = tolerance
        self.wavelengths = pd.Float64Index(wavelengths)

        if metadata:
            self.metadata = pd.Index(metadata)
        else:
            self.metadata = self.columns.difference(self.wavelengths)


    @property
    def _constructor_sliced(self):
        """
        Returns constructor used when dataframe dimension decreases (i.e. goes from a dataframe
        to a series).
        """
        return Spectrum


    @property
    def _constructor(self):
        """
        Returns constructor used when creating copies (i.e. when operations are run on the dataframe).
        """
        return _Spectra_DataFrame


    @classmethod
    def from_m3(cls, path_to_file, tolerance=2):
        """
        Generate DataFrame from spectral profiler data.

        parameters
        ----------
        f : str
            file path to spectral profiler file

        tolerance : Real
                    Tolerance for floating point index
        """

        wavelengths, _, ds = io_moon_minerology_mapper.openm3(path_to_file)

        m3_array = ds.ReadAsArray().swapaxes(0, 2)
        m3_array = np.reshape(m3_array, (-1, m3_array.shape[-1]), order = "A")

        coords = [(i%ds.RasterXSize, i//ds.RasterXSize) for i in range(ds.RasterXSize * ds.RasterYSize)]
        index = pd.MultiIndex.from_tuples(coords, names = ['x', 'y'])
        m3_df = pd.DataFrame(data = m3_array, columns = wavelengths, index = index)

        meta = ds.GetMetadata_Dict()
        metadata = meta.keys()
        meta_df = pd.DataFrame(meta, index = index)

        spectra_df = m3_df.merge(meta_df, left_index = True, right_index = True)
        spectra_df.sort_index(inplace = True)
        return cls(spectra_df, wavelengths, metadata, tolerance=tolerance)


    def linear_correction(self):
        """
        apply linear correction to all spectra
        """
        wavelengths = self.wavelengths.__array__()
        bands = tuple([0, len(wavelengths)-1])

        def lincorr(row):
            """
            Should be rewritten to be more apply friendly
            """
            corr, y = linear_correction(bands, row[wavelengths].__array__(), wavelengths)
            return Spectrum(corr, index=wavelengths)

        data = self.apply(lincorr, axis=1)
        return Spectra(data, wavelengths=self.wavelengths, tolerance = self.tolerance)


    def __getitem__(self, key):
        """
        overrides ndarray's __getitem__ to use .get's floating point tolerance for
        floating point indexes.

        parameters
        ----------
        key : object
              the column labels to access on

        """
        if isinstance(self.index, pd.MultiIndex):
            return self.get[:,:,key]
        else:
             return self.get[:,key]


    @classmethod
    def from_spectral_profiler(cls, f, tolerance=1):
        """
        Generate DataFrame from spectral profiler data.

        parameters
        ----------
        f : str
            file path to spectral profiler file

        tolerance : Real
                    Tolerance for floating point index
        """
        geo_data = io_spectral_profiler.Spectral_Profiler(f)
        meta = geo_data.ancillary_data

        df = geo_data.spectra.to_frame().unstack(level=1)
        df = df.transpose()
        df = df.swaplevel(0,1)

        df.index.names = ['minor', 'id']
        meta.index.name = 'id'

        wavelengths = df.columns

        df = df.reset_index().merge(meta.reset_index(), on='id')
        df = df.set_index(['minor', 'id'], drop=True)

        return cls(df, wavelengths=wavelengths, tolerance=tolerance)


    @property
    def get(self):
        return self._get


    @property
    def iget(self):
        return self._iget


    @property
    def meta(self):
        return self[self.metadata]


    @property
    def spectra(self):
        return self[self.wavelengths]


    def plot_spectra(self, *args, **kwargs):
        return self.T.plot(*args, **kwargs)


    @property
    def tolerance(self):
        if not hasattr(self._get, '_tolerance'):
            self._get._tolerance = .5
        return self._get._tolerance


    @tolerance.setter
    def tolerance(self, val):
        self._get._tolerance = val