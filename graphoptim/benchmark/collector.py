"""
Benchmark dataset collector for GraphOptim.

Downloads HumanEval and MBPP datasets and generates LLM solutions
using Claude Opus 4.6, GPT-5.2, and Gemini 2.5 Pro APIs.

API keys are loaded from environment variables:
    ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
"""

from __future__ import annotations

import ast
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from graphoptim.config import BenchmarkConfig


# Standard prompt for all models — identical as spec requires
SOLUTION_PROMPT = (
    "Write a Python function that solves the following problem. "
    "Return only the function code, no explanations.\n\n"
    "{problem_description}"
)

# Data directory relative to project root
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class BenchmarkProblem:
    """A single benchmark problem with solutions."""

    task_id: str
    prompt: str
    canonical_solution: str  # Human reference solution
    test: str  # Test cases
    llm_solutions: dict[str, str] = field(default_factory=dict)


class DatasetCollector:
    """
    Collects benchmark datasets and generates LLM solutions.

    Supports HumanEval (164 problems) and MBPP (974 problems).
    API keys are loaded from the BenchmarkConfig (environment variables).
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self._anthropic_client = None
        self._openai_client = None
        self._google_model = None

    def collect(self) -> list[BenchmarkProblem]:
        """
        Full pipeline: load dataset → filter to clean single-function
        problems → select N samples → generate LLM solutions.

        Returns:
            List of BenchmarkProblem objects with all solutions.
        """
        # Step 1: Load raw dataset
        if self.config.dataset == "humaneval":
            raw_problems = self._load_humaneval()
        else:
            raw_problems = self._load_mbpp()

        print(f"  Loaded {len(raw_problems)} raw problems from {self.config.dataset}")

        # Step 2: Filter to clean, single-function problems
        clean_problems = self._filter_single_function(raw_problems)
        print(f"  Filtered to {len(clean_problems)} clean single-function problems")

        # Step 3: Select N samples
        problems = clean_problems[: self.config.n_samples]
        print(f"  Selected {len(problems)} samples for benchmarking")

        # Step 4: Generate LLM solutions
        available_models = self.config.validate()
        if not available_models:
            print("  ⚠ No API keys found — skipping LLM solution generation")
            return problems

        print(f"  Generating solutions with: {', '.join(available_models)}")

        for i, problem in enumerate(problems):
            for model in available_models:
                try:
                    solution = self._generate_solution(model, problem.prompt)
                    problem.llm_solutions[model] = solution
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    print(f"    ⚠ {model} failed on {problem.task_id}: {e}")
                    problem.llm_solutions[model] = f"# Error: {e}"

            if (i + 1) % 10 == 0:
                print(f"    Progress: {i + 1}/{len(problems)} problems")

        return problems

    def _filter_single_function(
        self, problems: list[BenchmarkProblem]
    ) -> list[BenchmarkProblem]:
        """
        Filter to problems with clean, single-function human solutions.

        A 'clean' problem has a canonical solution that:
        1. Parses as valid Python
        2. Contains exactly one function definition
        3. Is not trivially empty
        """
        clean = []
        for problem in problems:
            solution = problem.canonical_solution
            if not solution or not solution.strip():
                continue

            try:
                # Try to parse: prompt + canonical (HumanEval format)
                # IMPORTANT: do NOT strip the canonical_solution — it's
                # indented as the function body in HumanEval
                full_source = problem.prompt + solution
                tree = ast.parse(full_source)

                # Count top-level function definitions
                func_count = sum(
                    1 for node in ast.iter_child_nodes(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                )

                if func_count == 1:
                    clean.append(problem)
            except SyntaxError:
                # Try the solution alone
                try:
                    tree = ast.parse(solution)
                    func_count = sum(
                        1 for node in ast.iter_child_nodes(tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    )
                    if func_count == 1:
                        clean.append(problem)
                except SyntaxError:
                    continue

        return clean

    def _load_humaneval(self) -> list[BenchmarkProblem]:
        """
        Load HumanEval dataset (164 problems).

        Uses the `human-eval` package if installed, otherwise
        falls back to loading from a JSONL file.
        """
        try:
            from human_eval.data import read_problems

            problems_dict = read_problems()
            problems = []
            for task_id, data in problems_dict.items():
                problems.append(
                    BenchmarkProblem(
                        task_id=task_id,
                        prompt=data["prompt"],
                        canonical_solution=data.get("canonical_solution", ""),
                        test=data.get("test", ""),
                    )
                )
            return problems
        except ImportError:
            # Fallback: load from JSONL file
            jsonl_path = DATA_DIR / "HumanEval.jsonl"
            if jsonl_path.exists():
                return self._load_from_jsonl(str(jsonl_path))
            print("  ⚠ human-eval package not installed and HumanEval.jsonl not found")
            print("    Install: uv pip install human-eval")
            return []

    def _load_mbpp(self) -> list[BenchmarkProblem]:
        """
        Load MBPP dataset (974 problems).

        Downloads from GitHub if not cached locally.
        """
        mbpp_path = DATA_DIR / "mbpp.jsonl"

        if not mbpp_path.exists():
            print("  Downloading MBPP dataset...")
            try:
                import urllib.request

                DATA_DIR.mkdir(parents=True, exist_ok=True)
                url = (
                    "https://raw.githubusercontent.com/google-research/"
                    "google-research/master/mbpp/mbpp.jsonl"
                )
                urllib.request.urlretrieve(url, str(mbpp_path))
                print("  ✓ MBPP downloaded")
            except Exception as e:
                print(f"  ⚠ Failed to download MBPP: {e}")
                return []

        return self._load_from_jsonl(str(mbpp_path))

    def _load_from_jsonl(self, filepath: str) -> list[BenchmarkProblem]:
        """Load problems from a JSONL file (works for both HumanEval & MBPP)."""
        problems = []
        path = Path(filepath)
        if not path.exists():
            return problems

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                # Handle both HumanEval and MBPP formats
                task_id = str(data.get("task_id", ""))
                prompt = data.get("prompt", data.get("text", ""))
                canonical = data.get("canonical_solution", data.get("code", ""))
                test = data.get("test", "")

                # MBPP has test_list instead of test
                if not test and "test_list" in data:
                    test = "\n".join(data["test_list"])

                problems.append(
                    BenchmarkProblem(
                        task_id=task_id,
                        prompt=prompt,
                        canonical_solution=canonical,
                        test=test,
                    )
                )

        return problems

    def _generate_solution(self, model: str, prompt: str) -> str:
        """Generate a solution using the specified LLM."""
        full_prompt = SOLUTION_PROMPT.format(problem_description=prompt)

        if model == "claude":
            return self._call_claude(full_prompt)
        elif model == "gpt4o":
            return self._call_gpt4o(full_prompt)
        elif model == "gemini":
            return self._call_gemini(full_prompt)
        else:
            raise ValueError(f"Unknown model: {model}")

    def _call_claude(self, prompt: str) -> str:
        """Call Claude Opus 4.6 API."""
        if self._anthropic_client is None:
            import anthropic

            self._anthropic_client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key
            )

        message = self._anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def _call_gpt4o(self, prompt: str) -> str:
        """Call GPT-5.2 API."""
        if self._openai_client is None:
            import openai

            self._openai_client = openai.OpenAI(
                api_key=self.config.openai_api_key
            )

        response = self._openai_client.chat.completions.create(
            model="gpt-5.2",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini 2.5 Pro API."""
        if self._google_model is None:
            import google.generativeai as genai

            genai.configure(api_key=self.config.google_api_key)
            self._google_model = genai.GenerativeModel("gemini-2.5-pro")

        response = self._google_model.generate_content(prompt)
        return response.text

    def save_dataset(
        self, problems: list[BenchmarkProblem], output_path: str
    ) -> None:
        """Save collected dataset to structured JSON."""
        data = []
        for p in problems:
            data.append(
                {
                    "task_id": p.task_id,
                    "prompt": p.prompt,
                    "canonical_solution": p.canonical_solution,
                    "test": p.test,
                    "llm_solutions": p.llm_solutions,
                }
            )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"  ✓ Dataset saved to {output_path} ({len(data)} problems)")
