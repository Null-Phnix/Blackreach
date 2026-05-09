"""Unit tests for blackreach/domain_skills.py."""
import pytest
from pathlib import Path
from blackreach.domain_skills import (
    SiteSkill,
    DomainSkillManager,
    get_skill_manager,
    _manager,
    SKILLS_DIR,
)


class TestSiteSkill:
    def test_trust_zero_when_no_attempts(self):
        skill = SiteSkill(host="example.com", name="search")
        assert skill.trust == 0.0

    def test_trust_half(self):
        skill = SiteSkill(host="example.com", name="search", success_count=1, fail_count=1)
        assert skill.trust == 0.5

    def test_trust_perfect(self):
        skill = SiteSkill(host="example.com", name="search", success_count=10, fail_count=0)
        assert skill.trust == 1.0

    def test_trust_zero_all_fails(self):
        skill = SiteSkill(host="example.com", name="search", success_count=0, fail_count=5)
        assert skill.trust == 0.0


class TestDomainSkillManager:
    @pytest.fixture(autouse=True)
    def clean_manager(self, tmp_path):
        global _manager
        _manager = None
        self.tmp_dir = tmp_path / "domain-skills"
        self.mgr = DomainSkillManager(skills_dir=self.tmp_dir)

    def test_init_creates_dir(self):
        assert self.tmp_dir.exists()

    def test_get_for_host_empty(self):
        assert self.mgr.get_for_host("example.com") == []

    def test_record_success_creates_skill(self):
        self.mgr.record_success(
            host="example.com",
            skill_name="search",
            selectors={"input": 'input[name="q"]'},
        )
        skills = self.mgr.get_for_host("example.com")
        assert len(skills) == 1
        assert skills[0].name == "search"
        assert skills[0].selectors == {"input": 'input[name="q"]'}
        assert skills[0].success_count == 1

    def test_record_success_updates_existing(self):
        self.mgr.record_success("example.com", "search", selectors={"a": "1"})
        self.mgr.record_success("example.com", "search", selectors={"b": "2"})
        skill = self.mgr.get_for_host("example.com")[0]
        assert skill.success_count == 2
        assert skill.selectors == {"a": "1", "b": "2"}

    def test_record_failure(self):
        self.mgr.record_success("example.com", "search")
        self.mgr.record_failure("example.com", "search", reason="timeout")
        skill = self.mgr.get_for_host("example.com")[0]
        assert skill.fail_count == 1
        assert "timeout" in skill.notes

    def test_get_selector_found(self):
        self.mgr.record_success("example.com", "search", selectors={"input": 'input[name="q"]'})
        assert self.mgr.get_selector("example.com", "input") == 'input[name="q"]'

    def test_get_selector_missing(self):
        assert self.mgr.get_selector("example.com", "input") is None

    def test_find_skill_file(self):
        self.mgr.record_success("example.com", "search")
        files = self.mgr.find_skill_file("example.com")
        assert len(files) == 1
        assert files[0].name == "search.yaml"

    def test_find_skill_file_missing_host(self):
        assert self.mgr.find_skill_file("nonexistent.com") == []

    def test_normalize_host(self):
        assert DomainSkillManager._normalize_host("WWW.Example.COM") == "example.com"

    def test_save_skips_empty_values(self):
        self.mgr.record_success("example.com", "search")
        yaml_text = (self.tmp_dir / "example.com" / "search.yaml").read_text()
        assert "waits" not in yaml_text
        assert "traps" not in yaml_text

    def test_load_persists_across_instances(self):
        self.mgr.record_success("example.com", "search", selectors={"input": 'input[name="q"]'})
        mgr2 = DomainSkillManager(skills_dir=self.tmp_dir)
        assert mgr2.get_selector("example.com", "input") == 'input[name="q"]'

    def test_ignores_underscore_files(self):
        host_dir = self.tmp_dir / "example.com"
        host_dir.mkdir(parents=True)
        (host_dir / "_template.yaml").write_text("host: example.com\nname: ignore_me\n")
        (host_dir / "valid.yaml").write_text("host: example.com\nname: valid\n")
        mgr = DomainSkillManager(skills_dir=self.tmp_dir)
        names = [s.name for s in mgr.get_for_host("example.com")]
        assert "ignore_me" not in names
        assert "valid" in names

    def test_record_success_notes_deduplication(self):
        self.mgr.record_success("example.com", "search", notes="tip: click first")
        self.mgr.record_success("example.com", "search", notes="tip: click first")
        skill = self.mgr.get_for_host("example.com")[0]
        assert skill.notes.count("tip: click first") == 1


class TestGetSkillManager:
    def test_singleton(self, tmp_path):
        global _manager
        _manager = None
        m1 = get_skill_manager()
        m2 = get_skill_manager()
        assert m1 is m2

    def test_singleton_uses_default_dir(self):
        global _manager
        _manager = None
        mgr = get_skill_manager()
        assert mgr.dir == SKILLS_DIR
