"""Unit tests for gh_sync.py — auto-sync to GitHub."""
import sys
import os
import json
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_sync


class TestShouldExclude:
    def test_excludes_pycache(self):
        assert gh_sync.should_exclude("skills/foo/__pycache__/bar.pyc") is True
    
    def test_excludes_pyc(self):
        assert gh_sync.should_exclude("automation/test.pyc") is True
    
    def test_excludes_env(self):
        assert gh_sync.should_exclude("automation/.env") is True
    
    def test_excludes_pending_pkce(self):
        assert gh_sync.should_exclude("automation/.pending_pkce.json") is True
    
    def test_excludes_publish_state(self):
        assert gh_sync.should_exclude("automation/publish_state.json") is True
    
    def test_excludes_costs(self):
        assert gh_sync.should_exclude("automation/wave2_costs.json") is True
    
    def test_excludes_log(self):
        assert gh_sync.should_exclude("automation/debug.log") is True
    
    def test_allows_normal_py(self):
        assert gh_sync.should_exclude("skills/reel-factory/render.py") is False
    
    def test_allows_markdown(self):
        assert gh_sync.should_exclude("skills/foo/SKILL.md") is False
    
    def test_allows_env_example(self):
        # .env.example is safe (template, no secrets)
        assert gh_sync.should_exclude(".env.example") is False


class TestScanForSecrets:
    def test_detects_user_email(self):
        content = b'EMAIL = "tangziyi001@gmail.com"'
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert len(found) > 0
        assert "user email" in found
    
    def test_detects_phone(self):
        content = b'phone: 347-301-3804'
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert "user phone" in found
    
    def test_detects_api_key(self):
        content = b'api_key = "sk-1234567890abcdef1234"'
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert len(found) > 0
    
    def test_detects_password(self):
        content = b'password = "secret123"'
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert "password assignment" in found
    
    def test_detects_github_pat(self):
        content = b'token = "github_pat_abc123XYZ"'
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert "github pat" in found
    
    def test_clean_code_passes(self):
        content = b'''import os
EMAIL = os.environ.get("ETSY_EMAIL", "")
def hello(): return "world"
'''
        found = gh_sync.scan_for_secrets(content, "test.py")
        assert found == []
    
    def test_env_example_passes(self):
        # Template with empty values should pass
        content = b'ETSY_EMAIL=\nETSY_API_KEY=\n'
        found = gh_sync.scan_for_secrets(content, ".env.example")
        assert found == []


class TestFileHash:
    def test_same_content_same_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path1 = f.name
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            path2 = f.name
        try:
            assert gh_sync.file_hash(path1) == gh_sync.file_hash(path2)
        finally:
            os.unlink(path1)
            os.unlink(path2)
    
    def test_different_content_different_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            path1 = f.name
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"world")
            path2 = f.name
        try:
            assert gh_sync.file_hash(path1) != gh_sync.file_hash(path2)
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestCollectFiles:
    def test_collects_from_sync_dirs(self):
        files = gh_sync.collect_files()
        # Should find at least the github skill itself
        assert any("skills/github" in k for k in files.keys())
    
    def test_excludes_pycache_from_collection(self):
        files = gh_sync.collect_files()
        for repo_path in files.keys():
            assert "__pycache__" not in repo_path
            assert not repo_path.endswith(".pyc")


class TestStateRoundtrip:
    def test_save_and_load_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, ".gh_sync_state.json")
            # Temporarily override STATE_FILE
            orig = gh_sync.STATE_FILE
            gh_sync.STATE_FILE = state_path
            try:
                test_state = {"skills/foo.py": "abc123"}
                gh_sync.save_state(test_state)
                loaded = gh_sync.load_state()
                assert loaded == test_state
            finally:
                gh_sync.STATE_FILE = orig
    
    def test_load_missing_state_returns_empty(self):
        orig = gh_sync.STATE_FILE
        gh_sync.STATE_FILE = "/tmp/nonexistent_gh_sync_state_12345.json"
        try:
            assert gh_sync.load_state() == {}
        finally:
            gh_sync.STATE_FILE = orig
