from pathlib import Path

import pytest

from derivgen.library import read_library
from derivgen.tcl import read_tcl_file

ROOT = Path(__file__).parent.parent
MEMORY = ROOT / "memory"


@pytest.fixture(scope="session")
def library():
    return read_library(MEMORY / "ip_library")


@pytest.fixture
def parent():
    return read_tcl_file(MEMORY / "platforms" / "derivsense.tcl")
