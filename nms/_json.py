import json

from typing import Any, Tuple, List

_TO_JSON = "__to_json__"
_FROM_JSON = "__from_json__"


class JSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if hasattr(o, _TO_JSON):
            fn = getattr(o, _TO_JSON)
            return fn()
        return super().default(o)


class JSONDecoder:
    @classmethod
    def loads(cls, s: str, idx: int = 0, decoder: json.JSONDecoder = None) -> Any:
        if decoder is None:
            decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(s, idx)

        return cls.from_json(data)

    @classmethod
    def load_list(cls, s: str, decoder: json.JSONDecoder = None) -> List[Any]:
        if decoder is None:
            decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(s, 0)
        return [cls.from_json(x) for x in data]

    @classmethod
    def from_json(cls, data: Any) -> Any:
        if not hasattr(cls, _FROM_JSON):
            return data

        o = cls.__new__(cls)
        super(cls, o).__init__()
        return cls.__from_json__(o, data)
