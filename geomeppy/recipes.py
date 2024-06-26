"""Recipes for making changes to EnergyPlus IDF files.

These are generally exposed and methods on the IDF object, e.g. `set_default_constructions(idf)`
can be called on an existing `IDF` object like ``myidf.set_default_constructions()``.

"""
from typing import Iterable, List, Optional, Tuple, Union  # noqa
import warnings

from eppy.bunch_subclass import BadEPFieldError
from eppy.idf_msequence import Idf_MSequence  # noqa
import numpy as np

from .geom.polygons import Polygon3D
from .geom.transformations import Transformation
from .geom.vectors import Vector2D, Vector3D  # noqa

if False:  # hacky way to avoid circular imports required by MyPy
    from .idf import IDF  # noqa
    from .patches import EpBunch  # noqa


def set_default_constructions(idf):
    # type: (IDF) -> None
    """Set default constructions for surfaces in the model.

    :param idf: The IDF object.

    """
    constructions = [
        "Project Wall",
        "Project Partition",
        "Project Floor",
        "Project Flat Roof",
        "Project Ceiling",
        "Project Door",
    ]
    for construction in constructions:
        idf.newidfobject(
            "CONSTRUCTION", Name=construction, Outside_Layer="DefaultMaterial"
        )
    idf.newidfobject(
        "MATERIAL",
        Name="DefaultMaterial",
        Roughness="Rough",
        Thickness=0.1,
        Conductivity=0.1,
        Density=1000,
        Specific_Heat=1000,
    )

    idf.newidfobject(
        "CONSTRUCTION", Name="Project External Window", Outside_Layer="DefaultGlazing"
    )
    idf.newidfobject(
        "WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
        Name="DefaultGlazing",
        UFactor=2.7,
        Solar_Heat_Gain_Coefficient=0.763,
        Visible_Transmittance=0.8,
    )

    for surface in idf.getsurfaces():
        set_default_construction(surface)
    for subsurface in idf.getsubsurfaces():
        set_default_construction(subsurface)


def set_default_construction(surface):
    # type: (EpBunch) -> None
    """Set default construction for a surface in the model.

    :param surface: A model surface.

    """
    if surface.Surface_Type.lower() == "wall":
        if surface.Outside_Boundary_Condition.lower() == "outdoors":
            surface.Construction_Name = "Project Wall"
        elif surface.Outside_Boundary_Condition.lower() == "ground":
            surface.Construction_Name = "Project Wall"
        else:
            surface.Construction_Name = "Project Partition"
    if surface.Surface_Type.lower() == "floor":
        if surface.Outside_Boundary_Condition.lower() == "ground":
            surface.Construction_Name = "Project Floor"
        else:
            surface.Construction_Name = "Project Floor"
    if surface.Surface_Type.lower() == "roof":
        surface.Construction_Name = "Project Flat Roof"
    if surface.Surface_Type.lower() == "ceiling":
        surface.Construction_Name = "Project Ceiling"
    if surface.Surface_Type == "window":
        surface.Construction_Name = "Project External Window"
    if surface.Surface_Type == "door":
        surface.Construction_Name = "Project Door"


def set_wwr(
    idf,  # IDF
    wwr=0.2,  # float
    construction=None,  # Optional[str]
    force=False,  # bool
    wwr_map=None,  # Optional[dict]
    orientation=None,  # Optional[str]
    surfaces=None,  # Optional[Iterable]
):
    # type: (...) -> None
    """Set the window to wall ratio on all external walls.

    :param idf: The IDF to edit.
    :param wwr: The window to wall ratio.
    :param construction: Name of a window construction.
    :param force: True to remove all subsurfaces before setting the WWR.
    :param wwr_map: Mapping from wall orientation (azimuth) to WWR, e.g. {180: 0.25, 90: 0.2}.
    :param orientation: One of "north", "east", "south", "west". Walls within 45 degrees will be affected.
    :param surfaces: Iterable of surfaces to set the window to wall ratio of.

    """
    try:
        ggr = idf.idfobjects["GLOBALGEOMETRYRULES"][0]  # type: Optional[Idf_MSequence]
    except IndexError:
        ggr = None

    # check orientation
    orientations = {
        "north": 0.0,
        "east": 90.0,
        "south": 180.0,
        "west": 270.0,
        None: None,
    }
    degrees = orientations.get(orientation, None)
    external_walls = filter(
        lambda x: x.Outside_Boundary_Condition.lower() == "outdoors",
        surfaces or idf.getsurfaces("wall"),
    )
    external_walls = filter(
        lambda x: _has_correct_orientation(x, degrees), external_walls
    )
    subsurfaces = idf.getsubsurfaces()
    base_wwr = wwr
    for wall in external_walls:
        # get any subsurfaces on the wall
        wall_subsurfaces = list(
            filter(lambda x: x.Building_Surface_Name == wall.Name, subsurfaces)
        )
        if not all(_is_window(wss) for wss in wall_subsurfaces) and not force:
            raise ValueError(
                'Not all subsurfaces on wall "{name}" are windows. '
                "Use `force=True` to replace all subsurfaces.".format(name=wall.Name)
            )

        if wall_subsurfaces and not construction:
            constructions = list(
                {wss.Construction_Name for wss in wall_subsurfaces if _is_window(wss)}
            )
            if len(constructions) > 1:
                raise ValueError(
                    'Not all subsurfaces on wall "{name}" have the same construction'.format(
                        name=wall.Name
                    )
                )
            construction = constructions[0]
        # remove all subsurfaces
        for ss in wall_subsurfaces:
            idf.removeidfobject(ss)
        wwr = (wwr_map or {}).get(wall.azimuth, base_wwr)
        if not wwr:
            continue
        coords = window_vertices_given_wall(wall, wwr)
        window = idf.newidfobject(
            "FENESTRATIONSURFACE:DETAILED",
            Name="%s window" % wall.Name,
            Surface_Type="Window",
            Construction_Name=construction or "",
            Building_Surface_Name=wall.Name,
            View_Factor_to_Ground="autocalculate",  # from the surface angle
        )
        window.setcoords(coords, ggr)


def _has_correct_orientation(wall, orientation_degrees):
    # type: (EpBunch, Optional[float]) -> bool
    """Check that the wall has an orientation which requires WWR to be set.

    :param wall: An EpBunch representing a wall.
    :param orientation_degrees: Orientation in degrees.
    :return: True if the wall is within 45 degrees of the orientation passed, or no orientation passed.
             False if the wall is not within 45 of the orientation passed.
    """
    if orientation_degrees is None:
        return True
    if abs((wall.azimuth - orientation_degrees + 180) % 360 - 180) < 45:
        return True
    return False


def _is_window(subsurface):
    if subsurface.key.lower() in {"window", "fenestrationsurface:detailed"}:
        return True


def window_vertices_given_wall(wall, wwr):
    # type: (EpBunch, float) -> Polygon3D
    """Calculate window vertices given wall vertices and glazing ratio.

    :: For each axis:
        1) Translate the axis points so that they are centred around zero
        2) Either:
            a) Multiply the z dimension by the glazing ratio to shrink it vertically
            b) Multiply the x or y dimension by 0.995 to keep inside the surface
        3) Translate the axis points back to their original positions

    :param wall: The wall to add a window on. We expect each wall to have four vertices.
    :param wwr: Window to wall ratio.

    :returns: Window vertices bounding a vertical strip midway up the surface.

    """
    vertices = wall.coords
    average_x = sum([x for x, _y, _z in vertices]) / len(vertices)
    average_y = sum([y for _x, y, _z in vertices]) / len(vertices)
    average_z = sum([z for _x, _y, z in vertices]) / len(vertices)
    # move windows in 0.5% from the edges so they can be drawn in SketchUp
    window_points = [
        [
            ((x - average_x) * 0.999) + average_x,
            ((y - average_y) * 0.999) + average_y,
            ((z - average_z) * wwr) + average_z,
        ]
        for x, y, z in vertices
    ]

    return Polygon3D(window_points)


def translate_to_origin(idf):
    # type: (IDF) -> None
    """Move an IDF close to the origin so that it can be viewed in SketchUp.

    :param idf: The IDF to edit.

    """
    surfaces = idf.getsurfaces()
    subsurfaces = idf.getsubsurfaces()
    shading_surfaces = idf.getshadingsurfaces()

    min_x = min(min(Polygon3D(s.coords).xs) for s in surfaces)
    min_y = min(min(Polygon3D(s.coords).ys) for s in surfaces)

    translate(surfaces, (-min_x, -min_y))
    translate(subsurfaces, (-min_x, -min_y))
    translate(shading_surfaces, (-min_x, -min_y))


def translate(
    surfaces, vector
):  # type: (Idf_MSequence, Union[Tuple[float, float], Vector2D, Vector3D]) -> None
    """Translate all surfaces by a vector.

    :param surfaces: A list of EpBunch objects.
    :param vector: Representation of a vector to translate by.

    """
    vector = Vector3D(*vector)
    for s in surfaces:
        try:
            new_coords = translate_coords(s.coords, vector)
            s.setcoords(new_coords)
        except BadEPFieldError:
            warnings.warn(
                "%s was not affected by this operation since it does not define "
                "vertices."
                % s.Name
            )
            continue


def translate_coords(coords, vector):
    # type: (Union[List[Tuple[float, float, float]], Polygon3D], Union[List[float], Vector3D]) -> List[Union[Vector2D, Vector3D]]  # noqa
    """Translate a set of coords by a direction vector.

    :param coords: A list of points.
    :param vector: Representation of a vector to translate by.
    :returns: List of translated vectors.

    """
    return [Vector3D(*v) + vector for v in coords]


def scale(surfaces, factor, axes):
    # type: (Idf_MSequence, float, str) -> None
    """Scale all surfaces by a factor.

    :param surfaces: A list of EpBunch objects.
    :param factor: Factor to scale the surfaces by.
    :param axes: Axes to scale on.

    """
    for s in surfaces:
        try:
            new_coords = scale_coords(s.coords, factor, axes)
            s.setcoords(new_coords)
        except BadEPFieldError:
            warnings.warn(
                "%s was not affected by this operation since it does not define "
                "vertices."
                % s.Name
            )
            continue


def scale_coords(coords, factor, axes="xy"):
    # type: (Union[List[Tuple[float, float, float]], Polygon3D], float, str) -> Polygon3D
    """Scale a set of coords by a factor.

    :param coords: A list of points.
    :param factor: Factor to scale the surfaces by.
    :param axes: Axes to scale on.
    :returns: A scaled polygon.

    """
    coords = Polygon3D(coords)
    vertices = []
    for coord in coords:
        x = coord[0] * factor if "x" in axes else coord[0]
        y = coord[1] * factor if "y" in axes else coord[1]
        z = coord[2] * factor if "z" in axes else coord[2]
        vertices.append(Vector3D(x, y, z))
    return Polygon3D(vertices)


def rotate(surfaces, angle):
    # type: (Union[List[EpBunch], Idf_MSequence], float) -> None
    """Rotate all surfaces by an angle.

    :param surfaces: A list of EpBunch objects or a mutable sequence.
    :param angle: An angle in degrees.

    """
    radians = np.deg2rad(angle)
    for s in surfaces:
        try:
            new_coords = rotate_coords(s.coords, radians)
            s.setcoords(new_coords)
        except BadEPFieldError:
            warnings.warn(
                "%s was not affected by this operation since it does not define "
                "vertices."
                % s.Name
            )
            continue


def rotate_coords(coords, radians):
    """Rotate a set of coords by an angle in radians.

    :param coords: A list of points.
    :param radians: The angle to rotate by.
    :returns: List of Vector3D objects.

    """
    poly = Polygon3D(coords)
    rotation = Transformation()._rotation(Vector3D(0, 0, 1), radians)
    coords = rotation * poly
    return coords
