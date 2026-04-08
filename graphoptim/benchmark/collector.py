"""
Benchmark dataset collector for GraphOptim.

Downloads HumanEval and MBPP datasets and generates LLM solutions
using Claude Opus 4.6, GPT-5.2, and Gemini 2.5 Pro APIs.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from graphoptim.config import BenchmarkConfig


# Standard prompt for all models
SOLUTION_PROMPT = (
    "Write a Python function that solves the following problem. "
    "Return only the function code, no explanations.\n\n"
    "{problem_description}"
)


@dataclass
class BenchmarkProblem:
    """A single benchmark problem with solutions."""

    task_id: str
    prompt: str
    canonical_solution: str  # Human reference solution
    test: str  # Test cases
    llm_solutions: dict[str, str]  # model_name → solution


class DatasetCollector:
    """
    Collects benchmark datasets and generates LLM solutions.

    Supports HumanEval and MBPP datasets.
    API keys are loaded from the BenchmarkConfig (environment variables).
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self._anthropic_client = None
        self._openai_client = None
        self._google_model = None

    def collect(self) -> list[BenchmarkProblem]:
        """
        Collect dataset and generate LLM solutions.

        Returns:
            List of BenchmarkProblem objects with solutions.
        """
        # Load dataset
        if self.config.dataset == "humaneval":
            problems = self._load_humaneval()
        else:
            problems = self._load_mbpp()

        # Select N samples
        problems = problems[: self.config.n_samples]

        # Generate LLM solutions
        available_models = self.config.validate()
        for problem in problems:
            for model in available_models:
                try:
                    solution = self._generate_solution(model, problem.prompt)
                    problem.llm_solutions[model] = solution
                    time.sleep(0.5)  # Rate limiting
                except Exception as e:
                    problem.llm_solutions[model] = f"# Error: {e}"

        return problems

    def _load_humaneval(self) -> list[BenchmarkProblem]:
        """Load HumanEval dataset."""
        try:
            # Try to load from the human-eval package
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
                        llm_solutions={},
                    )
                )
            return problems
        except ImportError:
            # Fallback: load from JSONL file if available
            return self._load_from_jsonl("HumanEval.jsonl")

    def _load_mbpp(self) -> list[BenchmarkProblem]:
        """Load MBPP dataset."""
        try:
            mbpp_path = Path("mbpp.jsonl")
            if mbpp_path.exists():
                return self._load_from_jsonl("mbpp.jsonl")

            # Try to download
            import urllib.request

            url = "https://raw.githubusercontent.com/google-research/google-research/master/mbpp/mbpp.jsonl"
            urllib.request.urlretrieve(url, "mbpp.jsonl")
            return self._load_from_jsonl("mbpp.jsonl")
        except Exception:
            return []

    def _load_from_jsonl(self, filepath: str) -> list[BenchmarkProblem]:
        """Load problems from a JSONL file."""
        problems = []
        path = Path(filepath)
        if not path.exists():
            return problems

        with open(path, encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                problems.append(
                    BenchmarkProblem(
                        task_id=data.get("task_id", data.get("task_id", "")),
                        prompt=data.get("prompt", data.get("text", "")),
                        canonical_solution=data.get(
                            "canonical_solution", data.get("code", "")
                        ),
                        test=data.get("test", ""),
                        llm_solutions={},
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
        """Call Claude API."""
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
        """Call GPT-4o API."""
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
        """Call Gemini API."""
        if self._google_model is None:
            import google.generativeai as genai

            genai.configure(api_key=self.config.google_api_key)
            self._google_model = genai.GenerativeModel("gemini-2.5-pro")

        response = self._google_model.generate_content(prompt)
        return response.text

    def save_dataset(
        self, problems: list[BenchmarkProblem], output_path: str
    ) -> None:
        """Save collected dataset to JSON."""
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
