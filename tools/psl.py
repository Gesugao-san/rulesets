"""Public Suffix List: the registrable domain (eTLD+1) of a host name.

Data: tools/data/public_suffix_list.dat, a snapshot of https://publicsuffix.org/list/
(Mozilla Public License 2.0, see the header of that file). Both the ICANN and the
private sections are used, so pages.dev or googleapis.com count as public suffixes.
"""

from __future__ import annotations

from pathlib import Path

PSL_FILE = Path(__file__).resolve().parent / "data/public_suffix_list.dat"


class PublicSuffixList:
  """Standard PSL matching: exact rules, wildcards (*.x) and exceptions (!y.x)."""

  def __init__(self, text: str):
    self.rules: set[str] = set()
    self.exceptions: set[str] = set()
    for raw in text.splitlines():
      line = raw.strip()
      if not line or line.startswith("//"):
        continue
      rule = line.split()[0].lower()
      if rule.startswith("!"):
        self.exceptions.add(rule[1:])
      else:
        self.rules.add(rule)

  def public_suffix(self, domain: str) -> str:
    """Longest public suffix of `domain`; an unlisted TLD is a suffix by the implicit "*" rule."""
    labels = domain.lower().strip(".").split(".")
    for i in range(len(labels)):
      candidate = ".".join(labels[i:])
      if candidate in self.exceptions:
        # An exception rule makes the name itself registrable: its suffix is one label shorter.
        return ".".join(labels[i + 1:])
      wildcard = ".".join(["*"] + labels[i + 1:])
      if candidate in self.rules or (i + 1 < len(labels) and wildcard in self.rules):
        return candidate
    return labels[-1]

  def registrable(self, domain: str) -> str | None:
    """eTLD+1, or None when the domain is itself a public suffix."""
    labels = domain.lower().strip(".").split(".")
    suffix_len = len(self.public_suffix(domain).split("."))
    if len(labels) <= suffix_len:
      return None
    return ".".join(labels[-(suffix_len + 1):])


def load_psl() -> PublicSuffixList:
  return PublicSuffixList(PSL_FILE.read_text(encoding="utf-8"))
