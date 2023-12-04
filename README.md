# nomanssky
No Man's Sky Python 3 library

The library uses [No Man's Sky Wiki](https://nomanssky.fandom.com/wiki/) as 
the primary information source, parses the pages and stores information in a 
database. The library doesn't request pages from wiki if item is found in the
database.

To crawl the entire wiki there is a script `crawl.py`, it requires a single
argument of an item to start with. `Oxygen` is fine for a start. It takes about
1:30 on my iternet connection and about 1200 requests to wiki server.

The library was initially created to calculate BOMs (Bills Of Material) to craft 
different items in No Man's Sky. 

## Top-level scripts

* `booster2portal.py` - convert [Signal Booster](https://nomanssky.fandom.com/wiki/Signal_Booster) code to [Portal Address](https://nomanssky.fandom.com/wiki/Portal_address)
* `portal2booster.py` - convert [Portal Address](https://nomanssky.fandom.com/wiki/Portal_address) to [Signal Booster](https://nomanssky.fandom.com/wiki/Signal_Booster) code
* `xyz.py` - parse [Portal Address](https://nomanssky.fandom.com/wiki/Portal_address) or [Signal Booster](https://nomanssky.fandom.com/wiki/Signal_Booster) code and print a string compatible with [Coordinate Plotting App](https://nomanssky.fandom.com/wiki/Coordinate_Plotting_App)
* `decode_coords.py` - decode a coord string (portal address, signal booster code or galactical coords) and print out Portal code, Galactic coords, XYZ, X, Y, Z, Star system and planet.
* `crawl.py` - parse Wiki and store data to databse. Won't request items that are already in database.
* `parse_page.py` - load a page from Wiki, parse it and store to the db.
* `clean_data.py` - clear the database. Might be required with the future releases if database scheme changes.
* `formula.py` - print the formula tree for an item (to be reworked to graph traversal).
* `bom.py` - print BOM for an item.
* `graph.py` - build a visual dependency graph for an item.
* `f.py` - formula graph traversal tool, for debug purposes.
* `load_page.py` - mostly a debug script to async load a wiki page and dump it's contents.

You can always call any script with `-h` argument to see what input it expects.

## Libary usage

### Coordinate parsing and conversion

```python
from nomanssky import GalacticGoords

# Booster code
coords = GalacticCoords(code="HUKYA:046A:0081:0D6D:0038")
# -- or --
# Galactic coords
coords = GalacticCoords(code="046A:0081:0D6D:0038")
# -- or ---
# Portal code
coords = GalacticCoords(code="00380256EC6B")

print(f"X: {coords.x} Y: {coords.y} Z: {coords.z}")
print(f"Star system: {coords.star_system}")
print(f"Planet index: {coords.planet}")

```

## Dependencies

Standard python modules:
* argparse (for top-level scripts)
* logging (throughout the library)
* asyncio (for async http reqeusts)
* sqlite3 (for internal database)
* typing
* enum
* os

Apart from the python's standard library the library uses the following libs:
* aiohttp (for async http reqeusts)
* bs4 (for page parsing)
* pyvis (used in `graph.py` to create a visualisation of dependency graph)

There are a couple of modules in the library that are somewhat utility stuff
(terminal coloring, database helpers and graph traversal). Those modules might
be later moved out if they prove mature.

## Disclaimer

This code is not covered with tests (yet), so a number of bugs can still be 
there. Feel free to create an issue if you are not happy with something, but
don't expect that I will be very fast to fix it.
