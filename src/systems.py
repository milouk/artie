"""Static system mapping for Artie Scraper.

Maps ROM directory name -> (screenscraper_id, display_name, catalogue_name).

Catalogue name is used to derive muOS paths:
  box:      {CATALOGUE_BASE}/{catalogue}/box/
  preview:  {CATALOGUE_BASE}/{catalogue}/preview/
  synopsis: {CATALOGUE_BASE}/{catalogue}/text/

Users can override or add entries by dropping a `systems.json` next to
their `settings.json`. See README ("Custom systems") for the format.
"""

import json
from pathlib import Path
from typing import Optional

from defaults import CATALOGUE_BASE
from logger import LoggerSingleton as logger

# fmt: off
SYSTEMS = {
    "ADVMAME": ("75", "Mame", "ADVMAME"),
    "AMIGA": ("64", "Commodore Amiga", "AMIGA"),
    "AMIGACD": ("134", "Commodore Amiga CD", "AMIGACD"),
    "AMIGACDTV": ("129", "Commodore Amiga CD", "AMIGACDTV"),
    "ARCADE": ("75", "Mame", "Arcade"),
    "ARDUBOY": ("263", "Arduboy", "Arduboy"),
    "ATARI2600": ("26", "Atari 2600", "Atari 2600"),
    "ATARI5200": ("40", "Atari 5200", "Atari 5200"),
    "ATARI7800": ("41", "Atari 7800", "Atari 7800"),
    "ATARI800": ("43", "Atari 800", "ATARI800"),
    "ATARIST": ("42", "Atari ST", "Atari ST-STE-TT-Falcon"),
    "ATOMISWAVE": ("53", "Atomiswave", "Sega Atomiswave Naomi"),
    "C64": ("66", "Commodore 64", "Commodore C64"),
    "CHANNELF": ("80", "Fairchild Channel F", "CHANNELF"),
    "COLECO": ("183", "ColecoVision", "ColecoVision"),
    "COLSGM": ("183", "ColecoVision SGM", "COLSGM"),
    "CPC": ("65", "Amstrad CPC", "Amstrad"),
    "CPET": ("240", "Commodore PET", "Commodore PET"),
    "CPLUS4": ("99", "Commodore Plus 4", "CPLUS4"),
    "CPS1": ("6", "Capcom Play System", "Arcade"),
    "CPS2": ("7", "Capcom Play System 2", "Arcade"),
    "CPS3": ("8", "Capcom Play System 3", "Arcade"),
    "DAPHNE": ("49", "Daphne", "DAPHNE"),
    "DC": ("23", "Dreamcast", "Sega Dreamcast"),
    "DOS": ("135", "DOS", "DOS"),
    "EASYRPG": ("231", "EasyRPG", "EASYRPG"),
    "EBK": ("93", "EBK", "EBK"),
    "FBA2012": ("75", "FBA2012", "FBA2012"),
    "FBALPHA": ("75", "FBAlpha", "FBALPHA"),
    "FBNEO": ("", "FBNeo", "FBNEO"),
    "FDS": ("106", "Famicom Disk System", "FDS"),
    "GB": ("9", "Game Boy", "Nintendo Game Boy"),
    "GBA": ("12", "Game Boy Advance", "Nintendo Game Boy Advance"),
    "GBC": ("10", "Game Boy Color", "Nintendo Game Boy Color"),
    "GG": ("21", "Sega Game Gear", "Sega Game Gear"),
    "GW": ("52", "Game & Watch", "Handheld Electronic - Game and Watch"),
    "INTELLIVISION": ("115", "Intellivision", "Mattel - Intellivision"),
    "JAGUAR": ("27", "Atari Jaguar", "Atari Jaguar"),
    "LOWRESNX": ("244", "LowRes NX", "Lowres NX"),
    "LUTRO": ("206", "Lutro", "LUTRO"),
    "LYNX": ("28", "Atari Lynx", "Atari Lynx"),
    "MAME": ("75", "MAME", "Arcade"),
    "MAME2003PLUS": ("75", "MAME 2003+", "MAME2003PLUS"),
    "MAME2010": ("75", "MAME 2010", "MAME2010"),
    "MBA": ("75", "MBA", "MBA"),
    "MDMSU": ("1", "Mega Drive Hacks", "Sega Mega Drive - Genesis"),
    "MEGADRIVE": ("1", "Mega Drive / Genesis", "Sega Mega Drive - Genesis"),
    "MEGADUCK": ("90", "Megaduck", "MEGADUCK"),
    "MS": ("2", "Sega Master System", "Sega Master System"),
    "MSX": ("113", "MSX", "Microsoft - MSX"),
    "MSX2": ("116", "MSX2", "MSX2"),
    "N64": ("14", "Nintendo 64", "Nintendo N64"),
    "N64DD": ("122", "Nintendo 64DD", "Nintendo N64 -DD"),
    "NAOMI": ("56", "Sega Naomi", "Sega Atomiswave Naomi"),
    "NDS": ("15", "Nintendo DS", "Nintendo DS"),
    "NEOCD": ("70", "Neo Geo CD", "SNK Neo Geo CD"),
    "NEOGEO": ("142", "Neo Geo", "SNK Neo Geo"),
    "NES": ("3", "NES / Famicom", "Nintendo NES-Famicom"),
    "NGC": ("13", "Nintendo GameCube", "Nintendo GameCube"),
    "NGP": ("25", "Neo Geo Pocket", "SNK Neo Geo Pocket - Color"),
    "NGPC": ("82", "Neo Geo Pocket Color", "SNK Neo Geo Pocket - Color"),
    "ODYSSEY": ("104", "Magnavox Odyssey 2", "ODYSSEY"),
    "OPENBOR": ("214", "OpenBOR", "OPENBOR"),
    "PALMOS": ("219", "Palm OS", "Palm OS"),
    "PANASONIC": ("29", "3DO", "PANASONIC"),
    "PC88": ("221", "NEC PC-8801", "NEC PC-8000 - PC-8800 series"),
    "PC98": ("208", "NEC PC-9801", "NEC PC98"),
    "PCE": ("31", "TurboGrafx-16 / PC Engine", "NEC PC Engine"),
    "PCECD": ("114", "TurboGrafx-CD", "NEC PC Engine CD"),
    "PCFX": ("72", "NEC PC-FX", "NEC PC-FX"),
    "PICO": ("234", "PICO-8", "PICO-8"),
    "POKEMINI": ("211", "Pokemon Mini", "Nintendo Pokemon Mini"),
    "PORTS": ("138", "Ports", "PORTS"),
    "PS": ("57", "PlayStation", "Sony PlayStation"),
    "PSP": ("61", "PSP", "Sony Playstation Portable"),
    "PSPMINIS": ("172", "PSP Minis", "PSPMINIS"),
    "SATELLAVIEW": ("107", "Satellaview", "SATELLAVIEW"),
    "SATURN": ("22", "Sega Saturn", "Sega Saturn"),
    "SCUMMVM": ("123", "ScummVM", "ScummVM"),
    "SEGA32X": ("19", "Sega 32X", "Sega 32X"),
    "SEGACD": ("20", "Sega CD", "Sega Mega CD - Sega CD"),
    "SFCMSU": ("4", "SNES Hacks", "Nintendo SNES-SFC"),
    "SFX": ("105", "PC Engine SuperGrafx", "SFX"),
    "SG1000": ("109", "Sega SG-1000", "SG1000"),
    "SGB": ("127", "Super Game Boy", "SGB"),
    "SNES": ("4", "Super Nintendo", "Nintendo SNES-SFC"),
    "SUFAMI": ("108", "Sufami Turbo", "SUFAMI"),
    "THOMSON": ("141", "Thomson", "THOMSON"),
    "TIC": ("222", "TIC-80", "TIC-80"),
    "UZEBOX": ("216", "Uzebox", "Uzebox"),
    "VB": ("11", "Virtual Boy", "Nintendo Virtual Boy"),
    "VECTREX": ("102", "Vectrex", "GCE-Vectrex"),
    "VIC20": ("73", "Commodore VIC-20", "Commodore VIC-20"),
    "VIDEOPAC": ("104", "Videopac", "VIDEOPAC"),
    "VIRCON32": ("272", "Vircon32", "Vircon32"),
    "VMU": ("23", "Dreamcast VMU", "VMU"),
    "WASM4": ("262", "WASM-4", "WASM-4"),
    "WONDERSWAN": ("45", "WonderSwan", "Bandai WonderSwan-Color"),
    "WONDERSWANCOLOR": ("46", "WonderSwan Color", "Bandai WonderSwan-Color"),
    "WS": ("207", "Watara Supervision", "Watara Supervision"),
    "WSC": ("207", "Watara Supervision", "Watara Supervision"),
    "X1": ("220", "Sharp X1", "Sharp X1"),
    "X68000": ("79", "Sharp X68000", "Sharp X68000"),
    "ZXEIGHTYONE": ("77", "Sinclair ZX-81", "Sinclair ZX 81"),
    "ZXS": ("76", "ZX Spectrum", "Sinclair ZX Spectrum"),
}
# fmt: on

# Alternate directory names that point at the same system. Keeps Artie
# working on devices where the user renamed folders or where a different
# muOS skin uses a different convention. Keys and values are compared
# lowercase in build_systems_mapping.
ALIASES = {
    # Sega
    "GENESIS": "MEGADRIVE",
    "MD": "MEGADRIVE",
    "SMD": "MEGADRIVE",
    "MASTERSYSTEM": "MS",
    "SMS": "MS",
    "GAMEGEAR": "GG",
    "DREAMCAST": "DC",
    "SEGACD-MCD": "SEGACD",
    "MEGACD": "SEGACD",
    "32X": "SEGA32X",
    "SEGASATURN": "SATURN",
    # Nintendo
    "FAMICOM": "NES",
    "SUPERNES": "SNES",
    "SUPERFAMICOM": "SNES",
    "SFC": "SNES",
    "GAMEBOY": "GB",
    "GAMEBOYCOLOR": "GBC",
    "GAMEBOYADVANCE": "GBA",
    "GBASP": "GBA",
    "NINTENDO64": "N64",
    "VIRTUALBOY": "VB",
    "NDSI": "NDS",
    # Sony
    "PLAYSTATION": "PS",
    "PSX": "PS",
    "PS1": "PS",
    "PSONE": "PS",
    "PSP1000": "PSP",
    # NEC / TurboGrafx
    "TG16": "PCE",
    "TURBOGRAFX": "PCE",
    "TURBOGRAFX16": "PCE",
    "PCENGINE": "PCE",
    "TGCD": "PCECD",
    "TG-CD": "PCECD",
    "TURBOGRAFXCD": "PCECD",
    # Atari
    "ATARIJAGUAR": "JAGUAR",
    "ATARILYNX": "LYNX",
    # SNK
    "NEOGEOPOCKET": "NGP",
    "NEOGEOPOCKETCOLOR": "NGPC",
    "GAMECUBE": "NGC",
    "NINTENDOGAMECUBE": "NGC",
    # Arcade
    "ARCADIA": "ARCADE",
    "FBA": "FBALPHA",
    "FBN": "FBNEO",
    # Misc
    "PICO8": "PICO",
    "TIC80": "TIC",
    "ZX81": "ZXEIGHTYONE",
    "ZXSPECTRUM": "ZXS",
    "SPECTRUM": "ZXS",
    "COMMODORE64": "C64",
    "AMSTRAD": "CPC",
    "AMSTRADCPC": "CPC",
    "MSX1": "MSX",
    "GAMEANDWATCH": "GW",
    "VIC-20": "VIC20",
    "PLUS4": "CPLUS4",
    "C-64": "C64",
}


def _make_entry(dir_name: str, sys_id: str, name: str, catalogue: str) -> dict:
    return {
        "dir": dir_name,
        "id": sys_id,
        "name": name,
        "box": f"{CATALOGUE_BASE}/{catalogue}/box/",
        "preview": f"{CATALOGUE_BASE}/{catalogue}/preview/",
        "synopsis": f"{CATALOGUE_BASE}/{catalogue}/text/",
        "video": f"{CATALOGUE_BASE}/{catalogue}/video/",
    }


def _apply_user_overrides(mapping: dict, overrides_path: Path) -> None:
    """Merge user-supplied entries from systems.json into the mapping.

    Each top-level key is a folder name (e.g. "NGPC"); each value is a
    dict of fields to override or add. Recognised fields: `id`, `name`,
    `catalogue`. Anything missing falls back to the existing entry (or
    the folder name as a sensible default for new entries). This lets
    power users fix mappings without rebuilding the binary.
    """
    if not overrides_path.is_file():
        return
    try:
        with open(overrides_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.log_warning(f"Failed to read {overrides_path}: {e}")
        return
    if not isinstance(data, dict):
        logger.log_warning(f"{overrides_path}: expected a JSON object at top level")
        return

    applied = 0
    for raw_dir, fields in data.items():
        if not isinstance(fields, dict):
            logger.log_warning(f"{overrides_path}: skipping {raw_dir} (not an object)")
            continue
        dir_name = str(raw_dir)
        key = dir_name.lower()
        existing = mapping.get(key)
        sys_id = str(fields.get("id", existing["id"] if existing else "")).strip()
        name = str(fields.get("name", existing["name"] if existing else dir_name))
        catalogue = str(
            fields.get("catalogue", existing["dir"] if existing else dir_name)
        )
        if not sys_id:
            logger.log_warning(
                f"{overrides_path}: {dir_name} has no id and isn't a built-in system; skipping"
            )
            continue
        mapping[key] = _make_entry(dir_name, sys_id, name, catalogue)
        applied += 1

    if applied:
        logger.log_info(f"Applied {applied} system override(s) from {overrides_path}")


def build_systems_mapping(
    roms_path: Optional[str] = None,
    settings_dir: Optional[str] = None,
) -> dict:
    """Build the systems mapping dict compatible with the old config format.

    Returns a dict keyed by lowercase dir name, with each value containing
    id, name, dir, box, preview, and synopsis paths. Aliases (see ALIASES
    above) resolve to the same entry as their canonical name so users who
    renamed ROM folders still get matched.

    If `settings_dir` is provided and contains a `systems.json` file, its
    contents override or add to the built-in mapping.
    """
    mapping = {}
    for dir_name, (sys_id, name, catalogue) in SYSTEMS.items():
        if not sys_id:
            continue
        mapping[dir_name.lower()] = _make_entry(dir_name, sys_id, name, catalogue)

    # Register aliases — each points to the canonical entry's config but
    # keeps its own "dir" (so media is still written under the user's
    # folder name).
    for alias, canonical in ALIASES.items():
        canonical_key = canonical.lower()
        if canonical_key not in mapping:
            continue
        alias_key = alias.lower()
        if alias_key in mapping:
            # An alias that happens to also be a canonical system wins
            # against itself — don't overwrite a real entry.
            continue
        entry = dict(mapping[canonical_key])
        entry["dir"] = alias
        mapping[alias_key] = entry

    # User overrides last so they win over both built-ins and aliases.
    if settings_dir:
        _apply_user_overrides(mapping, Path(settings_dir) / "systems.json")

    return mapping
