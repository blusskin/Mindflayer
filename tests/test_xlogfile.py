"""Tests for xlogfile parsing."""
import tempfile
from pathlib import Path

import pytest

from orange_nethack.game.xlogfile import (
    XlogfileWatcher,
    parse_xlogfile,
    parse_xlogfile_line,
    tail_xlogfile,
)


class TestParseXlogfileLine:
    def test_parse_tab_separated(self):
        line = "version=3.6.6\tpoints=1234\tname=player\tdeath=killed by a jackal\tturns=100"
        entry = parse_xlogfile_line(line)

        assert entry is not None
        assert entry.version == "3.6.6"
        assert entry.points == 1234
        assert entry.name == "player"
        assert entry.death == "killed by a jackal"
        assert entry.turns == 100
        assert entry.score == 1234
        assert not entry.ascended

    def test_parse_ascension(self):
        line = "version=3.6.6\tpoints=999999\tname=winner\tdeath=ascended\tturns=50000"
        entry = parse_xlogfile_line(line)

        assert entry is not None
        assert entry.ascended
        assert entry.score == 999999

    def test_parse_escaped_death(self):
        line = "version=3.6.6\tpoints=100\tname=player\tdeath=killed by a soldier ant, while helpless\tturns=50"
        entry = parse_xlogfile_line(line)

        assert entry is not None
        assert entry.death == "killed by a soldier ant, while helpless"

    def test_parse_empty_line(self):
        entry = parse_xlogfile_line("")
        assert entry is None

    def test_parse_whitespace_line(self):
        entry = parse_xlogfile_line("   \n")
        assert entry is None

    def test_parse_full_entry(self):
        line = (
            "version=3.6.6\tpoints=5000\tdeathdnum=0\tdeathlev=5\tmaxlvl=7\t"
            "hp=-3\tmaxhp=42\tdeaths=1\tdeathdate=20240115\tbirthdate=20240115\t"
            "uid=1000\trole=Val\trace=Hum\tgender=Fem\talign=Neu\t"
            "name=testplayer\tdeath=killed by a gnome lord\t"
            "conduct=0x0\tturns=2500\tachieve=0x0\trealtime=1800\t"
            "starttime=1705312345\tendtime=1705314145\t"
            "gender0=Fem\talign0=Neu\tflags=0x0"
        )
        entry = parse_xlogfile_line(line)

        assert entry is not None
        assert entry.version == "3.6.6"
        assert entry.points == 5000
        assert entry.deathdnum == 0
        assert entry.deathlev == 5
        assert entry.maxlvl == 7
        assert entry.hp == -3
        assert entry.maxhp == 42
        assert entry.deaths == 1
        assert entry.role == "Val"
        assert entry.race == "Hum"
        assert entry.gender == "Fem"
        assert entry.align == "Neu"
        assert entry.name == "testplayer"
        assert entry.turns == 2500
        assert entry.realtime == 1800


class TestParseXlogfile:
    def test_parse_multiple_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xlog") as f:
            f.write("version=3.6.6\tpoints=100\tname=player1\tdeath=died\tturns=50\n")
            f.write("version=3.6.6\tpoints=200\tname=player2\tdeath=died\tturns=100\n")
            f.write("version=3.6.6\tpoints=300\tname=player3\tdeath=ascended\tturns=150\n")
            path = Path(f.name)

        try:
            entries = list(parse_xlogfile(path))
            assert len(entries) == 3
            assert entries[0].name == "player1"
            assert entries[1].name == "player2"
            assert entries[2].name == "player3"
            assert entries[2].ascended
        finally:
            path.unlink()

    def test_parse_nonexistent_file(self):
        entries = list(parse_xlogfile(Path("/nonexistent/file.xlog")))
        assert entries == []


class TestTailXlogfile:
    def test_tail_from_start(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xlog") as f:
            f.write("version=3.6.6\tpoints=100\tname=player1\tdeath=died\tturns=50\n")
            f.write("version=3.6.6\tpoints=200\tname=player2\tdeath=died\tturns=100\n")
            path = Path(f.name)

        try:
            entries, pos = tail_xlogfile(path, 0)
            assert len(entries) == 2
            assert pos > 0
        finally:
            path.unlink()

    def test_tail_from_middle(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xlog") as f:
            f.write("version=3.6.6\tpoints=100\tname=player1\tdeath=died\tturns=50\n")
            first_pos = f.tell()
            f.write("version=3.6.6\tpoints=200\tname=player2\tdeath=died\tturns=100\n")
            path = Path(f.name)

        try:
            entries, pos = tail_xlogfile(path, first_pos)
            assert len(entries) == 1
            assert entries[0].name == "player2"
        finally:
            path.unlink()


class TestXlogfileWatcher:
    def test_watcher_initial_position(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xlog") as f:
            f.write("version=3.6.6\tpoints=100\tname=player1\tdeath=died\tturns=50\n")
            path = Path(f.name)

        try:
            watcher = XlogfileWatcher(path)
            # Should start at end of file
            entries = watcher.get_new_entries()
            assert entries == []
        finally:
            path.unlink()

    def test_watcher_detects_new_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".xlog") as f:
            f.write("version=3.6.6\tpoints=100\tname=player1\tdeath=died\tturns=50\n")
            path = Path(f.name)

        try:
            watcher = XlogfileWatcher(path)

            # Add new entry
            with open(path, "a") as f:
                f.write("version=3.6.6\tpoints=200\tname=player2\tdeath=died\tturns=100\n")

            entries = watcher.get_new_entries()
            assert len(entries) == 1
            assert entries[0].name == "player2"

            # No new entries
            entries = watcher.get_new_entries()
            assert entries == []
        finally:
            path.unlink()
