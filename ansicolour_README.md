# ANSI colour

This is a small python library for colourising your terminal output.

Basic usage:

```python
from ansicolour import highlight as hl, Colour, CLEAR

print(hl("Hello colours!", fg="red", bg="blue"))
print(f"{Colour.RED + (Colour.YELLOW + 'bg')}Hello colours in an f-string!{CLEAR}")
```
