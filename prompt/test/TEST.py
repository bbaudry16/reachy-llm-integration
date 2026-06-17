from librairy import load_library
from pathlib import Path

lib = load_library()
print("Library path:", Path("poses_library.json").absolute())
print("Arms:", len(lib["arms"]))
print("First arm:", lib["arms"][0] if lib["arms"] else "EMPTY")