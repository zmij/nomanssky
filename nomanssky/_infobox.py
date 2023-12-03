import bs4

from typing import Dict

from ._attributes import get_type, get_rarity


def class_name_filter(cls: str):
    def filter(tag: bs4.Tag):
        return tag.has_attr("class") and cls in tag.get("class")

    return filter


class Infobox:
    KEY_TYPES = {
        "type": get_type,
        "blueprint_value": lambda s: float(s.replace(",", "")),
        "total_value": lambda s: float(s.replace(",", "")),
        "used_for": lambda s: s.split(", "),
        "rarity": get_rarity,
    }
    name: str
    image: str
    symbol: str
    type: str

    def __init__(self, tag: bs4.Tag) -> None:
        self.name = None
        self.image = None
        self.type = None

        rows = tag.find_all("tr")
        for r in rows:
            res = Infobox.parse_row(r)
            for k, v in res.items():
                k = k.replace(" ", "_")
                v = Infobox.transform_value(k, v)
                setattr(self, k, v)

    @property
    def has_symbol(self) -> bool:
        return hasattr(self, "symbol")

    def __str__(self) -> str:
        val = self.name
        if self.has_symbol:
            val = val + f" ({self.symbol})"
        return f"<{val}>"

    def __repr__(self) -> str:
        val = self.name
        if self.has_symbol:
            val = val + f" ({self.symbol})"
        return f"<{self.type}: {val}>"

    @staticmethod
    def parse_row(tag: bs4.Tag) -> Dict[str, str]:
        th = tag.find("th")
        if th is None:
            return {}
        td = tag.find("td")
        if td is None:
            # Either box name or image
            if th.has_attr("class") and "infoboxname" in th.get("class"):
                return {"name": th.string.strip()}
            else:
                img = th.find(class_name_filter("image"))
                if img:
                    return {"image": img.get("href")}
        else:
            key = th.string.strip().lower().replace("\xa0", " ")
            value = ""
            if td.string is not None:
                value = td.string.strip()
            elif key == "symbol":
                value = td.find("b").string.strip()
            elif key in ["blueprint value", "total value"]:
                value = str(td.contents[0]).strip()
            else:
                value = str(td.contents).strip()
            return {key: value}
        return {}

    @staticmethod
    def transform_value(key: str, value: str):
        if key in Infobox.KEY_TYPES:
            return Infobox.KEY_TYPES[key](value)
        return value
