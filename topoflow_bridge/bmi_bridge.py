import os
import functools
import warnings

import numpy as np
import yaml


def to_type(value, dtype):
    if dtype == 'float':
        return float(value)
    elif dtype in ('long', 'int'):
        return int(value)
    elif dtype == 'string':
        return str(value)
    else:
        raise ValueError('dtype not understood {dtype}'.format(dtype=dtype))


def load_cfg(fname):
    params = {}
    with open(fname, 'r') as fp:
        for line in fp:
            try:
                (key, value, dtype, _) = [v.strip() for v in line.split('|')]
            except ValueError:
                pass
            else:
                params[key] = to_type(value, dtype)
    params['rti_file'] = params['site_prefix'] + '.rti'
    return params


def load_rti(fname):
    lines = []
    with open(fname, 'r') as fp:
        for line in fp:
            if ';' in line:
                line = line[:line.find(';')]
            if ':' in line:
                lines.append(line)

    return yaml.load(os.linesep.join(lines))


def camel_case(name):
    return ''.join(name.title().split('_'))


def memoize(func):
    cache = func.cache = {}

    @functools.wraps(func)
    def _wrapped(*args):
        key = str(args)
        if key not in cache:
            cache[key] = func(*args)
        return cache[key]
    return _wrapped


def is_grid(val):
    try:
        return val.ndim == 2
    except AttributeError:
        return False


def is_time_series(val):
    try:
        return val.ndim == 1
    except AttributeError:
        return False


def is_scalar(val):
    try:
        return val.ndim == 0
    except AttributeError:
        return False


def to_grid(val, shape):
    if is_grid(val):
        if val.shape == shape:
            grid = val
        else:
            grid = np.zeros(shape, dtype=type(val))
    elif is_time_series(val):
        grid = val
    elif is_scalar(val):
        grid = np.full(shape, val, dtype=val.dtype)
    else:
        grid = np.full(shape, val, dtype=type(val))

    return grid


def is_scalar_attr(name):
    return 'min_of' in name or 'max_of' in name or name.startswith('basin_outlet')


_BMI_DOCSTRING = """{cls}()

BMI wrapper for the TopoFlow {cls} component.
"""

def bmi_factory(cls, name=None):
    name = name or cls.__name__

    class BmiWrapper():

        _cls = cls

        def __init__(self):
            self._base = self._cls()
            self._shape = None

        def get_component_name(self):
            """Get the name of the component.

            Parameters
            ----------
            None
            
            Returns
            -------
            str
                Name of the compoennt.
            """
            return self._base.get_component_name()

        def get_grid_rank(self, grid):
            """Get the rank of a grid.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            int
                Number of dimension for the grid.
            """
            return grid
            # return self._base.get_grid_rank(grid)

        def get_grid_size(self, grid):
            """Get the number of elements in a grid.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            int
                Number of elements in the grid.
            """
            return self._base.get_grid_size(grid)

        def get_grid_type(self, grid):
            """Get the grid type.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            str
                The type of grid.
            """
            rank = self.get_grid_rank(grid)
            if rank == 2:
                return 'uniform_rectilinear'
            elif rank == 1:
                return 'vector'
            elif rank == 0:
                return 'scalar'

        def get_grid_shape(self, grid):
            """Get the shape of a grid.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            tuple of int
                The shape of the grid as (n_rows, n_cols).

            Raises
            ------
            NotImplementedError
                If the grid is not structured.
            """
            if self.get_grid_type(grid) == 'uniform_rectilinear':
                return self._shape
                # return tuple(
                #     (int(dim) for dim in self._base.get_grid_shape(grid)))
            else:
                raise NotImplementedError(
                    'get_grid_shape not implemented for grid '
                    '{grid}'.format(grid=grid))

        def get_grid_spacing(self, grid):
            """Get the row and column spacing of a grid.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            tuple of float
                The spacing of the grid as (dy, dx).

            Raises
            ------
            NotImplementedError
                If the grid is not rectilinear.
            """
            if self.get_grid_type(grid) == 'uniform_rectilinear':
                return tuple(self._base.get_grid_spacing(grid))
            else:
                raise NotImplementedError(
                    'get_grid_spacing not implemented for grid '
                    '{grid}'.format(grid=grid))

        def get_grid_origin(self, grid):
            """Get the coordinates of the grid origin.

            Parameters
            ----------
            grid : int
                Grid id.

            Returns
            -------
            tuple of float
                The coordinates of the lower-left corner.

            Raises
            ------
            NotImplementedError
                If the grid is not rectilinear.
            """
            if self.get_grid_type(grid) == 'uniform_rectilinear':
                return tuple(self._base.get_grid_origin(grid))
            else:
                raise NotImplementedError(
                    'get_grid_origin not implemented for grid '
                    '{grid}'.format(grid=grid))

        def get_input_var_names(self):
            """Get name of input variables.

            Parameters
            ----------
            None

            Returns
            -------
            tuple of str
                Name of input variables as Standard Names.
            """
            names = tuple(self._base.get_input_var_names())
            if len(names) == 1 and names[0] == 'None':
                return ()
            else:
                return tuple(names)

        def get_output_var_names(self):
            """Get name of output variables.

            Parameters
            ----------
            None

            Returns
            -------
            tuple of str
                Name of output variables as Standard Names.
            """
            names = self._base.get_output_var_names()
            if len(names) == 1 and names[0] == 'None':
                return ()
            else:
                if 'model__time_step' in names:
                    names.remove('model__time_step')
                return tuple(names)

        # @memoize
        def get_var_grid(self, var):
            """Get grid id for a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            int
                Grid id for the variable.
            """
            val = self._get_value(var)
            if val.ndim == 0 or (val.ndim == 1 and val.size == 1):
                return 0
            else:
                return 2
                # return val.ndim

        # @memoize
        def get_var_itemsize(self, var):
            """Get the item size for a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            int
                Size of each item in the variables's array.
            """
            val = self._get_value(var)
            return val.itemsize

        def get_var_units(self, var):
            """Get the units for a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            str
                Units for the variable.
            """
            return self._base.get_var_units(var)

        # @memoize
        def get_var_rank(self, var):
            """Get the number of dimension of a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            int
                Number of dimensions of a variable.
            """
            val = self._get_value(var)
            if val.ndim == 0 or (val.ndim == 1 and val.size == 1):
                return 0
            else:
                return 2

        # @memoize
        def get_var_type(self, var):
            """Get the data type of a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            str
                Data type for the variable as a `numpy.dtype` string.
            """
            val = self._get_value(var)
            return val.dtype

        def _get_value_ptr(self, var):
            """Get a reference to a variable's data.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            ndarray
                Numpy array that points to a variables's data.

            Raises
            ------
            NotImplementedError
                If a reference is unavailable for the given variable.
            """
            topoflow_name = self._base.get_var_name(var)
            try:
                val = getattr(self._base, topoflow_name)
            except AttributeError:
                raise KeyError('{var}: {attr}'.format(var=var, attr=topoflow_name))
            else:
                if not isinstance(val, np.ndarray):
                    # warnings.warn('type of {var} is {type}'.format(var=var, type=type(val)))
                    raise NotImplementedError(
                        'get_value_ptr not implemented for {var}'.format(
                            var=var))
                return val

        def get_value_ptr(self, var):
            """Get a reference to a variable's data.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            ndarray
                Numpy array that points to a variables's data.

            Raises
            ------
            NotImplementedError
                If a reference is unavailable for the given variable.
            """
            # if var not in self.get_output_var_names():
            #     raise KeyError('{name} not an output item'.format(name=var))

            return self._get_value_ptr(var)

        def _get_value(self, var):
            """Get a copy of a variable's data.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            ndarray
                Numpy array of a variables's data.
            """
            try:
                return self._get_value_ptr(var).copy().reshape((-1, ))
            except NotImplementedError:
                topoflow_name = self._base.get_var_name(var)
                return np.array(getattr(self._base, topoflow_name))

        def get_value(self, var):
            """Get a copy of a variable's data.

            Parameters
            ----------
            var : str
                Standard Name of variable.

            Returns
            -------
            ndarray
                Numpy array of a variables's data.
            """
            # if var not in self.get_output_var_names():
            #     raise KeyError('{name} not an output item'.format(name=var))
            return self._get_value(var)

        def set_value(self, var, value):
            """Set the values of a variable.

            Parameters
            ----------
            var : str
                Standard Name of variable.
            values : ndarray
                New values for the variable.
            """
            if var not in self.get_input_var_names():
                raise KeyError('{name} not an input item'.format(name=var))

            topoflow_name = self._base.get_var_name(var)
            try:
                topoflow_var = getattr(self._base, topoflow_name)
            except AttributeError:
                internal_shape = self.get_grid_shape(2)
                setattr(self._base, topoflow_name, value.reshape(internal_shape))
            else:
                try:
                    shape = topoflow_var.shape
                except AttributeError:
                    internal_shape = self.get_grid_shape(2)
                    setattr(self._base, topoflow_name, value.reshape(internal_shape))
                else:
                    # topoflow_var[:] = value[:]
                    setattr(self._base, topoflow_name, value.reshape(shape))
                    # setattr(self, topoflow_name, value)  # dicey (@mdpiper)
                    # gid = self._base.get_var_grid(var)
                    # internal_shape = self._base.get_grid_shape(gid)
                    # setattr(self._base, topoflow_name, value.reshape(internal_shape))
                    
        def get_time_step(self):
            """Get model time step.

            Parameters
            ----------
            None

            Returns
            -------
            float
                Model time step.
            """
            return self._base.get_time_step()

        def get_time_units(self):
            """Get the units of time used by the model.

            Parameters
            ----------
            None

            Returns
            -------
            str
                Units of time.
            """
            return self._base.get_time_units()

        def get_start_time(self):
            """Get model start time.

            Parameters
            ----------
            None

            Returns
            -------
            float
                Model start time.
            """
            return self._base.get_start_time()

        def get_current_time(self):
            """Get current model time.

            Parameters
            ----------
            None

            Returns
            -------
            float
                Current model time.
            """
            return float(self._base.get_current_time())

        def get_end_time(self):
            """Get model stop time.

            Parameters
            ----------
            None

            Returns
            -------
            float
                Model stop time.
            """
            return self._base.get_end_time()

        def initialize(self, fname):
            """Initialize the model.

            Parameters
            ----------
            fname : str
                Name of input configuration file.
            """
            params = load_cfg(fname)
            rti = load_rti(params['rti_file'])
            shape = (rti['Number of rows'], rti['Number of columns'])
            self._shape = shape
            for name in self.get_input_var_names():
                self.set_value(name, np.zeros(shape, dtype=float))

            rtn = self._base.initialize(cfg_file=fname)

            for name in self.get_output_var_names():
                if not is_scalar_attr(name):
                    attr = self._base.get_var_name(name)
                    try:
                        var = getattr(self._base, attr)
                    except AttributeError:
                        val = to_grid(0., shape)
                    else:
                        val = to_grid(var, shape)

                    setattr(self._base, attr, val)


            return rtn

        def update(self):
            """Update the model one time step.

            Parameters
            ----------
            None
            """
            return self._base.update()

        def update_until(self, then):
            """Update the model until a given time.

            Parameters
            ----------
            then : float
                Time to run model until.
            """
            n_steps = (then - self.get_current_time()) / self.get_time_step()
            try:
                n_steps = int(n_steps)
            except TypeError:
                print n_steps
            for _ in xrange(int(n_steps)):
                self.update()

        def finalize(self):
            """Close the model.

            Parameters
            ----------
            None
            """
            return self._base.finalize()

    BmiWrapper.__name__ = camel_case(name)
    BmiWrapper.__doc__ = _BMI_DOCSTRING.format(cls=camel_case(name))
    return BmiWrapper
