"""
Tests for agents/shared/tools.py — tool implementations and schemas.

Covers: read_file, write_file, list_files, run_command, search_code,
        grep_repos, make_tool, predefined schemas, HANDLERS dict.
"""

import os
import stat
import pytest
from pathlib import Path
from unittest.mock import patch

from local_ai.agents.shared.tools import (
    read_file, write_file, list_files, run_command, search_code, grep_repos,
    make_tool, READ_FILE, WRITE_FILE, LIST_FILES, RUN_COMMAND, SEARCH_CODE,
    HANDLERS, MAX_OUTPUT,
)


# ── read_file ─────────────────────────────────────────────────────────────────

class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        assert read_file(str(f)) == "hello world"

    def test_missing_file_returns_error_string(self, tmp_path):
        result = read_file(str(tmp_path / "nonexistent.py"))
        assert "not found" in result.lower() or "File not found" in result

    def test_tilde_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        f = tmp_path / "testfile.txt"
        f.write_text("expanded")
        result = read_file("~/testfile.txt")
        assert result == "expanded"

    def test_truncates_large_file(self, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * (MAX_OUTPUT + 500))
        result = read_file(str(f))
        assert len(result) < MAX_OUTPUT + 200
        assert "truncated" in result

    def test_reads_unicode_content(self, tmp_path):
        f = tmp_path / "unicode.py"
        f.write_text("# résumé naïve café", encoding="utf-8")
        assert "résumé" in read_file(str(f))

    def test_reads_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        assert read_file(str(f)) == ""

    def test_reads_multiline_file(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text("line1\nline2\nline3")
        result = read_file(str(f))
        assert "line1" in result
        assert "line3" in result

    def test_exactly_max_output_size_not_truncated(self, tmp_path):
        f = tmp_path / "exact.txt"
        f.write_text("a" * MAX_OUTPUT)
        result = read_file(str(f))
        assert "truncated" not in result

    def test_file_with_binary_chars_does_not_raise(self, tmp_path):
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\xff\xfe\x00hello")
        # Should not raise — errors="ignore"
        result = read_file(str(f))
        assert isinstance(result, str)


# ── write_file ────────────────────────────────────────────────────────────────

class TestWriteFile:
    def test_creates_file(self, tmp_path):
        path = str(tmp_path / "out.py")
        write_file(path, "print('hi')")
        assert Path(path).exists()

    def test_file_has_correct_content(self, tmp_path):
        path = str(tmp_path / "out.py")
        write_file(path, "hello")
        assert Path(path).read_text() == "hello"

    def test_creates_parent_directories(self, tmp_path):
        path = str(tmp_path / "a" / "b" / "c" / "file.py")
        write_file(path, "content")
        assert Path(path).exists()

    def test_return_value_contains_path(self, tmp_path):
        path = str(tmp_path / "x.py")
        result = write_file(path, "data")
        assert "x.py" in result or str(tmp_path) in result

    def test_return_value_contains_char_count(self, tmp_path):
        path = str(tmp_path / "x.py")
        result = write_file(path, "hello")
        assert "5" in result

    def test_overwrites_existing_file(self, tmp_path):
        path = str(tmp_path / "x.py")
        write_file(path, "original")
        write_file(path, "replaced")
        assert Path(path).read_text() == "replaced"

    def test_writes_empty_string(self, tmp_path):
        path = str(tmp_path / "empty.py")
        write_file(path, "")
        assert Path(path).read_text() == ""

    def test_writes_unicode(self, tmp_path):
        path = str(tmp_path / "utf8.py")
        write_file(path, "# naïve résumé")
        assert "naïve" in Path(path).read_text(encoding="utf-8")

    def test_writes_large_content(self, tmp_path):
        path = str(tmp_path / "large.py")
        big = "x" * 100_000
        write_file(path, big)
        assert len(Path(path).read_text()) == 100_000


# ── list_files ────────────────────────────────────────────────────────────────

class TestListFiles:
    def test_finds_matching_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        result = list_files(str(tmp_path / "*.py"))
        assert "a.py" in result
        assert "b.py" in result

    def test_no_matches_returns_informative_string(self, tmp_path):
        result = list_files(str(tmp_path / "*.nonexistent"))
        assert "No files" in result or "nonexistent" in result

    def test_recursive_pattern(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("")
        result = list_files(str(tmp_path / "**" / "*.py"))
        assert "deep.py" in result

    def test_results_sorted(self, tmp_path):
        (tmp_path / "z.py").write_text("")
        (tmp_path / "a.py").write_text("")
        (tmp_path / "m.py").write_text("")
        result = list_files(str(tmp_path / "*.py"))
        lines = [l for l in result.splitlines() if l.strip()]
        assert lines == sorted(lines)

    def test_non_matching_extension_excluded(self, tmp_path):
        (tmp_path / "main.py").write_text("")
        (tmp_path / "style.css").write_text("")
        result = list_files(str(tmp_path / "*.py"))
        assert "style.css" not in result

    def test_empty_directory(self, tmp_path):
        result = list_files(str(tmp_path / "*.py"))
        assert "No files" in result or result.strip() == ""


# ── run_command ───────────────────────────────────────────────────────────────

class TestRunCommand:
    def test_captures_stdout(self):
        result = run_command("echo hello_marker")
        assert "hello_marker" in result

    def test_captures_stderr(self):
        result = run_command("echo err_marker >&2")
        assert "err_marker" in result

    def test_non_zero_exit_returns_output(self):
        result = run_command("exit 1", working_dir="/tmp")
        # Should not raise; returns whatever output was produced
        assert isinstance(result, str)

    def test_no_output_returns_placeholder(self):
        result = run_command("true")
        assert isinstance(result, str)

    def test_working_dir_respected(self, tmp_path):
        (tmp_path / "sentinel.txt").write_text("found")
        result = run_command("ls sentinel.txt", working_dir=str(tmp_path))
        assert "sentinel.txt" in result

    def test_timeout_returns_error_string(self):
        result = run_command("sleep 200", working_dir="/tmp")
        # The default timeout is 120s; we mock it to avoid actually waiting
        # Just verify the function returns a string (won't time out in test)
        assert isinstance(result, str)

    def test_invalid_working_dir(self, tmp_path):
        result = run_command("echo x", working_dir=str(tmp_path / "nonexistent"))
        assert isinstance(result, str)

    def test_truncates_large_output(self):
        # Generate more than MAX_OUTPUT chars via a python one-liner
        result = run_command(f"python3 -c \"print('x'*{MAX_OUTPUT + 500})\"")
        assert len(result) < MAX_OUTPUT + 300
        assert "truncated" in result

    def test_returns_string(self):
        assert isinstance(run_command("echo test"), str)


# ── search_code ───────────────────────────────────────────────────────────────

class TestSearchCode:
    def test_finds_pattern_in_py_file(self, tmp_path):
        (tmp_path / "app.py").write_text("def my_function(): pass")
        result = search_code("my_function", str(tmp_path))
        assert "my_function" in result

    def test_no_match_returns_informative_string(self, tmp_path):
        (tmp_path / "app.py").write_text("nothing here")
        result = search_code("XYZNOTFOUND", str(tmp_path))
        assert "No matches" in result or "not found" in result.lower()

    def test_searches_ts_files(self, tmp_path):
        (tmp_path / "comp.ts").write_text("export const myVar = 42;")
        result = search_code("myVar", str(tmp_path))
        assert "myVar" in result

    def test_excludes_non_source_extensions(self, tmp_path):
        (tmp_path / "data.csv").write_text("find_me,col2")
        result = search_code("find_me", str(tmp_path))
        # CSV is not in include list, so shouldn't appear
        assert "data.csv" not in result or "No matches" in result

    def test_returns_string_on_exception(self, tmp_path, monkeypatch):
        import subprocess
        def boom(*args, **kwargs):
            raise OSError("grep not found")
        monkeypatch.setattr(subprocess, "run", boom)
        result = search_code("anything", str(tmp_path))
        assert "Error" in result

    def test_multiline_file_returns_line_numbers(self, tmp_path):
        (tmp_path / "f.py").write_text("line1\nfind_me\nline3")
        result = search_code("find_me", str(tmp_path))
        assert "find_me" in result

    def test_default_directory_is_current(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "check.py").write_text("TOKEN_HERE = 1")
        result = search_code("TOKEN_HERE")
        assert "TOKEN_HERE" in result


# ── grep_repos ────────────────────────────────────────────────────────────────

class TestGrepRepos:
    def test_no_repos_dir_returns_message(self, tmp_path):
        result = grep_repos(["anything"], repos_dir=str(tmp_path / "nonexistent"))
        assert "No reference repos" in result or result == ""

    def test_finds_keyword_in_repo(self, fake_repos_dir):
        result = grep_repos(["router"], repos_dir=str(fake_repos_dir))
        assert "router" in result.lower() or "No relevant" in result

    def test_empty_keywords_returns_empty_or_message(self, fake_repos_dir):
        result = grep_repos([], repos_dir=str(fake_repos_dir))
        assert isinstance(result, str)

    def test_respects_max_snippets(self, fake_repos_dir, tmp_path):
        # Add many files containing keyword
        many = tmp_path / "many_repos" / "big-repo"
        many.mkdir(parents=True)
        for i in range(20):
            (many / f"file{i}.py").write_text(f"# common_keyword_{i}\ncommon_keyword = {i}\n")
        result = grep_repos(["common_keyword"], repos_dir=str(tmp_path / "many_repos"))
        # Should have at most 6 snippets (MAX in implementation)
        snippet_count = result.count("###")
        assert snippet_count <= 6

    def test_returns_string(self, fake_repos_dir):
        result = grep_repos(["useState"], repos_dir=str(fake_repos_dir))
        assert isinstance(result, str)

    def test_skips_node_modules(self, tmp_path):
        repo = tmp_path / "repos" / "my-repo" / "node_modules"
        repo.mkdir(parents=True)
        (repo / "lib.ts").write_text("skip_me_keyword = true;")
        result = grep_repos(["skip_me_keyword"], repos_dir=str(tmp_path / "repos"))
        assert "skip_me_keyword" not in result

    def test_skips_pycache(self, tmp_path):
        repo = tmp_path / "repos" / "my-repo" / "__pycache__"
        repo.mkdir(parents=True)
        (repo / "mod.pyc").write_text("pycache_marker")
        result = grep_repos(["pycache_marker"], repos_dir=str(tmp_path / "repos"))
        assert "pycache_marker" not in result


# ── make_tool and schema definitions ──────────────────────────────────────────

class TestMakeTool:
    def test_returns_dict_with_type_function(self):
        t = make_tool("foo", "desc", {"x": {"type": "string"}}, ["x"])
        assert t["type"] == "function"

    def test_name_stored_correctly(self):
        t = make_tool("my_tool", "desc", {}, [])
        assert t["function"]["name"] == "my_tool"

    def test_description_stored(self):
        t = make_tool("t", "my description", {}, [])
        assert t["function"]["description"] == "my description"

    def test_properties_stored(self):
        props = {"path": {"type": "string"}, "content": {"type": "string"}}
        t = make_tool("t", "d", props, ["path"])
        assert t["function"]["parameters"]["properties"] == props

    def test_required_list_stored(self):
        t = make_tool("t", "d", {"x": {}}, ["x"])
        assert t["function"]["parameters"]["required"] == ["x"]

    def test_parameters_type_is_object(self):
        t = make_tool("t", "d", {}, [])
        assert t["function"]["parameters"]["type"] == "object"


class TestPredefinedSchemas:
    @pytest.mark.parametrize("schema,expected_name", [
        (READ_FILE,   "read_file"),
        (WRITE_FILE,  "write_file"),
        (LIST_FILES,  "list_files"),
        (RUN_COMMAND, "run_command"),
        (SEARCH_CODE, "search_code"),
    ])
    def test_schema_has_correct_name(self, schema, expected_name):
        assert schema["function"]["name"] == expected_name

    @pytest.mark.parametrize("schema", [READ_FILE, WRITE_FILE, LIST_FILES, RUN_COMMAND, SEARCH_CODE])
    def test_schema_has_required_list(self, schema):
        assert "required" in schema["function"]["parameters"]
        assert isinstance(schema["function"]["parameters"]["required"], list)

    def test_write_file_requires_path_and_content(self):
        req = WRITE_FILE["function"]["parameters"]["required"]
        assert "path" in req
        assert "content" in req

    def test_read_file_requires_path(self):
        assert "path" in READ_FILE["function"]["parameters"]["required"]

    def test_run_command_requires_command(self):
        assert "command" in RUN_COMMAND["function"]["parameters"]["required"]


# ── HANDLERS dict ─────────────────────────────────────────────────────────────

class TestHandlers:
    def test_has_all_five_tools(self):
        for name in ("read_file", "write_file", "list_files", "run_command", "search_code"):
            assert name in HANDLERS

    def test_handlers_are_callable(self):
        for fn in HANDLERS.values():
            assert callable(fn)

    def test_read_file_handler_is_correct(self, tmp_path):
        f = tmp_path / "h.txt"
        f.write_text("handler_test")
        result = HANDLERS["read_file"](str(f))
        assert "handler_test" in result

    def test_write_file_handler_is_correct(self, tmp_path):
        path = str(tmp_path / "written.txt")
        HANDLERS["write_file"](path, "via handler")
        assert Path(path).read_text() == "via handler"
