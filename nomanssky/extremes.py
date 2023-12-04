from enum import Enum

from ._coords import GalacticCoords


class Extremes(Enum):
    """
    These are the values from https://nomanssky.fandom.com/wiki/Portal_address#Extreme_Coordinates
    They might result in erroneous teleports
    """

    UPPER_POLE = GalacticCoords("10017F000000")
    NEAR_CENTRE = GalacticCoords("100104005005")
    LOWER_POLE = GalacticCoords("100180000000")

    NORTH_POLE_GALACTIC_PLANE = GalacticCoords("100100800000")
    EAST_POLE_GALACTIC_PLANE = GalacticCoords("1001000007FF")
    SOUTH_POLE_GALACTIC_PLANE = GalacticCoords("1001007FF000")
    WEST_POLE_GALACTIC_PLANE = GalacticCoords("100100000800")

    ALPHA_SPIRAL_MAJORIS = GalacticCoords("10017F800800")
    ALPHA_SPIRAL_GALACTIC_PLANE = GalacticCoords("100100800800")
    ALPHA_SPIRAL_MINORIS = GalacticCoords("100181800800")

    BETA_SPIRAL_MAJORIS = GalacticCoords("10017F8007FF")
    BETA_SPIRAL_GALACTIC_PLANE = GalacticCoords("1001008007FF")
    BETA_SPIRAL_MINORIS = GalacticCoords("1001818007FF")

    GAMMA_SPIRAL_MAJORIS = GalacticCoords("10017F7FF800")
    GAMMA_SPIRAL_GALACTIC_PLANE = GalacticCoords("1001007FF800")
    GAMMA_SPIRAL_MINORIS = GalacticCoords("1001817FF800")

    DELTA_SPIRAL_MAJORIS = GalacticCoords("10017F7FF7FF")
    DELTA_SPIRAL_GALACTIC_PLANE = GalacticCoords("1001007FF7FF")
    DELTA_SPIRAL_MINORIS = GalacticCoords("1001817FF7FF")
