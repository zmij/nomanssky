#!/usr/bin/env python3

import logging
import nomanssky

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)-8s - %(levelname)-7s - %(message)s",
)


wiki = nomanssky.Wiki()
wiki.drop_tables()
