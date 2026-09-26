"""Run the suite while denying connections to real active and historical DBs."""

import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname


def main():
    root = Path(__file__).resolve().parents[1]
    protected = {(root / "var/orbitai.db").resolve(), (root / "orbitai.db").resolve()}

    def guard(event, args):
        if event != "sqlite3.connect" or str(args[0]) == ":memory:":
            return
        value = str(args[0])
        if value.startswith("file:"):
            value = url2pathname(urlsplit(value).path)
        if Path(value).resolve() in protected:
            raise RuntimeError("Tests must not connect to the active or historical database")

    sys.addaudithook(guard)
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    raise SystemExit(main())
