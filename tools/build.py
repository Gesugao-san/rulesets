#!/usr/bin/env python3
"""rulesets builder: turns the single rules.yaml into files for every client.

Output (the --out directory, published by CI to the `release` branch):
  podkop/       <list>.domains.lst, <list>.subnets.lst, all-<action>.*.lst
  sing-box/     <list>.json (+ .srs when --sing-box is given)
  throne/       <profile>.txt — throne://route/... link for a remote profile
  tixati/       <list>.txt, all-block.txt, peerid-filter.txt
  qbittorrent/  ipfilter.p2p, peer_blacklist.txt (Enhanced), update-ipfilter.ps1
  index.json, README.md

  resolved/     <AS…|country-…|continent-…>.txt — prefixes behind asn/country/continent entries

Usage:
  python3 tools/build.py --rules rules.yaml --out dist [--sing-box /path/to/sing-box] [--snapshot prev-release]

asn/country/continent entries are expanded via RIPEstat (see tools/sources.py);
--snapshot points to a checkout of the previous release, used if RIPEstat is down.

Exit code 1 means rules.yaml has errors (nothing is written).
"""

from __future__ import annotations

import argparse
import base64
import ipaddress
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sources import Resolver, SourceError, load_continents

# Allowed list actions and what they become in Throne.
THRONE_ACTION = {
  "block": {"action": "reject"},
  "proxy": {"action": "route", "outbound": "proxy"},
  "direct": {"action": "route", "outbound": "direct"},
}
ENTRY_KINDS = ("domain", "ip", "peerid", "asn", "country", "continent")
# Entries expanded into prefixes at build time, with the default max_prefixes guard.
# The guard stops a too-broad entry (e.g. a hosting AS) from slipping in unnoticed.
SOURCE_KINDS = {"asn": 16, "country": 20_000, "continent": 200_000}
# ASNs that are never routed on the Internet: 0, AS_TRANS, documentation, private, last.
RESERVED_ASN = [(0, 0), (23456, 23456), (64496, 65551), (4_200_000_000, 4_294_967_295)]
CONTINENTS = load_continents()
LIST_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DOMAIN_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
# Peer ID: printable ASCII without spaces; Enhanced compares only the first 8 chars.
PEERID_RE = re.compile(r"^[\x21-\x7e]{1,8}$")
PEERID_MAX = 8
# Rule-set source version: podkop itself writes version 3, sing-box 1.11+ reads it.
SINGBOX_RULESET_VERSION = 3
REPO_ROOT = Path(__file__).resolve().parent.parent


class Yaml12Loader(yaml.SafeLoader):
  """SafeLoader with YAML 1.2 scalars: PyYAML follows YAML 1.1, where `NO`, `on`, `yes`
  become booleans (country: NO → False) and `0123` is octal (asn: 0123 → 83).
  Here only true/false are booleans and integers are always decimal."""


Yaml12Loader.yaml_implicit_resolvers = {
  first: [(tag, rx) for tag, rx in resolvers if tag not in ("tag:yaml.org,2002:bool", "tag:yaml.org,2002:int")]
  for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Yaml12Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
Yaml12Loader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?[0-9]+$"), list("-+0123456789"))
Yaml12Loader.add_constructor("tag:yaml.org,2002:int", lambda loader, node: int(loader.construct_scalar(node), 10))


class RulesError(Exception):
  """An error in rules.yaml: the build stops and nothing is published."""


@dataclass
class RuleList:
  """A single validated list from rules.yaml."""

  name: str
  action: str
  title: str
  domains: list[str] = field(default_factory=list)
  networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = field(default_factory=list)
  peerids: list[str] = field(default_factory=list)
  enabled: bool = True
  # (kind, value, max_prefixes) for asn/country/continent entries.
  sources: list[tuple[str, object, int]] = field(default_factory=list)
  resolved: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = field(default_factory=list)

  @property
  def all_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Explicit ip entries in their order, then resolved prefixes not already covered by them."""
    extra = [n for n in self.resolved if not any(n.version == e.version and n.subnet_of(e) for e in self.networks)]
    return self.networks + extra

  @property
  def ipv4(self) -> list[ipaddress.IPv4Network]:
    return [n for n in self.all_networks if n.version == 4]

  @property
  def ipv6(self) -> list[ipaddress.IPv6Network]:
    return [n for n in self.all_networks if n.version == 6]


# ---------------------------------------------------------------- validation


def check_domain(value: str, entry: dict, where: str) -> str:
  """Validates a domain; only the second level (SLD) is allowed by default."""
  domain = str(value).strip().lower().rstrip(".")
  labels = domain.split(".")
  if len(labels) < 2 or not all(DOMAIN_LABEL_RE.match(label) for label in labels):
    raise RulesError(f"{where}: '{value}' is not a valid domain")
  if labels[-1].isdigit():
    raise RulesError(f"{where}: '{value}' looks like an IP, use ip:")
  if len(labels) > 2 and not entry.get("sld_exception"):
    raise RulesError(f"{where}: '{value}' is deeper than the second level; add sld_exception: <reason>")
  return domain


def check_ip(value: str, where: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
  """Validates an address/subnet: no host bits set, not private or reserved."""
  try:
    net = ipaddress.ip_network(str(value).strip(), strict=True)
  except ValueError as exc:
    raise RulesError(f"{where}: '{value}' — {exc}") from None
  if not net.is_global:
    raise RulesError(f"{where}: '{value}' is a private/reserved range")
  return net


def check_peerid(value: str, where: str) -> str:
  """Validates a Peer ID prefix; a trailing asterisk is allowed and dropped."""
  peerid = str(value).strip()
  if peerid.endswith("*"):
    peerid = peerid[:-1]
  if "*" in peerid:
    raise RulesError(f"{where}: '{value}' — '*' is allowed only at the end")
  if len(peerid) > PEERID_MAX:
    raise RulesError(f"{where}: '{value}' is longer than {PEERID_MAX} chars — Enhanced would never match it")
  if not PEERID_RE.match(peerid):
    raise RulesError(f"{where}: '{value}' must be printable ASCII without spaces")
  return peerid


def check_asn(value, where: str) -> int:
  """Validates an AS number: 'AS123' or 123, publicly routable."""
  text = str(value).strip().upper().removeprefix("AS")
  if not text.isdigit():
    raise RulesError(f"{where}: '{value}' is not an AS number")
  asn = int(text)
  if any(lo <= asn <= hi for lo, hi in RESERVED_ASN):
    raise RulesError(f"{where}: AS{asn} is private/reserved")
  return asn


def check_country(value, where: str) -> str:
  """Validates an ISO 3166-1 alpha-2 country code known to GeoNames."""
  cc = str(value).strip().upper()
  if cc not in CONTINENTS["countries"]:
    raise RulesError(f"{where}: '{value}' is not an ISO 3166-1 alpha-2 country code")
  return cc


def check_continent(value, where: str) -> str:
  """Validates a GeoNames continent code."""
  code = str(value).strip().upper()
  if code not in CONTINENTS["continents"]:
    raise RulesError(f"{where}: '{value}' is not a continent code ({', '.join(CONTINENTS['continents'])})")
  return code


def check_max_prefixes(entry: dict, kind: str, where: str) -> int:
  """Reads the optional max_prefixes guard, falling back to the per-kind default."""
  value = entry.get("max_prefixes", SOURCE_KINDS[kind])
  if not isinstance(value, int) or isinstance(value, bool) or value < 1:
    raise RulesError(f"{where}: max_prefixes must be a positive integer")
  return value


def check_overlaps(rule_list: RuleList) -> None:
  """Rejects subnets nested in one another: almost always a typo."""
  for version in (4, 6):
    nets = sorted((n for n in rule_list.networks if n.version == version), key=lambda n: (n.network_address, n.prefixlen))
    for prev, cur in zip(nets, nets[1:]):
      if cur.subnet_of(prev):
        raise RulesError(f"lists.{rule_list.name}: {cur} is already inside {prev}")


def parse_entry(rule_list: RuleList, entry: dict, where: str) -> None:
  """Parses one entry and puts it into the matching field of the list."""
  if not isinstance(entry, dict):
    raise RulesError(f"{where}: an entry must be a mapping")
  kinds = [k for k in ENTRY_KINDS if k in entry]
  if len(kinds) != 1:
    raise RulesError(f"{where}: exactly one key of {', '.join(ENTRY_KINDS)} is required")
  kind = kinds[0]
  if rule_list.action == "block" and not entry.get("evidence"):
    raise RulesError(f"{where}: evidence is required in a block list")

  parsers = {
    "domain": lambda: rule_list.domains.append(check_domain(entry["domain"], entry, where)),
    "ip": lambda: rule_list.networks.append(check_ip(entry["ip"], where)),
    "peerid": lambda: rule_list.peerids.append(check_peerid(entry["peerid"], where)),
    "asn": lambda: rule_list.sources.append(("asn", check_asn(entry["asn"], where), check_max_prefixes(entry, "asn", where))),
    "country": lambda: rule_list.sources.append(("country", check_country(entry["country"], where), check_max_prefixes(entry, "country", where))),
    "continent": lambda: rule_list.sources.append(("continent", check_continent(entry["continent"], where), check_max_prefixes(entry, "continent", where))),
  }
  if "max_prefixes" in entry and kind not in SOURCE_KINDS:
    raise RulesError(f"{where}: max_prefixes applies only to {', '.join(SOURCE_KINDS)}")
  if kind == "peerid" and rule_list.action != "block":
    raise RulesError(f"{where}: peerid is allowed only in lists with action: block")
  parsers[kind]()


def parse_list(name: str, raw: dict) -> RuleList:
  """Validates a whole list: name, action, entries, duplicates, overlaps."""
  where = f"lists.{name}"
  if not LIST_NAME_RE.match(name):
    raise RulesError(f"{where}: list name must match [a-z0-9-]")
  if not isinstance(raw, dict):
    raise RulesError(f"{where}: a mapping was expected")
  action = raw.get("action")
  if action not in THRONE_ACTION:
    raise RulesError(f"{where}: action must be one of {', '.join(THRONE_ACTION)}")
  entries = raw.get("entries") or []
  if not entries:
    raise RulesError(f"{where}: the list is empty")

  enabled = raw.get("enabled", True)
  if not isinstance(enabled, bool):
    raise RulesError(f"{where}: enabled must be true or false")
  rule_list = RuleList(name=name, action=action, title=str(raw.get("title", name)), enabled=enabled)
  for index, entry in enumerate(entries):
    parse_entry(rule_list, entry, f"{where}.entries[{index}]")

  sources = [(kind, value) for kind, value, _ in rule_list.sources]
  for label, values in (("domain", rule_list.domains), ("ip", rule_list.networks), ("peerid", rule_list.peerids), ("asn/country/continent", sources)):
    dupes = sorted({str(v) for v in values if values.count(v) > 1})
    if dupes:
      raise RulesError(f"{where}: duplicate {label}: {', '.join(dupes)}")
  check_overlaps(rule_list)
  return rule_list


def parse_profiles(raw: dict, lists: dict[str, RuleList]) -> dict[str, dict]:
  """Validates Throne profiles: existing lists and a known default outbound."""
  unknown_kinds = sorted(set(raw or {}) - {"throne"})
  if unknown_kinds:
    raise RulesError(f"profiles: unknown profile kinds {', '.join(unknown_kinds)} (only throne)")
  profiles = (raw or {}).get("throne") or {}
  for name, profile in profiles.items():
    where = f"profiles.throne.{name}"
    if not LIST_NAME_RE.match(name):
      raise RulesError(f"{where}: profile name must match [a-z0-9-]")
    if profile.get("default_outbound", "direct") not in ("direct", "proxy", "block"):
      raise RulesError(f"{where}: default_outbound must be direct, proxy or block")
    unknown = [n for n in profile.get("lists", []) if n not in lists]
    if unknown:
      raise RulesError(f"{where}: unknown lists {', '.join(unknown)}")
    disabled = [n for n in profile.get("lists", []) if not lists[n].enabled]
    if disabled:
      raise RulesError(f"{where}: disabled lists {', '.join(disabled)}")
    if not profile.get("lists"):
      raise RulesError(f"{where}: the profile is empty")
  return profiles


def load_rules(path: Path) -> tuple[dict, dict[str, RuleList], dict[str, dict]]:
  """Reads and validates the whole rules.yaml."""
  try:
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=Yaml12Loader)
  except yaml.YAMLError as exc:
    raise RulesError(f"{path}: YAML could not be parsed: {exc}") from None
  if not isinstance(raw, dict):
    raise RulesError(f"{path}: the root must be a mapping")

  meta = raw.get("meta") or {}
  if not re.match(r"^[\w.-]+/[\w.-]+$", str(meta.get("repo", ""))):
    raise RulesError("meta.repo: owner/name is required")
  meta.setdefault("branch", "release")

  lists = {name: parse_list(name, body) for name, body in (raw.get("lists") or {}).items()}
  if not lists:
    raise RulesError("lists: there are no lists")
  profiles = parse_profiles(raw.get("profiles"), lists)
  return meta, lists, profiles


# ---------------------------------------------------------------- generators


def write_lines(path: Path, lines: list[str]) -> None:
  """Writes a text file with LF line endings and a trailing newline."""
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")


def raw_url(meta: dict, rel_path: str) -> str:
  """Direct link to a file on the release branch."""
  return f"https://raw.githubusercontent.com/{meta['repo']}/{meta['branch']}/{rel_path}"


def ip_range(net) -> str:
  """Subnet → 'start-end' range (qBittorrent does not understand CIDR)."""
  return f"{net.network_address}-{net.broadcast_address}"


def gen_podkop(out: Path, lists: dict[str, RuleList], warnings: list[str]) -> list[str]:
  """podkop: .lst with one value per line; subnets are IPv4 only."""
  files = []
  by_action: dict[str, dict[str, list[str]]] = {}
  for rl in lists.values():
    if rl.ipv6:
      warnings.append(f"{rl.name}: {len(rl.ipv6)} IPv6 entries skipped for podkop — it accepts IPv4 only")
    parts = {"domains": rl.domains, "subnets": [str(n) for n in rl.ipv4]}
    for kind, values in parts.items():
      if not values:
        continue
      rel = f"podkop/{rl.name}.{kind}.lst"
      write_lines(out / rel, values)
      files.append(rel)
      by_action.setdefault(rl.action, {}).setdefault(kind, []).extend(values)

  # Aggregated files per action: a new list is picked up without reconfiguring the router.
  for action, parts in by_action.items():
    for kind, values in parts.items():
      rel = f"podkop/all-{action}.{kind}.lst"
      write_lines(out / rel, sorted(set(values), key=values.index))
      files.append(rel)
  return files


def singbox_source(rl: RuleList) -> dict | None:
  """sing-box rule-set source; None when the list has no domains or IPs."""
  rules = []
  if rl.domains:
    rules.append({"domain_suffix": rl.domains})
  if rl.all_networks:
    rules.append({"ip_cidr": [str(n) for n in rl.all_networks]})
  if not rules:
    return None
  return {"version": SINGBOX_RULESET_VERSION, "rules": rules}


def gen_singbox(out: Path, lists: dict[str, RuleList], sing_box: str | None) -> list[str]:
  """sing-box: .json always, .srs only when a sing-box binary is given."""
  files = []
  for rl in lists.values():
    source = singbox_source(rl)
    if source is None:
      continue
    json_rel = f"sing-box/{rl.name}.json"
    (out / json_rel).parent.mkdir(parents=True, exist_ok=True)
    (out / json_rel).write_text(json.dumps(source, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    files.append(json_rel)
    if not sing_box:
      continue
    srs_rel = f"sing-box/{rl.name}.srs"
    subprocess.run([sing_box, "rule-set", "compile", "--output", str(out / srs_rel), str(out / json_rel)], check=True)
    files.append(srs_rel)
  return files


def throne_profile(meta: dict, name: str, profile: dict, lists: dict[str, RuleList]) -> dict:
  """Throne profile object (kind throne-route-profile, v 1) with rule_set URLs to .srs."""
  rules = [
    {"name": "dns", "type": "custom", "action": "hijack-dns", "protocol": "dns"},
    {"name": "private direct", "type": "custom", "action": "route", "outbound": "direct", "ip_is_private": True},
  ]
  for list_name in profile["lists"]:
    rl = lists[list_name]
    if singbox_source(rl) is None:
      continue
    rule = {"name": f"{rl.action}: {rl.name}", "type": "custom", **THRONE_ACTION[rl.action]}
    rule["rule_set"] = [raw_url(meta, f"sing-box/{rl.name}.srs")]
    rules.append(rule)
  return {
    "kind": "throne-route-profile",
    "v": 1,
    "name": profile.get("name", name),
    "default_outbound": profile.get("default_outbound", "direct"),
    "rules": rules,
  }


def throne_link(obj: dict) -> str:
  """throne://route/<base64url without '='> — the same way Throne makes links."""
  compact = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
  return "throne://route/" + base64.urlsafe_b64encode(compact).decode("ascii").rstrip("=")


def gen_throne(out: Path, meta: dict, lists: dict[str, RuleList], profiles: dict[str, dict]) -> list[str]:
  """Throne: one link file per profile."""
  files = []
  for name, profile in profiles.items():
    rel = f"throne/{name}.txt"
    write_lines(out / rel, [throne_link(throne_profile(meta, name, profile, lists))])
    files.append(rel)
  return files


def gen_nekobox(out: Path, meta: dict, lists: dict[str, RuleList]) -> list[str]:
  """NekoBox: desktop takes 'ruleset:<url>' lines; Android has no remote rule-sets, so plain lines to paste."""
  files = []
  for action in THRONE_ACTION:
    group = [rl for rl in lists.values() if rl.action == action]
    # Desktop (qr243vbi/nekobox): one 'ruleset:' line per list, pasted into the route of this action.
    desktop = [f"ruleset:{raw_url(meta, f'sing-box/{rl.name}.srs')}" for rl in group if singbox_source(rl)]
    # Android (NekoBoxForAndroid): 'domain:' = domain_suffix in its route editor; IPs as plain CIDR.
    android = {
      "domains": [f"domain:{d}" for rl in group for d in rl.domains],
      "ips": [str(n) for rl in group for n in rl.all_networks],
    }
    if desktop:
      write_lines(out / f"nekobox/desktop-{action}.txt", desktop)
      files.append(f"nekobox/desktop-{action}.txt")
    for kind, lines in android.items():
      if not lines:
        continue
      rel = f"nekobox/android-{action}.{kind}.txt"
      write_lines(out / rel, lines)
      files.append(rel)
  return files


def gen_tixati(out: Path, lists: dict[str, RuleList], warnings: list[str]) -> list[str]:
  """Tixati: 'label:CIDR' (IPv4 and IPv6), an aggregated blocklist and a Peer ID filter."""
  files = []
  all_block: list[str] = []
  peerids: list[str] = []
  for rl in lists.values():
    if rl.action != "block":
      continue
    peerids.extend(p for p in rl.peerids if p not in peerids)
    lines = [f"{rl.name}:{net}" for net in rl.all_networks]
    if not lines:
      continue
    if len(lines) == 1:
      warnings.append(f"{rl.name}: a single line — Tixati before 2.82 does not load such a file")
    rel = f"tixati/{rl.name}.txt"
    write_lines(out / rel, lines)
    files.append(rel)
    all_block.extend(lines)

  if all_block:
    write_lines(out / "tixati/all-block.txt", all_block)
    files.append("tixati/all-block.txt")
  if peerids:
    # One line each in Settings → Peers → Client Filter → Peer ID → "never allow".
    write_lines(out / "tixati/peerid-filter.txt", [f"{p}*" for p in peerids])
    files.append("tixati/peerid-filter.txt")
  return files


def pcre_escape(text: str) -> str:
  """Escapes PCRE (QRegularExpression) special characters without over-escaping."""
  return re.sub(r"([\\^$.|?*+()\[\]{}])", r"\\\1", text)


def gen_qbittorrent(out: Path, lists: dict[str, RuleList]) -> list[str]:
  """qBittorrent: one ipfilter.p2p (the client has a single filter path) and peer_blacklist.txt for Enhanced."""
  files = []
  lines = ["# rulesets: generated, do not edit"]
  peerids: list[str] = []
  for rl in lists.values():
    if rl.action != "block":
      continue
    lines.extend(f"{rl.name}:{ip_range(net)}" for net in rl.all_networks)
    peerids.extend(p for p in rl.peerids if p not in peerids)

  if len(lines) > 1:
    write_lines(out / "qbittorrent/ipfilter.p2p", lines)
    files.append("qbittorrent/ipfilter.p2p")
  if peerids:
    # Enhanced format: "<Peer ID regex> <client name regex>", both must match.
    write_lines(out / "qbittorrent/peer_blacklist.txt", [f"^{pcre_escape(p)} .*" for p in peerids])
    files.append("qbittorrent/peer_blacklist.txt")

  script = REPO_ROOT / "clients/qbittorrent/update-ipfilter.ps1"
  if script.exists():
    (out / "qbittorrent").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(script, out / "qbittorrent/update-ipfilter.ps1")
    files.append("qbittorrent/update-ipfilter.ps1")
  return files


# Release README texts per language: file name, language switcher and fixed phrases.
RELEASE_README = {
  "en": {
    "file": "README.md",
    "switch": "**English** | [Русский](README.ru.md)",
    "intro": "Generated from `rules.yaml` in [{repo}](https://github.com/{repo}). This branch is generated automatically; manual changes here are replaced by the next build.",
    "pin": (
      "Every build is also tagged `build-YYYY-MM-DD-N` (N is the CI run number). To pin a client to a build, replace "
      "`/{branch}/` in a link with `/<tag>/`. Throne profiles inside a tag still load `.srs` "
      "from the `{branch}` branch."
    ),
    "warnings": "Warnings",
  },
  "ru": {
    "file": "README.ru.md",
    "switch": "[English](README.md) | **Русский**",
    "intro": "Собрано из `rules.yaml` в [{repo}](https://github.com/{repo}). Ветка генерируется автоматически; ручные правки здесь заменит следующая сборка.",
    "pin": (
      "Каждая сборка также помечена тегом `build-YYYY-MM-DD-N` (N — номер прогона CI). Чтобы закрепить клиент на сборке, "
      "замените в ссылке `/{branch}/` на `/<тег>/`. Профили Throne внутри тега всё равно берут `.srs` "
      "из ветки `{branch}`."
    ),
    "warnings": "Предупреждения",
  },
}


def release_readme(meta: dict, files: list[str], warnings: list[str], texts: dict) -> list[str]:
  """Lines of one release README: switcher, intro, tag pinning, links by folder, warnings."""
  lines = [
    "# rulesets — release",
    "",
    texts["switch"],
    "",
    texts["intro"].format(repo=meta["repo"]),
    "",
    texts["pin"].format(branch=meta["branch"]),
    "",
  ]
  for folder in sorted({f.split("/")[0] for f in files}):
    lines += [f"## {folder}", ""]
    lines += [f"- [`{f}`]({raw_url(meta, f)})" for f in sorted(files) if f.startswith(folder + "/")]
    lines.append("")
  if warnings:
    lines += [f"## {texts['warnings']}", ""]
    lines += [f"- {w}" for w in warnings]
    lines.append("")
  return lines[:-1]


def gen_index(out: Path, meta: dict, files: list[str], warnings: list[str]) -> None:
  """index.json and README.md / README.ru.md of the release branch with links to everything built."""
  index = {"repo": meta["repo"], "branch": meta["branch"], "files": {f: raw_url(meta, f) for f in sorted(files)}, "warnings": warnings}
  (out / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

  for texts in RELEASE_README.values():
    write_lines(out / texts["file"], release_readme(meta, files, warnings, texts))


def resolve_sources(lists: dict[str, RuleList], resolver: Resolver, warnings: list[str]) -> None:
  """Expands asn/country/continent entries of enabled lists and enforces max_prefixes."""
  for rl in lists.values():
    for kind, value, limit in rl.sources:
      key = resolver.key(kind, value)
      try:
        nets = resolver.resolve(kind, value)
      except SourceError as exc:
        raise RulesError(str(exc)) from None
      if len(nets) > limit:
        raise RulesError(f"lists.{rl.name}: {key} has {len(nets)} prefixes, over max_prefixes {limit}; raise it explicitly if this is intended")
      if not nets:
        warnings.append(f"{rl.name}: {key} resolved to no prefixes")
      rl.resolved.extend(nets)
  warnings.extend(resolver.warnings)


def gen_resolved(out: Path, resolver: Resolver) -> list[str]:
  """Snapshot of every expansion, so the next build can fall back on it."""
  files = []
  for kind_value, nets in sorted(resolver.cache.items()):
    rel = f"resolved/{kind_value}.txt"
    write_lines(out / rel, [str(n) for n in nets])
    files.append(rel)
  return files


def build(rules_path: Path, out: Path, sing_box: str | None, resolver: Resolver | None = None) -> tuple[list[str], list[str]]:
  """Full build: validation, expansion of asn/country/continent, cleanup, all generators."""
  meta, all_lists, profiles = load_rules(rules_path)
  # Disabled lists (e.g. the example) are validated but produce nothing.
  lists = {name: rl for name, rl in all_lists.items() if rl.enabled}
  warnings: list[str] = []
  resolver = resolver or Resolver()
  resolve_sources(lists, resolver, warnings)

  if out.exists():
    shutil.rmtree(out)
  out.mkdir(parents=True)

  files = gen_resolved(out, resolver)
  files += gen_podkop(out, lists, warnings)
  files += gen_singbox(out, lists, sing_box)
  files += gen_throne(out, meta, lists, profiles)
  files += gen_nekobox(out, meta, lists)
  files += gen_tixati(out, lists, warnings)
  files += gen_qbittorrent(out, lists)
  if not sing_box:
    warnings.append("sing-box not given: .srs files were not built, Throne profiles point to missing files")
  gen_index(out, meta, files, warnings)
  return files, warnings


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--rules", type=Path, default=REPO_ROOT / "rules.yaml")
  parser.add_argument("--out", type=Path, default=REPO_ROOT / "dist")
  parser.add_argument("--sing-box", dest="sing_box", default=None, help="path to the sing-box binary for .srs")
  parser.add_argument("--snapshot", type=Path, default=None, help="previous release checkout, used if RIPEstat is down")
  args = parser.parse_args()

  try:
    files, warnings = build(args.rules, args.out, args.sing_box, Resolver(snapshot_dir=args.snapshot))
  except RulesError as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    return 1

  print(f"Built {len(files)} files → {args.out}")
  for warning in warnings:
    # GitHub Actions annotation format: the warning shows up in the run summary.
    print(f"::warning::{warning}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
