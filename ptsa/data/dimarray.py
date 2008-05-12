#emacs: -*- mode: python-mode; py-indent-offset: 4; indent-tabs-mode: nil -*-
#ex: set sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See the COPYING file distributed along with the PTSA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

import numpy as np
import copy as copylib
import re
from ptsa.data.attrarray import AttrArray

###############################
# New dimensioned array class
###############################

class Dim(AttrArray):
    """
    Dim(data, name, dtype=None, copy=False, **kwargs)
    
    Class that defines a dimension.  It has one required attribute
    (name), but other custom attributes (e.g., units) can be specified.

    Parameters
    ----------
    data : {1-D array_like}
        The values of the dimension (e.g., time points for a time dimension)
    name : {object}
        The name of the dimension (e.g., 'time')
    dtype : {numpy.dtype},optional
        The data type.
    copy : {bool},optional
        Flag specifying whether or not data should be copied.
    **kwargs : {**kwargs},optional
        Additional custom attributes (e.g., units='ms').
    """
    _required_attrs = {'name':str}
    
    def __new__(cls, data, name, dtype=None, copy=True, **kwargs):
        # set the kwargs to have name
        kwargs['name'] = name
        # make new AttrArray:
        dim = AttrArray(data,dtype=dtype,copy=copy,**kwargs)
        # convert to Dim and return:
        return dim.view(cls)

    def __array_finalize__(self, obj):
        AttrArray.__array_finalize__(self,obj)
        # XXX perhaps save the copy state and only copy if requested
        #self._attrs = copylib.copy(getattr(obj, '_attrs', {}))
        # Set all attributes:
        #self._setAllAttr()
        # Ensure that the required attributes are present:
        #self._chkReqAttr()
        
        #self._getitem = False
        #if (isinstance(obj, Dim) and obj._getitem): return

        # make sure the data is 1-D:
        if self.ndim == 1: # if 1-D, return
            return
        # massage the array into 1-D if possible:
        elif self.ndim > 1:
            # using self.squeeze() can lead to nasty recursions and
            # 0-D arrays so we do it by hand:
            newshape = tuple([x for x in self.shape if x > 1])
            ndim = len(newshape)
            if ndim == 1:
                self.shape = newshape
                return
            elif ndim == 0:
                self.shape = (1,)
            else:
                raise ValueError("Dim instances must be 1-dimensional!\ndim:\n"+
                                 str(self)+"\nnewshape:",newshape)
        # if the array is 0-D, make it 1-D:
        elif self.ndim == 0:
            self.shape = (1)
            return
        else:
            # This would require negative self.ndim which would
            # indicate a serious bug in ndarray.
            raise ValueError("Invalid number of dimensions!")



class DimArray(AttrArray):
    """
    DimArray(data, dims, dtype=None, copy=False, **kwargs)

    Class that keeps track of the dimensions of a NumPy ndarray.  The
    dimensions are specified in the dims attribute as a list of Dim
    instances that match the shape of the data array.

    The DimArray class provides a number of conveniences above and
    beyond normal ndarrays.  These include the ability to refer to
    dimensions by name and to select subsets of the data based on
    complex queries using the dimension names.

    Parameters
    ----------
    data : {array_like}
        The dimensioned data.
    dims : {list of Dim instances}
        The dimensions of the data.
    dtype : {numpy.dtype},optional
        The data type.
    copy : {bool},optional
        Flag specifying whether or not data should be copied.
    **kwargs : {**kwargs},optional
        Additional custom attributes.    
    """
    _required_attrs = {'dims':list}
    dim_names = property(lambda self: [dim.name for dim in self.dims],
                     doc="Dimension names (read only)")
    _dim_namesRE = property(lambda self: re.compile('(?<!.)\\b' +
                      '\\b(?!.)|(?<!.)\\b'.join(self.dim_names) + '\\b(?!.)'))

    
    def __new__(cls, data, dims, dtype=None, copy=True, **kwargs):
        # set the kwargs to have name
        kwargs['dims'] = dims
        # make new AttrArray:
        dimarray = AttrArray(data,dtype=dtype,copy=copy,**kwargs)
        # convert to DimArray and return:
        return dimarray.view(cls)

    def __array_finalize__(self,obj):
        # call the AttrArray finalize
        AttrArray.__array_finalize__(self,obj)
        # ensure _getitem flag is off
        self._getitem = False
        # if this method is called from __getitem__, don't check dims
        # (they are adjusted later by __getitem__):
        if (isinstance(obj,DimArray) and obj._getitem): return
        # ensure that the dims attribute is valid:
        self._chkDims()

    def _chkDims(self):
        """
        Ensure that the dims attribute is a list of Dim instances that match the array shape.
        """
        # Ensure list:
        if not isinstance(self.dims,list):
            raise AttributeError("The dims attribute must be a list "+
                             "of Dim instances!\ndims:\n"+str(self.dims))
        
        # Ensure that list is made up of only Dim instances:
        if not np.array([isinstance(x,Dim) for x in self.dims]).all():
            raise AttributeError("The dims attribute must contain "+
                             "only Dim instances!\ndims:\n"+str(self.dims))
        
        # Ensure that the lengths of the Dim instances match the array shape:
        if self.shape != tuple([len(d) for d in self.dims]):
            raise AttributeError("The length of the dims must match the shape of "+
                             "the DimArray!\nDimArray shape: "+str(self.shape)+
                             "\nShape of the dims:\n"+
                             str(tuple([len(d) for d in self.dims])))
        
        # Ensure unique dimension names:
        if len(np.unique(self.dim_names)) != len(self.dim_names):
            raise AttributeError("Dimension names must be unique!\nnames: "+
                                 str(self.dim_names))



    def _select_ind(self,*args,**kwargs):
        """
        Returns a tuple of index arrays for the selected conditions and an array
        of Boolean index arrays.     
        """
        # get starting indicies
        ind = [np.ones(dim.shape,np.bool) for dim in self.dims]

        # process the args
        for arg in args:
            # arg must be a string
            filterStr = arg

            # figure out which dimension we're dealing with
            foundDim = False
            for d,k in enumerate(self.dim_names):
                # RE makes sure to not replace substrings
                if re.search(r'\b'+k+r'\b',filterStr):
                    # this is our dimension
                    foundDim = True

                    # replace the string
                    filterStr = re.sub(r'\b'+k+r'\b','self["'+k+'"]',filterStr)

                    # get the new index
                    newind = eval(filterStr)
                    
                    # apply it to the dimension index
                    ind[d] = ind[d] & newind

                    # break this loop to continue the next
                    break
            # if we get to here, the provided string did not specify any dimensions
            if not foundDim:
                # XXX eventually this should be a custom exception
                raise ValueError("The provided filter string did not specify "+
                                 "any valid dimensions: "+str(filterStr))
            
        # loop over the kwargs
        for key,value in kwargs.iteritems():
            if key in self.dim_names:
                # get the proper dimension to cull
                d = self.dim_names.index(key)
                ind[d] = ind[d] & value

        # create the final master index
        m_ind = np.ix_(*ind)

        return m_ind,ind


    def __getitem__(self, index):
        # embedd in try block to ensure that _getitem flag is reset (in finally)
        try:
            if isinstance(index,str):
                # see if it's just a single dimension name
                res = self._dim_namesRE.search(index)
                if res:
                    # we have a single name, so return the
                    # corresponding dimension
                    return self.dims[self.dim_names.index(res.group())]
                else:
                    # call select to do the work
                    return self.select(index)
            elif isinstance(index,int):
                # a single int as index eliminates the first dimension:
                newdims = copylib.deepcopy(self.dims)
                newdims.pop(0)
            elif isinstance(index,slice) or isinstance(index,np.ndarray):
                # a single slice is taken over the first dimension:
                newdims = copylib.deepcopy(self.dims)
                newdims[0]=newdims[0][index]
            elif isinstance(index,tuple):
                # for tuples, loop over the elements:
                newdims = copylib.deepcopy(self.dims)
                adj_i = 0 # adjusted index (if dimensions are eliminated)
                for i,ind in enumerate(index):
                    if isinstance(ind,int):
                        # eliminate respective dim and update adj_i accordingly:
                        newdims.pop(adj_i)
                        adj_i -= 1
                    elif isinstance(ind,slice) or isinstance(ind,np.ndarray):
                        # apply the slice or array to the respective dimension
                        newdims[adj_i] = newdims[adj_i][ind]
                    else: # not sure if there are other legitimate indices here
                        raise NotImplementedError("This index is not (yet?) "+
                                                  " implemented!",type(ind),
                                                  str(ind),str(i),str(adj_i),
                                                  type(index),str(index))
                    # increment adjusted index:
                    adj_i += 1
            else: # not sure if there are other legitimate indices here
                raise NotImplementedError("This index is not (yet?) "+
                                          "implemented!",type(index),str(index))
            
            # Now that the dimensions are updated, we need to get the data:
            # set _getitem flag for __array_finalize__:
            self._getitem = True
            # get the data:
            ret = np.ndarray.__getitem__(self,index)
            # if the resulting data is scalar, return it:
            if ret.ndim == 0:
                return ret
            else: # othewise, adjust the dimensions:
                # set new dimensions:
                ret.dims = newdims
                # finalize the new array and return:
                ret.__array_finalize__(ret)
                return ret            
        finally:
            # reset the _getitem flag:
            self._getitem = False        

    def select(self,*args,**kwargs):
        """
        Return a slice of the data filtered with the select conditions.

        data.select('time>0','events.recalled==True')
        or
        data.select(time=data['time']>0,events=data['events'].recalled==True)
        or 
        data.find("time>kwargs['t']","events.recalled==kwargs['val']",t=0,val=True)

        To get a tuple of index arrays for the selected conditions use the find method.
        """
        m_ind,ind = self._select_ind(*args,**kwargs)
        return self[m_ind]

    def _apply_func(self,func,axis,**kwargs):
        ret = self.view(AttrArray)
        if axis is None:
            return func(ret,axis=axis,**kwargs)
        else:
            ret.dims.pop(axis)
            ret = func(ret,axis=axis,**kwargs)
            return ret.view(self.__class__)
             

    
    def mean(self, axis=None, dtype=None, out=None):
        if isinstance(axis,str):
            # must convert to index dim
            axis = self.names.index(axis)
        ret = self.view(AttrArray).mean(axis=axis, dtype=dtype, out=out)
        if axis is None:
            # just return what we got
            return ret
        else:
            # pop the dim
            ret.dims.pop(axis)
            return ret.view(self.__class__)
    
    def std(self, axis=None, dtype=None, out=None):
        if isinstance(axis,str):
            # must convert to index dim
            axis = self.names.index(axis)
        ret = self.view(AttrArray).std(axis=axis, dtype=dtype, out=out)
        if axis is None:
            # just return what we got
            return ret
        else:
            # pop the dim
            ret.dims.pop(axis)
            return ret.view(self.__class__)

# set the doc strings
DimArray.mean.im_func.func_doc = np.ndarray.mean.__doc__            
DimArray.std.im_func.func_doc = np.ndarray.std.__doc__            

    
