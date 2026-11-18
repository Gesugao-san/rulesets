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

## Usage

Below, `$R` = `https://raw.githubusercontent.com/Gesugao-san/rulesets/release`.

### podkop

Aggregated files pick up new lists automatically, no router reconfiguration needed.

- Section with connection type **Block** → `remote_subnet_lists`: `$R/podkop/all-block.subnets.lst`
- Section **Proxy** → `remote_domain_lists`: `$R/podkop/all-proxy.domains.lst`

IPv6 is not exported to podkop: its subnet `.lst` accepts IPv4 only (CI shows a warning in the run summary).

### Throne

Routes → new **remote** profile → URL `$R/throne/selective.txt`, enable auto-update.

On every update Throne overwrites the rules of a remote profile — keep personal rules in a separate local profile.
Throne rewrites `raw.githubusercontent.com` links to jsDelivr, so changes arrive with a cache delay.

### Tixati

- **IP Filter** icon → Add → URL `$R/tixati/all-block.txt`, set an auto-reload interval.
- Settings → Peers → Client Filter → **Peer ID** tab → "never allow": one line each from `$R/tixati/peerid-filter.txt` (manually, Tixati has no import).

### qBittorrent / qBittorrent Enhanced

qBittorrent cannot load a filter from a URL, so a script keeps it updated:

```powershell
.\update-ipfilter.ps1                      # Enhanced: ipfilter + peer_blacklist
.\update-ipfilter.ps1 -SkipPeerBlacklist   # plain qBittorrent
```

Point qBittorrent to the filter once: Options → Connection → IP Filtering → path
`%LOCALAPPDATA%\qBittorrent\gesu-ipfilter.p2p`. A Task Scheduler example is in the script header.

Enhanced reads `peer_blacklist.txt` only at startup, so a restart is needed after an update
(the script signals this with exit code 2 and never touches the process). The script never creates
`peer_whitelist.txt`: if that file exists, Enhanced lets through only the peers listed in it.

## What is not here and why

- **Peer ID filtering for podkop and Throne** — only IPs and domains are visible at the network level.
- **Blocking whole hosting providers** (AWS, IONOS, NFOrce, SoftLayer, Contabo): the evidence varies in
  strength, and NFOrce, for example, also hosts real seedboxes. Every entry requires `evidence`.
