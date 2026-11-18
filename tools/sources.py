"""Expands ASN, country and continent entries into IP prefixes.

Data sources:
  - ASN → prefixes: RIPEstat "announced-prefixes" (RIPE NCC, BGP data from RIS
    collectors worldwide). Only prefixes still announced at the end of the query
    window are taken.
  - Country → prefixes: RIPEstat "country-resource-list", built from the RIR
    delegation statistics. It reflects the country of REGISTRATION, not where
    the addresses are actually used.
  - Continent → countries: GeoNames countryInfo snapshot in tools/data/continents.json
    (CC BY 4.0), then each country as above.
  - Rule-set name → .srs URL: Throne's built-in catalog (throneproj/routeprofiles,
    branch rule-set, srslist.h), so `ruleset: geosite-youtube` means exactly what it
    means in Throne. Explicit https URLs ending in .srs are used as is.

Every expansion is saved to the release branch (resolved/*.txt). If RIPEstat is
unreachable, the previous snapshot is reused with a warning; with no snapshot the
build fails, because publishing an empty list would silently lift a block.
"""

from __future__ import annotations

import ipaddress
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

RIPESTAT = "https://stat.ripe.net/data/{endpoint}/data.json"
# RIPEstat asks heavy users to identify themselves.
SOURCE_APP = "gesugao-rulesets"
CONTINENTS_FILE = Path(__file__).resolve().parent / "data/continents.json"
RULESET_CATALOG = "https://raw.githubusercontent.com/throneproj/routeprofiles/rule-set/srslist.h"
CATALOG_ENTRY_RE = re.compile(r'\{"([^"]+)",\s*"(https://[^"]+)"')

Network = ipaddress.IPv4Network | ipaddress.IPv6Network
Fetcher = Callable[[str, dict], dict]


class SourceError(Exception):
  """A data source could not deliver and there is no snapshot to fall back on."""


def http_fetch(endpoint: str, params: dict) -> dict:
  """Calls a RIPEstat data API endpoint and returns its "data" object."""
  query = urllib.parse.urlencode({**params, "sourceapp": SOURCE_APP})
  url = f"{RIPESTAT.format(endpoint=endpoint)}?{query}"
  with urllib.request.urlopen(url, timeout=60) as resp:
    payload = json.load(resp)
  if payload.get("status") != "ok":
    raise SourceError(f"RIPEstat {endpoint}: status {payload.get('status')}")
  return payload["data"]


def http_text(url: str) -> str:
  """Downloads a text file (the rule-set catalog)."""
  with urllib.request.urlopen(url, timeout=60) as resp:
    return resp.read().decode("utf-8")


def load_continents() -> dict:
  """GeoNames snapshot: {"continents": {code: name}, "countries": {cc: continent}}."""
  return json.loads(CONTINENTS_FILE.read_text(encoding="utf-8"))


def parse_prefixes(values) -> list[Network]:
  """Turns strings into networks, dropping anything that is not a global prefix."""
  nets = []
  for value in values:
    try:
      net = ipaddress.ip_network(str(value), strict=False)
    except ValueError:
      continue
    if net.is_global:
      nets.append(net)
  return nets


class Resolver:
  """Resolves entries via RIPEstat with a cache and a snapshot fallback."""

  def __init__(self, fetch: Fetcher = http_fetch, snapshot_dir: Path | None = None, fetch_text: Callable[[str], str] = http_text):
    self.fetch = fetch
    self.fetch_text = fetch_text
    self.catalog: dict[str, str] | None = None
    # Rule-set names actually used in this build → URL; saved as resolved/rulesets.json.
    self.rulesets: dict[str, str] = {}
    self.snapshot_dir = snapshot_dir
    self.continents = load_continents()
    self.cache: dict[str, list[Network]] = {}
    self.sizes: dict[int, int] = {}
    self.warnings: list[str] = []

  # ------------------------------------------------------------ fetchers

  def _asn(self, asn: int) -> list[Network]:
    data = self.fetch("announced-prefixes", {"resource": f"AS{asn}"})
    end = data.get("query_endtime", "")
    # Keep only prefixes whose latest timeline reaches the end of the window: still announced.
    live = [p["prefix"] for p in data.get("prefixes", []) if any(t.get("endtime") == end for t in p.get("timelines", []))]
    return parse_prefixes(live)

  def _country(self, cc: str) -> list[Network]:
    data = self.fetch("country-resource-list", {"resource": cc, "v4_format": "prefix"})
    res = data.get("resources", {})
    return parse_prefixes(res.get("ipv4", []) + res.get("ipv6", []))

  def _continent(self, code: str) -> list[Network]:
    countries = sorted(cc for cc, cont in self.continents["countries"].items() if cont == code)
    nets: list[Network] = []
    for cc in countries:
      nets += self.resolve("country", cc)
    return nets

  # ------------------------------------------------------------ review

  def origin(self, net: Network) -> dict:
    """Announced prefix covering `net` and its origin ASes (RIPEstat prefix-overview)."""
    data = self.fetch("prefix-overview", {"resource": str(net)})
    return {
      "prefix": data.get("resource", ""),
      "announced": bool(data.get("announced")),
      "asns": [(a["asn"], a.get("holder", "")) for a in data.get("asns", [])],
    }

  def as_size(self, asn: int) -> int:
    """Number of prefixes an AS announces; kept apart from the blocking cache."""
    if asn not in self.sizes:
      self.sizes[asn] = len(self._asn(asn))
    return self.sizes[asn]

  # ------------------------------------------------------------ public

  def key(self, kind: str, value) -> str:
    """Snapshot key, also the file name under resolved/: AS216158, country-CN, continent-EU."""
    keys = {"asn": lambda: f"AS{value}", "country": lambda: f"country-{value}", "continent": lambda: f"continent-{value}"}
    return keys[kind]()

  def resolve(self, kind: str, value) -> list[Network]:
    """Prefixes for an entry, collapsed; falls back to the snapshot when the source fails."""
    key = self.key(kind, value)
    if key in self.cache:
      return self.cache[key]
    fetchers = {"asn": lambda: self._asn(int(value)), "country": lambda: self._country(value), "continent": lambda: self._continent(value)}
    try:
      nets = fetchers[kind]()
    except Exception as exc:  # network, HTTP, JSON: all handled the same way
      nets = self._from_snapshot(key, exc)
    nets = collapse(nets)
    self.cache[key] = nets
    return nets

  def _from_snapshot(self, key: str, exc: Exception) -> list[Network]:
    path = self.snapshot_dir / "resolved" / f"{key}.txt" if self.snapshot_dir else None
    if not path or not path.exists():
      raise SourceError(f"{key}: source failed ({exc}) and there is no previous snapshot") from None
    self.warnings.append(f"{key}: source failed ({exc}); reused the previous snapshot")
    return parse_prefixes(path.read_text(encoding="utf-8").split())


  # ------------------------------------------------------------ rule-sets

  def _load_catalog(self) -> dict[str, str]:
    if self.catalog is not None:
      return self.catalog
    try:
      self.catalog = dict(CATALOG_ENTRY_RE.findall(self.fetch_text(RULESET_CATALOG)))
      if not self.catalog:
        raise SourceError("the rule-set catalog is empty")
    except Exception as exc:
      path = self.snapshot_dir / "resolved" / "rulesets.json" if self.snapshot_dir else None
      if not path or not path.exists():
        raise SourceError(f"rule-set catalog failed ({exc}) and there is no previous snapshot") from None
      self.warnings.append(f"rule-set catalog failed ({exc}); reused the previous snapshot")
      self.catalog = json.loads(path.read_text(encoding="utf-8"))
    return self.catalog

  def ruleset_url(self, value: str) -> str:
    """URL of a rule-set: as given for https links, from Throne's catalog for names."""
    if value.startswith("https://"):
      return value
    url = self._load_catalog().get(value)
    if not url:
      raise SourceError(f"rule-set '{value}' is not in Throne's catalog ({RULESET_CATALOG})")
    self.rulesets[value] = url
    return url


def collapse(nets: list[Network]) -> list[Network]:
  """Merges adjacent and nested prefixes, IPv4 first, then IPv6."""
  out: list[Network] = []
  for version in (4, 6):
    out += ipaddress.collapse_addresses(n for n in nets if n.version == version)
  return out
