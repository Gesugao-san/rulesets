#!/usr/bin/env python3
"""rulesets builder tests: rules.yml validation and format compatibility with clients.

The client parsers here mirror the clients' own source code, so a format
change on our side cannot slip through unnoticed:
  - qBittorrent: src/base/bittorrent/filterparserthread.cpp (P2P format);
  - Tixati: examples from https://support.tixati.com/ip%20filter%20format;
  - Throne: RouteProfile::FromShareInput (throne://route/<base64url>).

Run: python3 -m unittest tools/test_build.py
With SING_BOX=/path/to/sing-box the .srs files are checked too.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
# Line forms from the Tixati docs (only the ones we generate).
TIXATI_LINE_RE = re.compile(r"^[^:\s]+:(?P<net>[0-9a-fA-F.:\[\]]+/\d{1,3})$")


def parse_ip(text: str):
  """Parses an address like libtorrent does: empty or garbage is an error."""
  try:
    return ipaddress.ip_address(text.strip())
  except ValueError:
    return None


def qbt_parse_p2p_line(line: str):
  """Mirrors qBittorrent P2P parsing: the last '-' splits the range, the label ends at the first fitting ':'."""
  if line.startswith("#") or line.startswith("//") or not line.strip():
    return "skip"
  delim = line.rfind("-")
  if delim == -1:
    return None
  left, right = line[:delim], line[delim + 1:]
  search = 0
  start_addr = None
  while True:
    colon = left.find(":", search)
    if colon == -1:
      break
    start_addr = parse_ip(left[colon + 1:])
    if start_addr:
      break
    search = colon + 1
  end_addr = parse_ip(right)
  if not start_addr or not end_addr or start_addr.version != end_addr.version:
    return None
  return start_addr, end_addr


def decode_throne(link: str) -> dict:
  """Decodes a link like Throne does: the path after throne://route/ is unpadded base64url."""
  payload = link.strip().removeprefix("throne://route/")
  payload += "=" * (-len(payload) % 4)
  return json.loads(base64.urlsafe_b64decode(payload))


def write_rules(tmp: Path, body: str) -> Path:
  """Writes a temporary rules.yml with a minimal header."""
  path = tmp / "rules.yml"
  path.write_text("meta:\n  repo: owner/repo\n" + textwrap.dedent(body), encoding="utf-8")
  return path


class ValidationTests(unittest.TestCase):
  """Errors in rules.yml must be caught before publishing."""

  def assert_rejected(self, body: str, fragment: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      path = write_rules(Path(tmp), body)
      with self.assertRaises(build.RulesError) as ctx:
        build.load_rules(path)
      self.assertIn(fragment, str(ctx.exception))

  def test_private_range(self):
    self.assert_rejected("""
      lists:
        x:
          action: block
          entries:
            - ip: 192.168.0.0/16
              evidence: [https://example.com]
    """, "private")

  def test_host_bits(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - ip: 8.8.8.1/24
    """, "host bits")

  def test_third_level_domain(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - domain: a.b.example
    """, "second level")

  def test_third_level_with_exception(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = write_rules(Path(tmp), """
        lists:
          x:
            action: proxy
            entries:
              - domain: a.example.com
                sld_exception: test
      """)
      _, lists, _ = build.load_rules(path)
      self.assertEqual(lists["x"].domains, ["a.example.com"])

  def test_block_requires_evidence(self):
    self.assert_rejected("""
      lists:
        x:
          action: block
          entries:
            - ip: 8.8.8.0/24
    """, "evidence")

  def test_peerid_too_long(self):
    self.assert_rejected("""
      lists:
        x:
          action: block
          entries:
            - peerid: -ABCDEFG1-
              evidence: [https://example.com]
    """, "longer than")

  def test_peerid_only_in_block(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - peerid: -AB0001-
    """, "only in lists")

  def test_overlap(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - ip: 8.8.0.0/16
            - ip: 8.8.8.0/24
    """, "already inside")

  def test_duplicate(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - domain: example.com
            - domain: Example.com
    """, "duplicate")

  def test_unknown_profile_list(self):
    self.assert_rejected("""
      lists:
        x:
          action: proxy
          entries:
            - domain: example.com
      profiles:
        throne:
          p:
            lists: [nope]
    """, "unknown lists")


class OutputTests(unittest.TestCase):
  """Builds the real rules.yml and checks every format."""

  @classmethod
  def setUpClass(cls):
    cls.tmp = tempfile.TemporaryDirectory()
    cls.out = Path(cls.tmp.name) / "dist"
    cls.sing_box = os.environ.get("SING_BOX")
    cls.files, cls.warnings = build.build(REPO_ROOT / "rules.yml", cls.out, cls.sing_box)
    cls.meta, cls.lists, cls.profiles = build.load_rules(REPO_ROOT / "rules.yml")

  @classmethod
  def tearDownClass(cls):
    cls.tmp.cleanup()

  def read(self, rel: str) -> list[str]:
    text = (self.out / rel).read_text(encoding="utf-8")
    self.assertTrue(text.endswith("\n"), f"{rel}: no trailing newline")
    self.assertNotIn("\r", text, f"{rel}: CRLF")
    return text.splitlines()

  def test_podkop_subnets_ipv4_only(self):
    for rel in (f for f in self.files if f.startswith("podkop/") and f.endswith(".subnets.lst")):
      for line in self.read(rel):
        self.assertEqual(ipaddress.ip_network(line).version, 4, f"{rel}: {line}")

  def test_podkop_domains_plain(self):
    for rel in (f for f in self.files if f.startswith("podkop/") and f.endswith(".domains.lst")):
      for line in self.read(rel):
        self.assertRegex(line, r"^[a-z0-9.-]+$", rel)

  def test_qbittorrent_p2p_parses(self):
    expected = sum(len(rl.networks) for rl in self.lists.values() if rl.action == "block")
    parsed = [qbt_parse_p2p_line(line) for line in self.read("qbittorrent/ipfilter.p2p")]
    self.assertNotIn(None, parsed, "qBittorrent would treat a line as malformed")
    self.assertEqual(len([p for p in parsed if p != "skip"]), expected)

  def test_qbittorrent_ranges_match_cidr(self):
    nets = [n for rl in self.lists.values() if rl.action == "block" for n in rl.networks]
    ranges = [qbt_parse_p2p_line(line) for line in self.read("qbittorrent/ipfilter.p2p")]
    ranges = [r for r in ranges if r != "skip"]
    for net, (start, end) in zip(nets, ranges):
      self.assertEqual((start, end), (net.network_address, net.broadcast_address))

  def test_enhanced_blacklist_format(self):
    for line in self.read("qbittorrent/peer_blacklist.txt"):
      fields = line.split()
      self.assertEqual(len(fields), 2, f"Enhanced reads exactly two space-separated fields: {line}")
      peer_re = re.compile(fields[0])
      self.assertTrue(fields[0].startswith("^"), "without ^ the regex matches in the middle of a Peer ID")
      # Enhanced compares only the first 8 chars of a Peer ID.
      sample = fields[0].lstrip("^").replace("\\", "")[:8].ljust(8, "0")
      self.assertTrue(peer_re.search(sample), line)

  def test_tixati_lines_documented(self):
    for rel in (f for f in self.files if f.startswith("tixati/") and f != "tixati/peerid-filter.txt"):
      lines = self.read(rel)
      for line in lines:
        match = TIXATI_LINE_RE.match(line)
        self.assertIsNotNone(match, f"{rel}: '{line}' does not follow the Tixati docs")
        ipaddress.ip_network(match["net"].strip("[]"), strict=True)

  def test_tixati_peerid(self):
    for line in self.read("tixati/peerid-filter.txt"):
      self.assertTrue(line.endswith("*"))
      self.assertNotIn(" ", line)

  def test_throne_roundtrip(self):
    for name in self.profiles:
      (link,) = self.read(f"throne/{name}.txt")
      self.assertTrue(link.startswith("throne://route/"))
      self.assertNotIn("=", link, "Throne uses base64url without '='")
      obj = decode_throne(link)
      self.assertEqual(obj["kind"], "throne-route-profile")
      self.assertEqual(obj["v"], 1)
      for rule in obj["rules"]:
        self.assertIn(rule["action"], ("route", "reject", "hijack-dns"))
        for url in rule.get("rule_set", []):
          # Throne accepts a remote rule-set only if the file name contains .srs.
          self.assertTrue(url.startswith("https://") and url.endswith(".srs"), url)

  def test_singbox_json(self):
    for rel in (f for f in self.files if f.startswith("sing-box/") and f.endswith(".json")):
      data = json.loads((self.out / rel).read_text(encoding="utf-8"))
      self.assertEqual(data["version"], build.SINGBOX_RULESET_VERSION)
      self.assertTrue(data["rules"])

  @unittest.skipUnless(os.environ.get("SING_BOX"), "needs SING_BOX=/path/to/sing-box")
  def test_srs_roundtrip(self):
    for rel in (f for f in self.files if f.endswith(".srs")):
      src = json.loads((self.out / rel.replace(".srs", ".json")).read_text(encoding="utf-8"))
      decompiled = self.out / "decompiled.json"
      subprocess.run([self.sing_box, "rule-set", "decompile", "--output", str(decompiled), str(self.out / rel)], check=True)
      back = json.loads(decompiled.read_text(encoding="utf-8"))
      self.assertEqual(back["rules"], src["rules"], rel)

  def test_index_lists_everything(self):
    index = json.loads((self.out / "index.json").read_text(encoding="utf-8"))
    self.assertEqual(sorted(index["files"]), sorted(self.files))


if __name__ == "__main__":
  unittest.main()
