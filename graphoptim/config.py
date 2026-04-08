"""
Configuration dataclasses for GraphOptim.

All configuration is done via dataclasses with sensible defaults.
API keys are loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AnalyzeConfig:
    """Configuration for analysis operations."""

    bottleneck_threshold: float = 0.7
    max_chain_depth: int = 8
    cc_threshold: int = 7
    verbose: bool = False
    output_format: str = "text"  # "text", "json", "html"


@dataclass
class OptimizeConfig:
    """Configuration for optimization operations."""

    passes: Optional[list[str]] = None  # None = auto-select via knapsack
    budget: float = 0.6
    max_changes: int = 10
    min_improvement: float = 0.1
    dry_run: bool = True  # Safe default — preview only
    create_backup: bool = True


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark operations."""

    # API keys loaded from environment
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", "")
    )
    google_api_key: str = field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_API_KEY", os.environ.get("GEMINI_API_KEY", "")
        )
    )

    n_samples: int = 100
    dataset: str = "humaneval"  # "humaneval" or "mbpp"
    models: list[str] = field(
        default_factory=lambda: ["claude", "gpt4o", "gemini"]
    )
    output_dir: str = "benchmark_results"

    def validate(self) -> list[str]:
        """Validate configuration and return list of available models."""
        available = []
        if self.anthropic_api_key and "claude" in self.models:
            available.append("claude")
        if self.openai_api_key and "gpt4o" in self.models:
            available.append("gpt4o")
        if self.google_api_key and "gemini" in self.models:
            available.append("gemini")
        return available


@dataclass
class GraphOptimConfig:
    """Top-level configuration combining all sub-configs."""

    analyze: AnalyzeConfig = field(default_factory=AnalyzeConfig)
    optimize: OptimizeConfig = field(default_factory=OptimizeConfig)
    benchmark: BenchmarkConfig = field(default_factory=BenchmarkConfig)
