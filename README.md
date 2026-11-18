# rulesets

**English** | [Русский](README.ru.md)

Filtering and routing rules kept in one place: all lists live in [`rules.yaml`](rules.yaml),
and CI builds every client format from it into the [`release`](../../tree/release) branch.

| Format | Contents | Client → file in `release` |
|---|---|---|
| sing-box binary rule-set `.srs` | domains and IP subnets | [sing-box](https://sing-box.sagernet.org) (any) → `sing-box/<list>.srs`<br>[Karing](https://github.com/KaringX/karing) (Android, iOS, Windows, macOS, Linux) → same file<br>[Throne](https://github.com/throneproj/Throne), [NekoBox](https://github.com/qr243vbi/nekobox) load it by link |
| sing-box rule-set source `.json` (version 3) | the same, human-readable | [sing-box](https://sing-box.sagernet.org) → `sing-box/<list>.json` |
| Throne route-profile link `throne://route/…` | profile with links to the `.srs` files | [Throne](https://github.com/throneproj/Throne) (Windows, Linux, macOS) → `throne/selective.txt` |
| Throne remote-routes link `throne://remoteroute/…` | one-step subscription to the profile above | [Throne](https://github.com/throneproj/Throne) → `throne/selective.remoteroute.txt` |
| NekoBox / Throne simple rules `ruleset:<link>` | `.srs` links, one line per list | [NekoBox](https://github.com/qr243vbi/nekobox) (Windows, Linux) → `nekobox/desktop-<action>.txt` |
| v2ray-style routing lines `domain:` / CIDR | domains and IP subnets to paste by hand | [NekoBox for Android](https://github.com/MatsuriDayo/NekoBoxForAndroid) (Android) → `nekobox/android-<action>.domains.txt`, `….ips.txt` |
| plain list `.lst` | one domain or IPv4 subnet per line | [podkop](https://github.com/itdoginfo/podkop) (OpenWrt) → `podkop/all-<action>.domains.lst`, `….subnets.lst` |
| P2P with CIDR `.p2p.txt` (`label:CIDR`) | IP filter, IPv4 and IPv6 | [Tixati](https://www.tixati.com) (Windows, Linux) → `tixati/all-block.txt` |
| PeerGuardian P2P `.p2p` (`label:start-end`) | IP filter, IPv4 and IPv6 | [qBittorrent](https://www.qbittorrent.org), [qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) (Windows, Linux, macOS) → `qbittorrent/ipfilter.p2p` |
| Peer ID filter: wildcard / PCRE | Peer ID prefixes of spy clients | [Tixati](https://www.tixati.com) → `tixati/peerid-filter.txt` (`-XX0001-*`)<br>[qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) → `qbittorrent/peer_blacklist.txt` (`^-XX0001- .*`) |
| PowerShell script `.ps1` | updates the IP filter and the Peer ID list | [qBittorrent](https://www.qbittorrent.org), [qBittorrent Enhanced](https://github.com/c0re100/qBittorrent-Enhanced-Edition) (Windows) → `qbittorrent/update-ipfilter.ps1` |
| URL list `.txt` | links to external `.srs` (`ruleset:` entries) | [Karing](https://github.com/KaringX/karing), [sing-box](https://sing-box.sagernet.org), [podkop](https://github.com/itdoginfo/podkop) → `external/all-<action>.txt` |
| CIDR list `.txt`, `.json`, `.csv` | expanded `asn`/`country`/`continent`, rule-set map, origin-AS report | for review, not for clients → `resolved/`, `review.csv` |

The full list of files with links is in `README.md` and `index.json` on the `release` branch.

## Quick start

Copy a link, paste it into the client. All links point to the `release` branch and always serve the latest build.

### podkop (OpenWrt)

LuCI → **Services → Podkop**. Lists update on podkop's own schedule.

1. Add a section with connection type **Block** → *Remote subnet lists*:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/podkop/all-block.subnets.lst
   ```
2. In your **Proxy** section → *Remote domain lists*:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/podkop/all-proxy.domains.lst
   ```
3. Save & Apply.

IPv6 is not exported to podkop: its subnet lists accept IPv4 only.

### Throne

**One step:** copy this link, open the routes manager in Throne and press **Import** — it reads the clipboard,
asks for confirmation and adds a remote, auto-updating profile:
```
throne://remoteroute/aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL0dlc3VnYW8tc2FuL3J1bGVzZXRzL3JlbGVhc2UvdGhyb25lL3NlbGVjdGl2ZS50eHQjR2VzdSUyMHNlbGVjdGl2ZQ==
```
**By hand:** add a **remote** route profile with the URL below and enable auto-update:
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/throne/selective.txt
```

On every update Throne overwrites the rules of a remote profile — keep personal rules in a separate local profile.
Throne fetches GitHub links through jsDelivr, so changes arrive with a cache delay.
Pasting `throne/selective.txt` itself into **Import** creates a one-off local copy that does not update.

### NekoBox (desktop)

Routing settings → route of the needed outbound (Block / Proxy) → paste the lines from:
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/desktop-block.txt
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/desktop-proxy.txt
```
Each line is `ruleset:<.srs link>`; NekoBox downloads the rule-sets itself, so updates arrive automatically.

### NekoBox for Android

NekoBox for Android has no remote rule-sets — only its bundled `geoip:`/`geosite:`. Rules are pasted as text and are **not** updated automatically:
Route → new rule → *domain* field: lines from the first file, *IP* field: lines from the second, outbound Block / Proxy.
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/android-proxy.domains.txt
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/nekobox/android-block.ips.txt
```
Re-paste after changes. Large lists (countries, continents) are impractical here.

### Karing

Diversion rules → **Add New Diversion Group** → paste a `.srs` link and save → Custom Diversion Group → select the group and set its action.
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/sing-box/p2p-spies.srs
```
```
https://raw.githubusercontent.com/Gesugao-san/rulesets/release/sing-box/ru-extra.srs
```
The same steps on every platform. Karing's own docs warn that `.srs` files over 3 MB may exceed memory limits on Android and iOS — keep country and continent lists in mind.

### Tixati

1. **IP Filter** (castle wall icon on the toolbar) → **Add** → source URL, then set an auto-reload interval:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/tixati/all-block.txt
   ```
2. **Settings → Peers → Client Filter → Peer ID** → "never allow": add each line of
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/tixati/peerid-filter.txt
   ```
   Tixati has no import for this filter, so lines are added by hand.

### qBittorrent / qBittorrent Enhanced (Windows)

qBittorrent cannot load a filter from a URL, so a script keeps it updated.

1. Download the script and run it once in PowerShell:
   ```powershell
   iwr https://raw.githubusercontent.com/Gesugao-san/rulesets/release/qbittorrent/update-ipfilter.ps1 -OutFile "$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1"
   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1"
   ```
   Plain qBittorrent: add `-SkipPeerBlacklist` to the second command.
2. qBittorrent → **Options → Connection → IP Filtering** → enable, and paste this path into the file dialog:
   ```
   %LOCALAPPDATA%\qBittorrent\rulesets-ipfilter.p2p
   ```
3. Daily update via Task Scheduler (run once):
   ```powershell
   $a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$env:LOCALAPPDATA\qBittorrent\update-ipfilter.ps1`""
   Register-ScheduledTask -TaskName 'rulesets qBittorrent' -Action $a -Trigger (New-ScheduledTaskTrigger -Daily -At 4:20)
   ```

Enhanced reads `peer_blacklist.txt` only at startup: restart qBittorrent after an update (the script exits with code 2 and never touches the process).
The script never creates `peer_whitelist.txt`: if that file exists, Enhanced lets through only the peers listed in it.

### Pinning a build

Every build that changes `release` is also tagged `build-YYYY-MM-DD-N` (N is the CI run number).
To pin a client to a build or roll back, use `/<tag>/` instead of `/release/` in the link.
Throne profiles inside a tag still load `.srs` from the `release` branch.

Each tag also gets a [GitHub Release](../../releases) with every file attached separately (folder becomes a prefix:
`podkop/all-block.subnets.lst` → `podkop.all-block.subnets.lst`). The 30 newest releases are kept; older tags stay.

The `release` branch has its own `README.md` and `README.ru.md` with direct links to every file.

## Editing

1. Edit `rules.yaml` (the GitHub web editor is fine).
2. Open a PR — CI runs validation and tests but publishes nothing.
3. After merging into `main`, CI builds and pushes `release`.

Entry kinds: `domain`, `ip`, `peerid`, `asn`, `country`, `continent`. The `example` list at the end of `rules.yaml` shows each of them;
it has `enabled: false`, so it is validated on every build but never published.

The build fails if `rules.yaml` contains:

- a private/reserved range or a subnet with host bits set;
- a domain deeper than the second level without `sld_exception: <reason>`;
- an entry in a `block` list without `evidence`;
- a Peer ID longer than 8 characters (Enhanced compares only the first 8) or with a space;
- duplicates or a subnet nested in another one;
- a Throne profile referencing a list that does not exist or is disabled;
- a private/reserved AS number, an unknown country or continent code;
- an `asn`/`country`/`continent` entry expanding to more prefixes than its `max_prefixes`
  (defaults: 16 / 20000 / 200000) — so a broad block is always a deliberate choice.

Locally:

```sh
pip install pyyaml
python3 tools/build.py --out dist                      # without .srs
python3 tools/build.py --out dist --sing-box sing-box  # with .srs
python3 -m unittest tools/test_build.py -v
```

## When a build runs

| Event | Condition | Result |
|---|---|---|
| Push to `main` | `rules.yaml`, `tools/**`, `clients/**` or `.github/workflows/build.yml` changed | tests, build, publish |
| Pull request | the same paths changed | tests and build only, nothing is published |
| Schedule | daily at 00:00 UTC (scheduled runs may start a few minutes late) | tests, build, publish — prefixes behind `asn`/`country`/`continent` change without edits |
| Manual | **Run workflow** on the Actions tab | tests, build, publish |

Changes to `README.md`, `README.ru.md` or `.gitignore` alone do not start a build.
A publish that changes nothing in `release` creates no commit, no tag and no GitHub Release.

## Data sources

`asn`, `country` and `continent` entries are expanded at build time; results are saved in `release/resolved/` so every change is visible as a diff.

| Entry | Source | Notes |
|---|---|---|
| `asn` | [RIPEstat announced-prefixes](https://stat.ripe.net/docs/data-api/api-endpoints/announced-prefixes) (RIPE NCC) | BGP data from RIS collectors worldwide, not only the RIPE region. Only prefixes still announced at the end of the 2-week window are taken |
| `country` | [RIPEstat country-resource-list](https://stat.ripe.net/docs/data-api/api-endpoints/country-resource-list) | Built from RIR delegation stats: the country of **registration**, not where addresses are used (not geolocation) |
| `continent` | [GeoNames](https://www.geonames.org/) countryInfo ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), snapshot in [`tools/data/continents.json`](tools/data/continents.json) | Country → continent, then each country as above. GeoNames puts Russia in `EU` and Turkey in `AS` |

If RIPEstat is unreachable, the previous snapshot from `release` is reused with a warning; with no snapshot the build fails rather than publish an empty list.
CI also rebuilds daily, because prefixes change without edits to `rules.yaml`.

`release/review.csv` lists every `ip` entry with the announced prefix covering it, its origin AS
([RIPEstat prefix-overview](https://stat.ripe.net/docs/data-api/api-endpoints/prefix-overview)) and how many prefixes that AS announces.
It only informs: whether a small, dedicated AS deserves an `asn` entry is decided by hand. A failed lookup is a warning, not a build failure.

## What is not here and why

- **Peer ID filtering for podkop and Throne** — only IPs and domains are visible at the network level.
- **Blocking whole hosting providers** (AWS, IONOS, NFOrce, SoftLayer, Contabo): the evidence varies in
  strength, and NFOrce, for example, also hosts real seedboxes. Every entry requires `evidence`.
