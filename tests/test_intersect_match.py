"""Tests for intersecting and matching."""
import itertools

import pytest
from eppy.iddcurrent import iddcurrent
from six import StringIO


from geomeppy.geom.surfaces import minimal_set
from geomeppy.idf import IDF
from geomeppy.geom.intersect_match import (
    get_adjacencies,
    intersect_idf_surfaces,
    match_idf_surfaces,
)
from geomeppy.geom.polygons import intersect, is_hole, Polygon3D
from geomeppy.recipes import translate_coords
from geomeppy.utilities import almostequal


class TestSetCoords:
    def test_set_coords(self, base_idf):
        # type: (IDF) -> None
        idf = base_idf
        ggr = idf.idfobjects["GLOBALGEOMETRYRULES"]
        wall = idf.idfobjects["BUILDINGSURFACE:DETAILED"][0]
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)])
        wall.setcoords(poly1, ggr)


class TestSimpleTestPolygons:
    def test_simple_match(self):
        # type: () -> None
        """
        The intersect function should just return the two polygons.
         ___
        | 1 |
        |_2_|

        """
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)])
        poly2 = Polygon3D([(1, 1, 0), (1, 0, 0), (0, 0, 0), (0, 1, 0)])
        adjacencies = [(poly1, poly2)]
        result = intersect(*adjacencies[0])
        expected = [poly1, poly2]
        assert len(result) == len(expected)
        for poly in expected:
            assert poly in result

    def test_simple_overlap(self):
        # type: () -> None
        """
        The intersect function should return four surfaces.
         __ ___ __
        | 1| 1 |  |
        |__|_2_|_2|

         __ ___ __
        | 1| 3 |  |
        |__|_4_|_2|

        """
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly2 = Polygon3D([(3, 1, 0), (3, 0, 0), (1, 0, 0), (1, 1, 0)])
        adjacencies = [(poly1, poly2)]
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)])
        poly2 = Polygon3D([(3, 1, 0), (3, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly3 = Polygon3D([(1, 1, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly4 = Polygon3D([(2, 1, 0), (2, 0, 0), (1, 0, 0), (1, 1, 0)])
        result = intersect(*adjacencies[0])
        expected = [poly1, poly2, poly3, poly4]
        assert len(result) == len(expected)
        for poly in expected:
            assert poly in result

    def test_simple_hole(self):
        # type: () -> None
        """
         _________
        | 1 ___   |
        |  | 2 |  |
        |  |___|  |
        |_________|

         ________
        |\ ___   |
        |1| 2 | 4|
        | |_3_|  |
        |/_______|

        """
        poly1 = Polygon3D([(0, 4, 0), (0, 0, 0), (4, 0, 0), (4, 4, 0)])
        poly2 = Polygon3D([(2, 2, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0)])
        adjacencies = [(poly1, poly2)]

        poly1 = Polygon3D(
            [(0, 4, 0), (0, 0, 0), (1, 1, 0), (1, 2, 0)]
        )  # smaller section
        poly2 = Polygon3D([(1, 2, 0), (1, 1, 0), (2, 1, 0), (2, 2, 0)])  # inverse hole
        poly3 = Polygon3D([(2, 2, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0)])  # hole
        poly4 = Polygon3D(
            [
                (4, 4, 0),
                (0, 4, 0),
                (1, 2, 0),
                (2, 2, 0),
                (2, 1, 0),
                (1, 1, 0),
                (0, 0, 0),
                (4, 0, 0),
            ]
        )  # larger section
        result = intersect(*adjacencies[0])
        expected = [poly1, poly2, poly3, poly4]
        assert len(result) == len(expected)
        for poly in result:
            assert poly in expected

    def test_three_overlapping(self):
        # type: () -> None
        """
         __ ___ __ __
        | 1| 1 | 3| 3|
        |__|_2_|_2|__|

         __ ___ __ __
        | 1| 2 | 4| 6|
        |__|_3_|_5|__|

        """
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly2 = Polygon3D([(3, 1, 0), (3, 0, 0), (1, 0, 0), (1, 1, 0)])
        poly3 = Polygon3D([(2, 1, 0), (2, 0, 0), (4, 0, 0), (4, 1, 0)])
        adjacencies = [(poly1, poly2), (poly2, poly3)]
        poly1 = Polygon3D([(0, 1, 0), (0, 0, 0), (1, 0, 0), (1, 1, 0)])
        poly2 = Polygon3D([(2, 1, 0), (2, 0, 0), (1, 0, 0), (1, 1, 0)])
        poly3 = Polygon3D([(1, 1, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly4 = Polygon3D([(2, 1, 0), (2, 0, 0), (3, 0, 0), (3, 1, 0)])
        poly5 = Polygon3D([(3, 1, 0), (3, 0, 0), (2, 0, 0), (2, 1, 0)])
        poly6 = Polygon3D([(3, 1, 0), (3, 0, 0), (4, 0, 0), (4, 1, 0)])
        expected = [poly1, poly2, poly3, poly4, poly5, poly6]

        result = intersect(*adjacencies[0])
        result.extend(intersect(*adjacencies[1]))

        assert len(minimal_set(result)) == len(minimal_set(expected))
        for poly in expected:
            assert poly in result

    def test_double_overlap(self):
        # type: () -> None
        """
         __________
        |__1_______|
        | 1 | 2 |1 |
        |_2_|   |2_|
        |__________|

         __________
        |__1________|
        | 2 | 4 | 5 |
        |_3_|   |_6_|
        |___________|

        """
        poly1 = Polygon3D([(0, 2, 0), (0, 0, 0), (3, 0, 0), (3, 2, 0)])
        poly2 = Polygon3D(
            [
                (3, 3, 0),
                (3, 1, 0),
                (2, 1, 0),
                (2, 2, 0),
                (1, 2, 0),
                (1, 1, 0),
                (0, 1, 0),
                (0, 3, 0),
            ]
        )
        adjacencies = [(poly1, poly2)]

        poly1 = Polygon3D([(3, 3, 0), (3, 2, 0), (0, 2, 0), (0, 3, 0)])
        poly2 = Polygon3D([(0, 2, 0), (0, 1, 0), (1, 1, 0), (1, 2, 0)])
        poly3 = Polygon3D([(1, 2, 0), (1, 1, 0), (0, 1, 0), (0, 2, 0)])
        poly4 = Polygon3D(
            [
                (1, 2, 0),
                (1, 1, 0),
                (0, 1, 0),
                (0, 0, 0),
                (3, 0, 0),
                (3, 1, 0),
                (2, 1, 0),
                (2, 2, 0),
            ]
        )
        poly5 = Polygon3D([(2, 2, 0), (2, 1, 0), (3, 1, 0), (3, 2, 0)])
        poly6 = Polygon3D([(3, 2, 0), (3, 1, 0), (2, 1, 0), (2, 2, 0)])

        result = intersect(*adjacencies[0])
        expected = [poly1, poly2, poly3, poly4, poly5, poly6]
        assert len(result) == len(expected)
        assert len(result) == len(expected)
        for poly in expected:
            assert poly in result

    def test_vertically_offset(self):
        # type: () -> None
        """
         ___
        |_1_|
        | 1 |
        |_2_|
        |_2_|
         ___
        |_1_|
        | 2 |
        |_3_|
        |_4_|

        """
        poly1 = Polygon3D([(0, 0, 1), (0, 0, 0), (2, 0, 0), (2, 0, 1)])
        poly2 = Polygon3D([(3, 0, 1), (3, 0, 0), (1, 0, 0), (1, 0, 1)])
        adjacencies = [(poly1, poly2)]
        poly1 = Polygon3D([(0, 0, 1), (0, 0, 0), (1, 0, 0), (1, 0, 1)])
        poly2 = Polygon3D([(3, 0, 1), (3, 0, 0), (2, 0, 0), (2, 0, 1)])
        poly3 = Polygon3D([(1, 0, 1), (1, 0, 0), (2, 0, 0), (2, 0, 1)])
        poly4 = Polygon3D([(2, 0, 1), (2, 0, 0), (1, 0, 0), (1, 0, 1)])
        result = intersect(*adjacencies[0])
        expected = [poly1, poly2, poly3, poly4]
        assert len(result) == len(expected)
        for poly in expected:
            assert poly in result


class TestMatchSurfaces:
    def test_match_idf_surfaces(self, base_idf):
        # type: (IDF) -> None
        idf = base_idf
        intersect_idf_surfaces(idf)
        match_idf_surfaces(idf)
        inside_walls = [
            obj
            for obj in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
            if obj.Outside_Boundary_Condition == "surface"
        ]
        assert inside_walls
        for w in inside_walls:
            assert w.Outside_Boundary_Condition_Object != ""

        outside_walls = [
            obj
            for obj in idf.idfobjects["BUILDINGSURFACE:DETAILED"]
            if obj.Outside_Boundary_Condition == "outdoors"
        ]
        assert outside_walls
        for w in outside_walls:
            assert w.Outside_Boundary_Condition_Object == ""

        floors = idf.getsurfaces("floor")
        assert floors
        for f in floors:
            assert f.Outside_Boundary_Condition == "ground"
            assert f.Outside_Boundary_Condition_Object == ""


class TestAdjacencies:
    def test_get_adjacencies(self, base_idf):
        # type: (IDF) -> None
        surfaces = base_idf.getsurfaces()
        adjacencies = get_adjacencies(surfaces)
        assert ("BuildingSurface:Detailed", "z1_WALL_0002") in adjacencies
        assert ("BuildingSurface:Detailed", "z2_WALL_0004") in adjacencies
        assert len(adjacencies) == 2


def test_intersect():
    # type: () -> None
    poly1 = Polygon3D(
        [(1.0, 2.1, 0.5), (1.0, 2.1, 0.0), (2.0, 2.0, 0.0), (2.0, 2.0, 0.5)]
    )
    poly2 = Polygon3D(
        [(2.5, 1.95, 0.5), (2.5, 1.95, 0.0), (1.5, 2.05, 0.0), (1.5, 2.05, 0.5)]
    )
    intersection = poly1.intersect(poly2)[0]
    assert not is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)


def test_real_intersect():
    # type: () -> None
    """
    Test that we can make a previously failing test pass by moving to the
    origin first.

    """
    poly1 = Polygon3D(
        [
            (526492.65, 185910.65, 6.0),
            (526492.65, 185910.65, 3.0),
            (526489.05, 185916.45, 3.0),
            (526489.05, 185916.45, 6.0),
        ]
    )
    poly2 = Polygon3D(
        [
            (526489.05, 185916.45, 5.0),
            (526489.05, 185916.45, 2.5),
            (526492.65, 185910.65, 2.5),
            (526492.65, 185910.65, 5.0),
        ]
    )
    min_x = min(min(s.xs) for s in [poly1, poly2])
    min_y = min(min(s.ys) for s in [poly1, poly2])
    poly1 = Polygon3D(translate_coords(poly1, [-min_x, -min_y, 0]))
    poly2 = Polygon3D(translate_coords(poly2, [-min_x, -min_y, 0]))
    intersection = Polygon3D(
        translate_coords(poly1.intersect(poly2)[0], [min_x, min_y, 0])
    )
    poly1 = Polygon3D(translate_coords(poly1, [min_x, min_y, 0]))
    poly2 = Polygon3D(translate_coords(poly2, [min_x, min_y, 0]))
    assert not is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)


def test_is_hole():
    # type: () -> None
    """Test if a surface represents a hole in one of the surfaces."""
    # opposite faces (all touching edges)
    poly1 = Polygon3D([(0, 4, 0), (0, 0, 0), (4, 0, 0), (4, 4, 0)])
    poly2 = Polygon3D(reversed([(0, 4, 0), (0, 0, 0), (4, 0, 0), (4, 4, 0)]))
    intersection = poly1.intersect(poly2)[0]
    assert not is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)

    # poly2 is within poly1 and reversed (no touching edges)
    poly1 = Polygon3D([(0, 4, 0), (0, 0, 0), (4, 0, 0), (4, 4, 0)])
    poly2 = Polygon3D(reversed([(1, 3, 0), (1, 1, 0), (3, 1, 0), (3, 3, 0)]))
    intersection = poly1.intersect(poly2)[0]
    assert is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)

    # poly2 is within poly1 and reversed (touches at x=0)
    poly1 = Polygon3D([(0, 4, 0), (0, 0, 0), (4, 0, 0), (4, 4, 0)])
    poly2 = Polygon3D(reversed([(0, 3, 0), (0, 1, 0), (3, 1, 0), (3, 3, 0)]))
    intersection = poly1.intersect(poly2)[0]
    assert not is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)

    # poly2 overlaps poly1
    poly1 = Polygon3D([(1, 4, 0), (1, 0, 0), (5, 0, 0), (5, 4, 0)])
    poly2 = Polygon3D(reversed([(0, 3, 0), (0, 1, 0), (3, 1, 0), (3, 3, 0)]))
    intersection = poly1.intersect(poly2)[0]
    assert not is_hole(poly1, intersection)
    assert not is_hole(poly2, intersection)


class TestIntersectMatchRing:
    def test_intersect_idf_surfaces(self, ring_idf):
        # type: (IDF) -> None
        idf = ring_idf
        starting = len(idf.idfobjects["BUILDINGSURFACE:DETAILED"])
        intersect_idf_surfaces(idf)
        idf.set_default_constructions()
        ending = len(idf.idfobjects["BUILDINGSURFACE:DETAILED"])
        assert starting == 12
        assert ending == 15
        for name in [
            "z1 Roof 0001_1",
            "z1 Roof 0001_2",
            "z1 Roof 0001_3",
            "z2 Floor 0001_1",
        ]:
            obj = idf.getobject("BUILDINGSURFACE:DETAILED", name)
            assert obj


class TestIntersectMatch:
    def test_getsurfaces(self, base_idf):
        # type: (IDF) -> None
        idf = base_idf
        surfaces = idf.getsurfaces()
        assert len(surfaces) == 12

    def test_intersect_idf_surfaces(self, base_idf):
        # type: (IDF) -> None
        idf = base_idf
        starting = len(idf.idfobjects["BUILDINGSURFACE:DETAILED"])
        intersect_idf_surfaces(idf)
        ending = len(idf.idfobjects["BUILDINGSURFACE:DETAILED"])
        assert starting == 12
        assert ending == 14

        for name in [
            "z1_WALL_0002_1",
            "z1_WALL_0002_2",
            "z2_WALL_0004_1",
            "z2_WALL_0004_2",
        ]:
            obj = idf.getobject("BUILDINGSURFACE:DETAILED", name)
            assert obj

    def test_match_idf_surfaces(self):
        # type: () -> None
        """Test intersect_match for stacked geometry"""
        iddfhandle = StringIO(iddcurrent.iddtxt)
        if IDF.getiddname() == None:
            IDF.setiddname(iddfhandle)

        idf = IDF(StringIO("Version, 8.9;"))
        lower_poly = [[21, 5], [21, 14], [31, 14], [31, 5]]
        upper_poly = [[26, 5], [26, 14], [36, 14], [36, 5]]
        idf.add_block("upper", upper_poly, 10)
        idf.translate((0, 0, 10))
        idf.add_block("lower", lower_poly, 10)
        expected_surface_count = 12
        assert len(idf.idfobjects["BUILDINGSURFACE:DETAILED"]) == expected_surface_count
        idf.intersect_match()
        new_expected_surface_count = 14
        assert (
            len(idf.idfobjects["BUILDINGSURFACE:DETAILED"])
            == new_expected_surface_count
        )
        # check outside boundary condition of roof
        adjacency_count = 0
        for obj in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
            if obj.Outside_Boundary_Condition == "surface":
                adjacency_count += 1
        assert adjacency_count == 2


@pytest.mark.xfail("sys.version_info.major == 3 and sys.version_info.minor == 5")
def test_real_scale():
    # type: () -> None
    """Test building, intersecting and matching from a real building footprint."""
    iddfhandle = StringIO(iddcurrent.iddtxt)
    if IDF.getiddname() == None:
        IDF.setiddname(iddfhandle)

    idf = IDF(StringIO("Version, 8.5;"))
    poly1 = [
        (526492.65, 185910.65),
        (526489.05, 185916.45),
        (526479.15, 185910.3),
        (526482.65, 185904.6),
        (526492.65, 185910.65),
    ]
    poly2 = [
        (526483.3, 185903.15),
        (526483.5, 185903.25),
        (526482.65, 185904.6),
        (526479.15, 185910.3),
        (526489.05, 185916.45),
        (526492.65, 185910.65),
        (526493.4, 185909.4),
        (526500, 185913.95),
        (526500.45, 185914.3),
        (526500, 185914.85),
        (526497.4, 185918.95),
        (526499.45, 185920.2),
        (526494.4, 185928.35),
        (526466.05, 185910.95),
        (526471.1, 185902.75),
        (526473.05, 185903.9),
        (526476.2, 185898.8),
        (526479.95, 185901.1),
        (526483.3, 185903.15),
    ]
    idf.add_block("small", poly1, 6.0, 2)
    idf.add_block("large", poly2, 5.0, 2)
    idf.translate_to_origin()
    idf.intersect_match()
    idf.set_wwr(0.25)
    walls = idf.getsurfaces("wall")
    # look for a wall which should have been split
    assert "Block large Storey 1 Wall 0003" not in [w.Name for w in walls]
    # look for another wall which should have been split
    assert "Block large Storey 1 Wall 0005" not in [w.Name for w in walls]
    # look for a wall which should be an internal wall
    wall = idf.getobject("BUILDINGSURFACE:DETAILED", "Block small Storey 1 Wall 0002_1")
    assert wall.Outside_Boundary_Condition != "outdoors"
    # look for another wall which should be an internal wall
    wall = idf.getobject("BUILDINGSURFACE:DETAILED", "Block large Storey 1 Wall 0003_2")
    assert wall.Outside_Boundary_Condition != "outdoors"

    walls = idf.getsurfaces("wall")
    # look for walls which are being incorrectly duplicated
    for s1, s2 in itertools.combinations(walls, 2):
        assert not almostequal(s1.coords, s2.coords), "Dupes: '{}' and '{}'".format(
            s1.Name, s2.Name
        )
