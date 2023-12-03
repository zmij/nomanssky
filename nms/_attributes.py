import logging

from enum import Enum
from typing import Any, Dict
from collections import defaultdict

__all__ = ["Rarity", "Type", "Class"]


class MissingValueEnum(Enum):
    seen_missing: Dict[str, int]

    @classmethod
    def _missing_(cls, value: object) -> Any:
        errata = getattr(cls, "_errata_", {})
        if value in errata:
            return errata[value]
        seen = getattr(cls, "seen_missing", defaultdict(int))
        if value not in seen:
            logger = logging.getLogger(cls.__name__)
            log_level = getattr(cls, "_log_level_", logging.WARNING)
            if logger.isEnabledFor(log_level):
                logger._log(log_level, f"Unknown {cls.__name__} value `{value}`", [])
            setattr(cls, "seen_missing", seen)
        seen[value] += 1
        return cls.UNKNOWN


MissingValueEnum._log_level_ = logging.DEBUG


class Rarity(MissingValueEnum):
    Common = "common"
    Uncommon = "uncommon"
    Rare = "rare"
    VeryRare = "very rare"
    UNKNOWN = "unknown"

    def compare(self, other) -> int:
        if self.__class__ == other.__class__:
            items = [m for m in self.__class__.__members__.values()]
            self_idx = items.index(self)
            other_idx = items.index(other)
            if self_idx < other_idx:
                return -1
            elif self_idx > other_idx:
                return 1
            return 0
        raise NotImplementedError()

    def __lt__(self, other):
        return self.compare(other) < 0

    def __le__(self, other):
        return self.compare(other) <= 0

    def __gt__(self, other):
        return self.compare(other) > 0

    def __ge__(self, other):
        return self.compare(other) >= 0


def get_rarity(value: str) -> Rarity:
    return Rarity(value.lower())


class Type(MissingValueEnum):
    UNKNOWN = "Unknown"

    KEY = "Key"

    RES_LEE = "Localised Earth Element"
    RES_CLF = "Concentrated Liquid Fuel"
    RES_VAM = "Valuable Asteroid Mineral"
    RES_CM = "Compressed Mineral"
    RES_HES = "High Energy Substance"
    RES_UCE = "Unrefined Catalytic Element"
    RES_RCE = "Refined Catalytic Element"
    RES_RSM = "Refined Stellar Metal"
    RES_PMM = "Processed Metallic Minerals"

    TM = "Transmuted Metal"

    HB = "Herbivore Bait"
    RE = "Raw Ingredient"
    EP = "Edible Product"

    # Exosuit stuff
    EES = "Exosuit Environmental Shielding"

    # Exocraft stuff
    MSA = "Minotaur Scan Attachment"
    EPS = "Exocraft Power System"
    HDU = "Humboldt Drive Upgrade"

    # Multitool stuff
    MU = "Multitool Upgrade"

    # Weapons
    EPW = "Energy Projectile Weapon"

    # Starship stuff
    SEW = "Starship Energy Weapon"
    CRSW = "Close Range Starship Weapon"
    PCU = "Photon Cannon Upgrade"
    BJU = "Blaze Javelin Upgrade"

    # Portable devices
    PMD = "Portable Mining Device"
    PSU = "Portable Sustenance Unit"

    # Buildings
    BLD_CM = "Construction Module"
    BLD_PDM = "Power Distribution Module"
    BLD_ARU = "Automated Refinery Unit"
    BLD_REF = "Refiner"
    CCC = "Concrete Construction Component"

    DECO = "Decoration"
    COMPONENT = "Component"

    # Freighter stuff
    SMTD = "Ship-Mounted Teleportation Device"

    # Junk
    JUNK = "Junk"
    SS = "Starship Subcomponent"

    # WTF?
    FOL = "Fragment Of Life"
    GENUS = "Genus"
    PE = "Precious/Exotic"
    RCG = "Recessive Creature Genes"
    UVC = "Unique Valuable Curiosity"
    HLSB = "Heavy Loader Storage Bay"
    RPS = "Remote Planet Scanner"
    VTD = "Vehicle Translocation Device"
    AGC = "Autonomous Gas Compressor"
    SDMTD = "Short-Distance Matter Transfer Device"
    CN = "Compressed Nutrients"
    TT = "Trade Terminal"
    ARL = "Auto-Regenerating Lifeform"
    HRT = "Highly Refined Technology"
    GI = "Glassy Indeterminance"

    AAF = "Advanced Agricultural Product"
    ACP = "Advanced Crafted Product"


Type._log_level_ = logging.DEBUG


def get_type(value: str) -> Type:
    value = value.split(":")[0]
    return Type(value.title())


class Class(MissingValueEnum):
    UNKNOWN = "Unknown"

    Resource = "resource"
    Product = "product"
    Tech = "technology"
    Tradeable = "tradeable"
    Plant = "plant"
    TradeableItem = "tradeable item"
    Component = "component"
    Consumable = "consumable"
    ConsumableProduct = "consumable product"
    FuelSource = "fuel source"
    CustomisationPart = "customisation part"
    CookingIngredient = "cooking ingredient"
    FarmableProduct = "farmable product"
    FarmableAgricultureProduct = "farmable agricultural product"
    IndoorFarmingItem = "item used in indoor farming"

    Terminal = "terminal"

    ResearchItem = "item used for research"

    ConstructedTech = "constructed technology"

    TechType = "type of technology"

    EnergyTech = "energy technology"
    UpgradeTech = "upgrade technology"

    Curiosity = "curiosity"
    CuriosityProduct = "curiosity product"

    ExosuitTech = "exosuit technology"
    ExosuitHealthTech = "exosuit health technology"
    ExosuitTechType = "type of exosuit technology"
    ExosuitUtilClass = "class of exosuit utilities"
    ExosuitUpgrageType = "type of exosuit upgrade"
    ExosuitUpgrade = "exosuit upgrade"

    ExocraftTech = "exocraft technology"
    ExocraftUpgrade = "exocraft upgrade"

    MultiToolUpgrade = "multi-tool upgrade"
    MultiToolComponent = "multi-tool component"
    MultiToolCoreComponent = "core component of the multi-tool"
    MultiToolBlueprint = "multi-tool blueprint"
    MultiToolTech = "multi-tool technology"

    PortableBaseBuildingProduct = "portable base building product"

    BuildableTech = "buildable technology"
    BaseBuildingStructure = "base building structure"
    BaseBuildingComponent = "base building component"
    BaseBuildingProduct = "base building product"
    BaseBuildingModule = "base building module"
    BaseBuildingConstructedTechnology = "base building constructed technology"
    BaseBuildingItem = (
        "item used for creating specific objects for use in base building"
    )
    DecorationBuildingPart = "decoration building part"

    StarshipTech = "starship technology"
    StarshipWeaponsTech = "weapons technology for the starship"
    StarshipPropulsion = "starship propulsion method"
    StarshipUpgrade = "starship upgrade"
    StarshipWeapon = "starship weapon"
    StarshipShieldTech = "shield technology for the starship"
    StarshipInteriorAdornment = "starship interior adornment"
    StarshipEnhancement = "starship enhancement"

    FreighterTech = "freighter technology"

    BlaseJavelinUpgrade = "upgrade for the blaze javelin"
    TimeLoopTool = "tool for locating time loops"

    Messenger = "means of leaving brief messages for other players"


Class._errata_ = {
    "base-building component": Class.BaseBuildingComponent,
    "base-building product": Class.BaseBuildingProduct,
    "component of the multi-tool": Class.MultiToolComponent,
    "upgrade for the multi-tool": Class.MultiToolUpgrade,
    "an exocraft upgrade": Class.ExocraftUpgrade,
}

"""
base building product and can be used to mark locations on planets

"""


def get_class(value: str) -> Class:
    classes = value.lower().split(" and ")

    for s in classes:
        cls = Class(s.strip())
        if cls != Class.UNKNOWN:
            return cls
    return Class(value.lower())
