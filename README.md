<p align="center">
  <img src="glyph/artie.png" alt="Artie" width="96" height="96">
</p>

<h1 align="center">Artie</h1>

<p align="center">
  <strong>Art scraper for Anbernic devices running MuOS</strong>
</p>

<p align="center">
  <a href="https://github.com/milouk/artie/releases/latest"><img src="https://img.shields.io/github/v/release/milouk/artie?style=flat-square&color=d4881c" alt="Release"></a>
  <a href="https://github.com/milouk/artie/blob/main/LICENSE"><img src="https://img.shields.io/github/license/milouk/artie?style=flat-square" alt="License"></a>
  <a href="https://github.com/milouk/artie/releases/latest"><img src="https://img.shields.io/github/downloads/milouk/artie/total?style=flat-square&color=d4881c" alt="Downloads"></a>
  <a href="https://screenscraper.fr/"><img src="https://img.shields.io/badge/API-ScreenScraper-blue?style=flat-square" alt="ScreenScraper"></a>
</p>

<p align="center">
  <img src="screenshots/artie_new_emulators.png" alt="Systems" width="32%">
  <img src="screenshots/artie_new_roms.png" alt="ROMs" width="32%">
  <img src="screenshots/artie_new_progress.png" alt="Progress" width="32%">
</p>

---

## Features

### Scraping & Media

- Scrape box art, previews, and screenshots from [ScreenScraper](https://screenscraper.fr/) with region priority
- Fetch metadata for each ROM — genre, developer, publisher, player count, and release date
- Localized synopsis support with configurable language
- Scrape a single ROM, all ROMs in a system, or every system at once
- Apply custom PNG masks as overlays on box art and previews
- Choose from multiple media types: `mixrbv2`, `box-2D`, `box-3D`, `ss`, `marquee`

### Performance

- Multi-threaded scraping with configurable thread count
- Connection pooling and API response caching for faster repeat runs
- Smart thread limits — automatically respects your ScreenScraper API tier

### Interface

- Dark UI with amber accent theme and fully configurable color palette
- System logos displayed inline in the emulator list
- ROM detail view showing box art, preview, and synopsis at a glance
- Progress bar with ETA and cancel support during batch scrapes
- Filter to hide already-scraped ROMs and focus on what's left

### Device & Data

- OTA updates — check for new versions and apply them without leaving the app (auto-restarts)
- Backup your entire catalogue (art, previews, text) to SD2 for safekeeping
- Delete media per-ROM or per-system to free up space
- Configurable log levels for easy troubleshooting

## Quick Start

1. Download `Artie.muxapp` from the [latest release](https://github.com/milouk/artie/releases/latest)
2. Copy it to `/mnt/mmc/MUOS/application/` on your device
3. Edit `Artie/.artie/config.json` with your [ScreenScraper](https://screenscraper.fr/) credentials and ROM paths
4. Launch from the MuOS applications menu

## Controls

### Systems Screen

| Button | Action |
|--------|--------|
| D-pad | Navigate systems |
| A | Select system |
| X | Delete system media |
| START | Scrape all systems |
| SELECT | Backup to SD2 |
| Y | Update (when available) |
| L1/R1 | Page jump |
| L2/R2 | Jump by 100 |
| MENU | Exit |

### ROMs Screen

| Button | Action |
|--------|--------|
| D-pad | Navigate ROMs |
| A | Scrape selected ROM |
| X | Delete ROM media |
| Y | ROM detail view |
| B | Back to systems |
| START | Scrape all ROMs |
| L1/R1 | Page jump |
| L2/R2 | Jump by 100 |
| MENU | Exit |

### ROM Detail Screen

| Button | Action |
|--------|--------|
| A | Scrape ROM |
| B | Back |

## Configuration

```json
{
  "roms": "/mnt/sdcard/ROMS",
  "logos": "assets/logos",
  "show_logos": true,
  "log_level": "info",
  "colors": {
    "primary": "#d4881c",
    "primary_dark": "#a06210",
    "secondary": "#1e1e2e",
    "secondary_light": "#2a2a3c",
    "secondary_dark": "#14141e"
  },
  "screenscraper": {
    "username": "your_username",
    "password": "your_password",
    "threads": 10,
    "show_scraped_roms": true,
    "content": {
      "synopsis": { "enabled": true, "lang": "en" },
      "box": {
        "enabled": true,
        "type": "mixrbv2",
        "height": 240,
        "width": 320,
        "apply_mask": false,
        "mask_path": "assets/masks/box_mask.png",
        "resize_mask": true
      },
      "preview": {
        "enabled": true,
        "type": "ss",
        "height": 275,
        "width": 515,
        "apply_mask": false,
        "mask_path": "assets/masks/preview_mask.png",
        "resize_mask": true
      },
      "regions": ["us", "eu", "jp", "wor"]
    },
    "systems": [
      {
        "dir": "SNES",
        "id": "4",
        "name": "Super Nintendo (SNES)",
        "box": "/mnt/mmc/MUOS/info/catalogue/Nintendo SNES-SFC/box/",
        "preview": "/mnt/mmc/MUOS/info/catalogue/Nintendo SNES-SFC/preview/",
        "synopsis": "/mnt/mmc/MUOS/info/catalogue/Nintendo SNES-SFC/text/"
      }
    ]
  }
}
```

### Key Options

| Option | Description |
|--------|-------------|
| `roms` | Path to ROMs directory |
| `show_logos` | Show system logos in list |
| `colors` | UI color theme |
| `threads` | Concurrent scraping threads |
| `show_scraped_roms` | Show already-scraped ROMs |
| `content.*.type` | Media type (`mixrbv2`, `box-2D`, `box-3D`, `ss`, `marquee`) |
| `content.*.apply_mask` | Enable mask overlay |
| `content.regions` | Region priority for artwork |
| `systems[].dir` | ROM directory name |
| `systems[].id` | ScreenScraper system ID |

## Image Masks

Apply custom PNG overlays to box art and previews. Masks must be PNG with an alpha channel.

```json
"box": {
  "apply_mask": true,
  "mask_path": "assets/masks/box_mask.png",
  "resize_mask": true
}
```

Set `resize_mask: true` to auto-fit mask dimensions to artwork.

## Troubleshooting

Check the log file first:

```
/mnt/mmc/MUOS/application/Artie/.artie/log.txt
```

| Problem | Solution |
|---------|----------|
| Won't start | Verify `config.json` format and file paths |
| Scraping fails | Check ScreenScraper credentials and internet connection |
| Media missing | Check storage space and file permissions |
| Masks not applying | Ensure `apply_mask: true` and mask file exists at `mask_path` |

## Contributing

1. Fork the repo
2. Create a feature branch
3. Submit a pull request

Bug reports welcome on the [issues page](https://github.com/milouk/artie/issues) — include log excerpts and device info.

## License

[MIT](LICENSE)
