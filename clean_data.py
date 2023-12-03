#!/usr/bin/env python3

import logging
import nms

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


wiki = nms.Wiki()
wiki.drop_tables()
