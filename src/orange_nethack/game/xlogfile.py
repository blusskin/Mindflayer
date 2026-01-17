"""Parser for Nethack xlogfile format.

The xlogfile is a tab-separated file where each line represents a completed game.
Each field is in the format key=value, separated by tabs or colons depending on
the nethack variant.

Example line (tab-separated):
version=3.6.6	points=1234	deathdnum=0	deathlev=1	maxlvl=1	hp=-1	maxhp=12	deaths=1	deathdate=20240115	birthdate=20240115	uid=1000	role=Val	race=Hum	gender=Fem	align=Neu	name=player	death=killed by a jackal	conduct=0x0	turns=100	achieve=0x0	realtime=60	starttime=1705312345	endtime=1705312400	gender0=Fem	align0=Neu	flags=0x0

"""
import logging
from pathlib import Path
from typing import Iterator

from orange_nethack.models import XlogEntry

logger = logging.getLogger(__name__)


def parse_xlogfile_line(line: str) -> XlogEntry | None:
    """Parse a single line from an xlogfile into an XlogEntry.

    Handles both tab-separated and colon-separated formats.
    Returns None if the line cannot be parsed.
    """
    line = line.strip()
    if not line:
        return None

    # Determine separator - try tab first, then colon
    if "\t" in line:
        fields = line.split("\t")
    else:
        # Colon-separated is trickier because values can contain colons
        # We need to parse key=value pairs
        fields = []
        current = ""
        in_value = False
        for char in line:
            if char == ":" and not in_value:
                if current:
                    fields.append(current)
                current = ""
            elif char == "=":
                in_value = True
                current += char
            else:
                current += char
                # Reset in_value at end of field
                if char == ":" and in_value:
                    # This might be part of the value, keep going
                    pass
        if current:
            fields.append(current)

        # Fallback: simple split
        if not fields or not any("=" in f for f in fields):
            fields = line.split(":")

    # Parse key=value pairs into dict
    data: dict[str, str] = {}
    for field in fields:
        if "=" not in field:
            continue
        key, _, value = field.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            data[key] = value

    if not data:
        return None

    # Convert to XlogEntry
    try:
        entry = XlogEntry(
            version=data.get("version"),
            points=int(data.get("points", 0)),
            deathdnum=int(data["deathdnum"]) if "deathdnum" in data else None,
            deathlev=int(data["deathlev"]) if "deathlev" in data else None,
            maxlvl=int(data["maxlvl"]) if "maxlvl" in data else None,
            hp=int(data["hp"]) if "hp" in data else None,
            maxhp=int(data["maxhp"]) if "maxhp" in data else None,
            deaths=int(data["deaths"]) if "deaths" in data else None,
            deathdate=data.get("deathdate"),
            birthdate=data.get("birthdate"),
            uid=int(data["uid"]) if "uid" in data else None,
            role=data.get("role"),
            race=data.get("race"),
            gender=data.get("gender"),
            align=data.get("align"),
            name=data.get("name", ""),
            death=data.get("death", ""),
            conduct=data.get("conduct"),
            turns=int(data.get("turns", 0)),
            achieve=data.get("achieve"),
            realtime=int(data["realtime"]) if "realtime" in data else None,
            starttime=int(data["starttime"]) if "starttime" in data else None,
            endtime=int(data["endtime"]) if "endtime" in data else None,
            gender0=data.get("gender0"),
            align0=data.get("align0"),
            flags=data.get("flags"),
        )
        return entry
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse xlogfile line: {e}")
        return None


def parse_xlogfile(path: Path) -> Iterator[XlogEntry]:
    """Parse an entire xlogfile, yielding XlogEntry objects."""
    if not path.exists():
        return

    with open(path, "r") as f:
        for line in f:
            entry = parse_xlogfile_line(line)
            if entry:
                yield entry


def get_last_entry(path: Path) -> XlogEntry | None:
    """Get the most recent entry from the xlogfile."""
    if not path.exists():
        return None

    last_entry = None
    for entry in parse_xlogfile(path):
        last_entry = entry
    return last_entry


def tail_xlogfile(path: Path, last_position: int = 0) -> tuple[list[XlogEntry], int]:
    """Read new entries from xlogfile since last_position.

    Returns (list of new entries, new position).
    """
    if not path.exists():
        return [], 0

    entries = []
    with open(path, "r") as f:
        f.seek(last_position)
        for line in f:
            entry = parse_xlogfile_line(line)
            if entry:
                entries.append(entry)
        new_position = f.tell()

    return entries, new_position


class XlogfileWatcher:
    """Watch an xlogfile for new entries."""

    def __init__(self, path: Path):
        self.path = path
        self.position = 0
        self._initialize_position()

    def _initialize_position(self) -> None:
        """Set position to end of file."""
        if self.path.exists():
            with open(self.path, "r") as f:
                f.seek(0, 2)  # Seek to end
                self.position = f.tell()

    def get_new_entries(self) -> list[XlogEntry]:
        """Get new entries since last check."""
        entries, new_position = tail_xlogfile(self.path, self.position)
        self.position = new_position
        return entries

    def reset(self) -> None:
        """Reset position to end of file."""
        self._initialize_position()
