from enum import Enum


class Symbols(Enum):
    RECYCLE = "♻️"
    HAMMER = "🔨"
    PICK = "⛏️"
    SPANNER = "🔧"
    HAMMER_AND_PICK = "⚒️"
    HAMMER_AND_SPANNER = "🛠️"
    AXE = "🪓"
    TEST_TUBE = "🧪"
    THERMOMETER = "🌡️"
    ALEMBIC = "⚗️"
    SCREWDRIVER = "🪛"

    def __str__(self) -> str:
        return self.value
