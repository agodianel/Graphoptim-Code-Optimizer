"""Tests for the CLI interface."""

from click.testing import CliRunner

from graphoptim.cli import main


class TestCLI:
    """Test the CLI commands."""

    def test_version(self):
        """--version should print version."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        """--help should print help text."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "GraphOptim" in result.output

    def test_analyze_help(self):
        """analyze --help should work."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output

    def test_optimize_help(self):
        """optimize --help should work."""
        runner = CliRunner()
        result = runner.invoke(main, ["optimize", "--help"])
        assert result.exit_code == 0

    def test_analyze_file(self, tmp_path):
        """Analyzing a real file should work."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(x):\n    return x + 1\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(test_file)])
        assert result.exit_code == 0

    def test_analyze_json_output(self, tmp_path):
        """JSON output format should work."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(x):\n    return x + 1\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", str(test_file), "--format", "json"])
        assert result.exit_code == 0

    def test_analyze_nonexistent(self):
        """Analyzing nonexistent file should fail gracefully."""
        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "/nonexistent.py"])
        assert result.exit_code != 0

    def test_config_show(self):
        """Config show should display settings."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "show"])
        assert result.exit_code == 0

    def test_optimize_dry_run(self, tmp_path):
        """Dry run optimization should print output."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(x):\n    return x\n    y = 1\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(main, ["optimize", str(test_file)])
        assert result.exit_code == 0
