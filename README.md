# rulesets

**English** | [Русский](README.ru.md)

A single source of filtering and routing rules. Edit **only** [`rules.yml`](rules.yml);
everything else is built by CI and published to the [`release`](../../tree/release) branch.

| Client | What is built | Where in `release` |
|---|---|---|
| podkop (OpenWrt) | `.lst`: domains and IPv4 subnets, per list and aggregated per action | `podkop/` |
| sing-box | rule-set `.json` (version 3) and `.srs` | `sing-box/` |
| Throne | remote route profile `throne://route/…` | `throne/` |
| Tixati | IP filter `label:CIDR` (IPv4 and IPv6), Peer ID filter | `tixati/` |
| qBittorrent | IP filter `ipfilter.p2p`, update script | `qbittorrent/` |
| qBittorrent Enhanced | all of the above + `peer_blacklist.txt` (Peer ID) | `qbittorrent/` |

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

1. Routing settings → add a **remote** route profile, URL:
   ```
   https://raw.githubusercontent.com/Gesugao-san/rulesets/release/throne/selective.txt
   ```
2. Enable auto-update and select the profile.

On every update Throne overwrites the rules of a remote profile — keep personal rules in a separate local profile.
Throne fetches GitHub links through jsDelivr, so changes arrive with a cache delay.

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

The `release` branch has its own `README.md` and `README.ru.md` with direct links to every file.

## Editing

1. Edit `rules.yml` (the GitHub web editor is fine).
2. Open a PR — CI runs validation and tests but publishes nothing.
3. After merging into `main`, CI builds and pushes `release`.

The build fails if `rules.yml` contains:

- a private/reserved range or a subnet with host bits set;
- a domain deeper than the second level without `sld_exception: <reason>`;
- an entry in a `block` list without `evidence`;
- a Peer ID longer than 8 characters (Enhanced compares only the first 8) or with a space;
- duplicates or a subnet nested in another one;
- a Throne profile referencing a list that does not exist.

Locally:

```sh
pip install pyyaml
python3 tools/build.py --out dist                      # without .srs
python3 tools/build.py --out dist --sing-box sing-box  # with .srs
python3 -m unittest tools/test_build.py -v
```

## What is not here and why

- **Peer ID filtering for podkop and Throne** — only IPs and domains are visible at the network level.
- **Blocking whole hosting providers** (AWS, IONOS, NFOrce, SoftLayer, Contabo): the evidence varies in
  strength, and NFOrce, for example, also hosts real seedboxes. Every entry requires `evidence`.
