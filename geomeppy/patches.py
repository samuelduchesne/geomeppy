# Copyright (c) 2016 Jamie Bull
# Copyright (c) 2012 Santosh Philip
# =======================================================================
#  Distributed under the MIT License.
#  (See accompanying file LICENSE or copy at
#  http://opensource.org/licenses/MIT)
# =======================================================================
"""
Monkey patches for changes to classes and functions in Eppy. These include
fixes which have not yet made it to the released version of Eppy. These will be
removed if/when they are added to Eppy.

"""
import copy
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union  # noqa

from eppy import bunchhelpers, iddgaps
from eppy.EPlusInterfaceFunctions import eplusdata, iddindex, parse_idd
from eppy.EPlusInterfaceFunctions.eplusdata import Eplusdata  # noqa
from eppy.EPlusInterfaceFunctions.structures import CaseInsensitiveDict
from eppy.bunch_subclass import EpBunch as BaseBunch
from eppy.idf_msequence import Idf_MSequence
from eppy.idfreader import convertallfields, iddversiontuple, convertfields
from eppy.modeleditor import IDF as BaseIDF
from eppy.modeleditor import IDDNotSetError, namebunch, newrawobject

from .geom.polygons import Polygon3D  # noqa
from .geom.surfaces import set_coords
from .geom.vectors import Vector3D  # noqa

if False:
    from .idf import IDF  # noqa


class EpBunch(BaseBunch):
    """Monkeypatched EpBunch to add the setcoords function."""

    def setcoords(
        self,
        poly,  # type: Union[List[Vector3D], List[Tuple[float, float, float]], Polygon3D]
        ggr=None,  # type: Optional[Union[List, None, Idf_MSequence]]
    ):
        # type: (...) -> None
        """Set the coordinates of a surface.

        :param poly: Either a Polygon3D object of a list of (x,y,z) tuples.
        :param ggr: A GlobalGeometryRules IDF object. Defaults to None.

        """
        surfaces = [
            "BUILDINGSURFACE:DETAILED",
            "WALL:DETAILED",
            "ROOFCEILING:DETAILED",
            "FLOOR:DETAILED",
            "FENESTRATIONSURFACE:DETAILED",
            "SHADING:SITE:DETAILED",
            "SHADING:BUILDING:DETAILED",
            "SHADING:ZONE:DETAILED",
        ]
        if self.key.upper() in surfaces:
            set_coords(self, poly, ggr)
        else:
            raise AttributeError


def idfreader1(
    fname,  # type: str
    iddfile,  # type: str
    theidf,  # type: IDF
    conv=True,  # type: Optional[bool]
    commdct=None,  # type: List[List[Dict[str, Any]]]
    block=None,  # type: Optional[List]
):
    # type: (...) -> Tuple[Dict[str, Any], Optional[List[Any]], Any, List[List[Dict[str, Any]]], Any, Any]
    """Read idf file and return bunches.

    :param fname: Name of the IDF file to read.
    :param iddfile: Name of the IDD file to use to interpret the IDF.
    :param conv: If True, convert strings to floats and integers where marked in the IDD. Defaults to None.
    :param commdct: Descriptions of IDF fields from the IDD. Defaults to None.
    :param block: EnergyPlus field ID names of the IDF from the IDD. Defaults to None.
    :returns: bunchdt Dict of lists of idf_MSequence objects in the IDF.
    :returns: block EnergyPlus field ID names of the IDF from the IDD.
    :returns data: Eplusdata object containing representions of IDF objects.
    :returns: commdct List of names of IDF objects.
    :returns: idd_index A pair of dicts used for fast lookups of names of groups of objects.
    :returns: versiontuple Version of EnergyPlus from the IDD.

    """
    versiontuple = iddversiontuple(iddfile)
    block, data, commdct, idd_index = readdatacommdct1(
        fname, iddfile=iddfile, commdct=commdct, block=block
    )
    if conv:
        convertallfields(data, commdct)
    # fill gaps in idd
    if versiontuple < (8,):
        skiplist = ["TABLE:MULTIVARIABLELOOKUP"]  # type: Optional[List[str]]
    else:
        skiplist = None
    nofirstfields = iddgaps.missingkeys_standard(commdct, data.dtls, skiplist=skiplist)
    iddgaps.missingkeys_nonstandard(block, commdct, data.dtls, nofirstfields)
    bunchdt = makebunches_alter(data, commdct, theidf, block)

    return bunchdt, block, data, commdct, idd_index, versiontuple


def readdatacommdct1(
    idfname,  # type: str
    iddfile="Energy+.idd",  # type: str
    commdct=None,  # type: Optional[List[List[Dict[str, Any]]]]
    block=None,  # type: Optional[List]
):
    # type: (...) -> Tuple[Optional[List[Any]], Any, List[List[Dict[str, Any]]], Any]
    """Read the idf file.

    This is patched so that the IDD index is not lost when reading a new IDF without reloading the modeleditor module.

    :param idfname: Name of the IDF file to read.
    :param iddfile: Name of the IDD file to use to interpret the IDF.
    :param commdct: Descriptions of IDF fields from the IDD. Defaults to None.
    :param block: EnergyPlus field ID names of the IDF from the IDD. Defaults to None.
    :returns: block EnergyPlus field ID names of the IDF from the IDD.
    :returns data: Eplusdata object containing representions of IDF objects.
    :returns: commdct List of names of IDF objects.
    :returns: idd_index A pair of dicts used for fast lookups of names of groups of objects.

    """
    if not commdct:
        block, commlst, updated_commdct, idd_index = parse_idd.extractidddata(iddfile)
        theidd = eplusdata.Idd(block, 2)
    else:
        theidd = eplusdata.Idd(block, 2)
        name2refs = iddindex.makename2refdct(commdct)
        ref2namesdct = iddindex.makeref2namesdct(name2refs)
        idd_index = dict(name2refs=name2refs, ref2names=ref2namesdct)
        updated_commdct = iddindex.ref2names2commdct(ref2namesdct, commdct)
    data = eplusdata.Eplusdata(theidd, idfname)
    return block, data, updated_commdct, idd_index


def addthisbunch(
    bunchdt,  # type: Dict[str, Idf_MSequence]
    data,  # type: Eplusdata
    commdct,  # type: List[List[Dict[str, Any]]]
    thisbunch,  # type: EpBunch
    _idf,  # type: IDF
):
    # type: (...) -> EpBunch
    """Add an object to the IDF. Monkeypatched to return the object.

    `thisbunch` usually comes from another idf file or it can be used to copy within the idf file.

    :param bunchdt: Dict of lists of idf_MSequence objects in the IDF.
    :param data: Eplusdata object containing representions of IDF objects.
    :param commdct: Descriptions of IDF fields from the IDD.
    :param thisbunch: The object to add to the model.
    :param _idf: The IDF object. Not used either here or in Eppy but kept for consistency with Eppy.
    :returns: The EpBunch object added.

    """
    key = thisbunch.key.upper()
    obj = copy.copy(thisbunch.obj)
    abunch = obj2bunch(data, commdct, obj, thisbunch.theidf.block)
    bunchdt[key].append(abunch)
    return abunch


def makebunches(
    data, commdct, theidf
):  # type: (Eplusdata, List[List[Dict[str, Any]]], IDF) -> Dict[str, Idf_MSequence]
    """Make bunches with data.

    :param data: Eplusdata object containing representions of IDF objects.
    :param commdct: Descriptions of IDF fields from the IDD.
    :param theidf: The IDF object.
    :returns: Dict of lists of idf_MSequence objects in the IDF.

    """
    bunchdt = {}
    dt, dtls = data.dt, data.dtls
    for obj_i, key in enumerate(dtls):
        key = key.upper()
        objs = dt[key]
        list1 = []
        for obj in objs:
            bobj = makeabunch(commdct, obj, obj_i)
            list1.append(bobj)
        bunchdt[key] = Idf_MSequence(list1, objs, theidf)
    return bunchdt

def makebunches_alter(data, commdct, theidf, block=None):
    """make bunches with data"""
    bunchdt = CaseInsensitiveDict()
    dt, dtls = data.dt, data.dtls
    for obj_i, key in enumerate(dtls):
        key = key.upper()
        objs = dt[key]
        list1 = []
        for obj in objs:
            bobj = makeabunch(commdct, obj, obj_i, block=block)
            list1.append(bobj)
        bunchdt[key] = Idf_MSequence(list1, objs, theidf)
    return bunchdt


def obj2bunch(
    data, commdct, obj, block=None
):  # type: (Eplusdata, List[List[Dict[str, Any]]], List[str]) -> EpBunch
    """Make a new bunch object using the data object.

    :param data: Eplusdata object containing representions of IDF objects.
    :param commdct: Descriptions of IDF fields from the IDD.
    :param obj: List of field values in an object.
    :returns: EpBunch object.

    """
    dtls = data.dtls
    key = obj[0].upper()
    key_i = dtls.index(key)
    abunch = makeabunch(commdct, obj, key_i, block)
    return abunch


def makeabunch(commdct, obj, obj_i, block=None, debugidd=True, ):
    """make a bunch from the object"""
    objidd = commdct[obj_i]
    objfields = [comm.get("field") for comm in commdct[obj_i]]
    if debugidd:
        import eppy.ext_field_functions as extff

        if len(obj) > len(objfields):
            # there are not enough fields in the IDD to match the IDF
            # -- increase the number of fields in the IDD (in block and commdct)
            #       -- start
            n = len(obj) - len(objfields)
            key_txt = obj[0]
            objfields = extff.increaseIDDfields(block, commdct, obj_i, key_txt, n)
            # -- increase the number of fields in the IDD (in block and commdct)
            #       -- end
            #
            # -- convertfields for added fields -  start
            key_i = obj_i
            key_comm = commdct[obj_i]
            try:
                inblock = block[obj_i]
            except TypeError as e:
                inblock = None
            obj = convertfields(key_comm, obj, inblock)
            # -- convertfields for added fields -  end
    objfields[0] = ["key"]
    objfields = [field[0] for field in objfields]
    obj_fields = [bunchhelpers.makefieldname(field) for field in objfields]
    bobj = EpBunch(obj, obj_fields, objidd)
    return bobj


class PatchedIDF(BaseIDF):
    """Monkey-patched IDF.

    Patched to add read (to add additional functionality) and to fix copyidfobject and newidfobject.
    """

    def read(self):
        """Read the IDF file and the IDD file.

        If the IDD file had already been read, it will not be read again.

        Populates the following data structures::

        - idfobjects : list
        - model : list
        - idd_info : list
        - idd_index : dict
        """
        if self.getiddname() is None:
            errortxt = "IDD file needed to read the idf file. Set it using IDF.setiddname(iddfile)"
            raise IDDNotSetError(errortxt)
        (
            self.idfobjects,
            block,
            self.model,
            idd_info,
            idd_index,
            versiontuple,
        ) = idfreader1(
            self.idfname, self.iddname, self, commdct=self.idd_info, block=self.block
        )
        self.__class__.setidd(idd_info, idd_index, block, versiontuple)

    def newidfobject(self, key, aname="", defaultvalues=True, **kwargs):
        # type: (str, str, bool, **Any) -> EpBunch
        """Add a new idfobject to the model.

        If you don't specify a value for a field, the default value will be set, unless
        defaultvalues is set to False.

        For example ::

            newidfobject("CONSTRUCTION")
            newidfobject("CONSTRUCTION",
                Name='Interior Ceiling_class',
                Outside_Layer='LW Concrete',
                Layer_2='soundmat')

        :param key: The type of IDF object. This must be in ALL_CAPS.
        :param aname: This parameter is not used. It is left there for backward compatibility.
        :param defaultvalues: Specifies whether to set default values when creating IDF objects.
        :param kwargs: Keyword arguments in the format `field=value` used to set fields in the EnergyPlus object.
        :returns: EpBunch object.
        """
        obj = newrawobject(self.model, self.idd_info, key, defaultvalues=defaultvalues)
        abunch = obj2bunch(self.model, self.idd_info, obj)
        if aname:
            warnings.warn(
                "The aname parameter should no longer be used (%s)." % aname,
                UserWarning,
            )
            namebunch(abunch, aname)
        self.idfobjects[key].append(abunch)  # type: Dict[str, Idf_MSequence]
        for k, v in kwargs.items():
            abunch[k] = v
        return abunch

    def copyidfobject(self, idfobject):
        # type: (EpBunch) -> EpBunch
        """Add an IDF object to the IDF.

        This has been monkey-patched to add the return value.

        :param idfobject: The IDF object to copy. Usually from another IDF, or it can be used to copy within this IDF.
        :returns: EpBunch object.
        """
        return addthisbunch(self.idfobjects, self.model, self.idd_info, idfobject, self)
