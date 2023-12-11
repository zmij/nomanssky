import sys
import os
import logging

from typing import Iterable

root_dir = "/".join(os.path.abspath(__file__).split("/")[:-2])
sys.path.append(root_dir)

from nomanssky._items import Item as MockItem, Class

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


async def mock_get_resource_items(item_ids: Iterable[str], *args, **kwargs):
    return [MockItem(url=x, cls=Class.Resource) for x in item_ids]
