"""
Domain Skills — self-improving per-site playbooks.

After the agent figures out a tricky site's structure (selectors, flows,
edge cases), it writes a skill file. Next visit loads the skill automatically.

This is the browser-harness "domain-skills" concept ported to Blackreach.

File layout:
    domain-skills/
        ├── github.com/
        │   └── skill.yaml       ← patterns the agent learned
        ├── amazon.com/
        │   ├── cart.yaml
        │   └── search.yaml
        └── _template.yaml       ← what a new skill looks like

Each skill file:
    host: "github.com"
    last_verified: "2026-05-06"
    selectors:
      search_input: 'input[name="q"]'
      repo_list:    'article.Box-row'
      next_page:    'a[rel="next"]'
    waits:
      - selector: '.ajax-loaded'
        timeout: 3000
    traps:
      - pattern: 'rate limit'
        action: 'wait 60s, retry'
      - pattern: 'Sign in to view'
        action: 'stop, ask user'
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml


SKILLS_DIR = Path("domain-skills")


@dataclass
class SiteSkill:
    """A single learned skill for a hostname + path pattern."""
    host: str
    name: str                       # e.g. "search", "cart", "download"
    last_verified: str = ""
    selectors: Dict[str, str] = field(default_factory=dict)
    waits: List[Dict] = field(default_factory=list)
    traps: List[Dict] = field(default_factory=list)
    notes: str = ""
    success_count: int = 0
    fail_count: int = 0

    @property
    def trust(self) -> float:
        """How reliable this skill is. Higher = more trustworthy."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return self.success_count / total


class DomainSkillManager:
    """Loads, matches, and writes domain-specific skills."""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.dir = skills_dir or SKILLS_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, List[SiteSkill]] = {}  # host -> [skills]
        self._load_all()

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_for_host(self, host: str) -> List[SiteSkill]:
        """All skills for a given hostname (e.g. 'github.com')."""
        return self._skills.get(self._normalize_host(host), [])

    def get_selector(self, host: str, name: str) -> Optional[str]:
        """Get a specific selector by skill name."""
        for skill in self.get_for_host(host):
            if name in skill.selectors:
                return skill.selectors[name]
        return None

    def find_skill_file(self, host: str) -> List[Path]:
        """Return up to 10 skill YAML files for a hostname."""
        host_dir = self.dir / self._normalize_host(host)
        if not host_dir.exists():
            return []
        return sorted(host_dir.glob("*.yaml"))[:10]

    # ------------------------------------------------------------------
    # Write API — called after agent succeeds on a site
    # ------------------------------------------------------------------

    def record_success(
        self,
        host: str,
        skill_name: str,
        selectors: Optional[Dict[str, str]] = None,
        traps: Optional[List[Dict]] = None,
        notes: str = "",
    ) -> None:
        """Record a successful interaction pattern for a site."""
        host = self._normalize_host(host)
        existing = self._find_skill(host, skill_name)

        if existing:
            existing.success_count += 1
            existing.last_verified = self._today()
            if selectors:
                existing.selectors.update(selectors)
            if traps:
                existing.traps.extend(traps)
            if notes and notes not in existing.notes:
                existing.notes += f"\n{notes}"
        else:
            existing = SiteSkill(
                host=host,
                name=skill_name,
                last_verified=self._today(),
                selectors=selectors or {},
                traps=traps or [],
                notes=notes,
                success_count=1,
            )
            self._skills.setdefault(host, []).append(existing)

        self._save_skill(existing)

    def record_failure(self, host: str, skill_name: str, reason: str = "") -> None:
        """Mark a skill as having failed so trust score drops."""
        host = self._normalize_host(host)
        skill = self._find_skill(host, skill_name)
        if skill:
            skill.fail_count += 1
            if reason and reason not in skill.notes:
                skill.notes += f"\nFAIL: {reason}"
            self._save_skill(skill)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        if not self.dir.exists():
            return
        for yaml_file in self.dir.rglob("*.yaml"):
            if yaml_file.name.startswith("_"):
                continue
            try:
                data = yaml.safe_load(yaml_file.read_text()) or {}
                skill = SiteSkill(**data)
                self._skills.setdefault(skill.host, []).append(skill)
            except Exception:
                pass

    def _find_skill(self, host: str, name: str) -> Optional[SiteSkill]:
        for skill in self._skills.get(host, []):
            if skill.name == name:
                return skill
        return None

    @staticmethod
    def _normalize_host(host: str) -> str:
        return host.lower().replace("www.", "")

    @staticmethod
    def _today() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _save_skill(self, skill: SiteSkill) -> None:
        host_dir = self.dir / skill.host
        host_dir.mkdir(parents=True, exist_ok=True)
        path = host_dir / f"{skill.name}.yaml"
        data = {
            "host": skill.host,
            "name": skill.name,
            "last_verified": skill.last_verified,
            "selectors": skill.selectors,
            "waits": skill.waits,
            "traps": skill.traps,
            "notes": skill.notes,
            "success_count": skill.success_count,
            "fail_count": skill.fail_count,
        }
        # Skip None values
        data = {k: v for k, v in data.items() if v is not None and v != "" and v != [] and v != {}}
        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


# ---------------------------------------------------------------------------
# Shortcuts
# ---------------------------------------------------------------------------

_manager: Optional[DomainSkillManager] = None


def get_skill_manager() -> DomainSkillManager:
    global _manager
    if _manager is None:
        _manager = DomainSkillManager()
    return _manager
