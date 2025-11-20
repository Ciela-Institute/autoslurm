#!/usr/bin/env python
"""
LLM-driven agent demo that reads the agent docs and crafts ACP requests.

Set `OPENAI_API_KEY` in your environment to let this script call OpenAI's chat
completion API. When not available it will still run with a very simple
fallback strategy so you can inspect how the docs would be used.
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional

from autoslurm.acp import action_definitions, execute_acp
from autoslurm.context import agent_context


class LLMClient:
    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
        self.openai, self.client = self._import_openai()

    def _import_openai(self):
        try:
            import openai

            client = None
            if hasattr(openai, "OpenAI"):
                client = openai.OpenAI()
            return openai, client
        except ImportError:
            return None, None

    def compose_schedule_request(
        self, docs: str, actions: Dict[str, dict]
    ) -> Dict[str, object]:
        if self.openai and os.environ.get("OPENAI_API_KEY"):
            prompt = self._build_prompt(docs, actions)
            if self.client:
                print("Using Client")
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an AutoSlurm agent that speaks ACP.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = completion.choices[0].message.content.strip()
            else:
                print("using openai old API")
                completion = self.openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an AutoSlurm agent that speaks ACP.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = completion.choices[0].message.content.strip()
            return json.loads(content)
        else:
            raise ValueError
            # # Fallback for offline testing.
            # bundle = "llm_agent_bundle"
            # job = {
                # "name": "llm_job",
                # "script": "python tests/scripts/hello_script.py",
                # "slurm": {"time": "00:02:00", "cpus_per_task": 1, "mem": "1G"},
            # }
            # return {"action": "schedule", "bundle": bundle, "job": job, "append": False}

    def _build_prompt(self, docs: str, actions: Dict[str, dict]) -> str:
        action_list = "\n".join(
            f"- {name}: {meta['description']}" for name, meta in actions.items()
        )
        return (
            "You have read the compiled AutoSlurm agent reference. "
            "Compose an ACP JSON payload that schedules a small script. "
            f"Available actions:\n{action_list}\n"
            # "Documentation:\n"
            # f"{docs}\n"
            "Respond with raw JSON only."
        )


def run_agent():
    """
    Observation: including the docs is too much context. The agent does not do a proper job.
    Not included is perhaps not enough context. The agent outputs the correct schema (ACP), 
    but there is some variability in the output which ultimately renders invalid the action.
    The next agent demo will include a more refined workflow where we included engineered context 
    for each task.
    """
    docs = agent_context()
    print(f"[Agent] Loaded {len(docs)} characters of documentation.")
    actions = action_definitions()
    print("[Agent] Available ACP actions:", ", ".join(actions.keys()))

    llm = LLMClient()
    request = llm.compose_schedule_request(docs, actions)
    print("[Agent] Generated request:\n", json.dumps(request, indent=4))
    response = execute_acp(request)
    print("[Agent] Response:\n", json.dumps(response, indent=4))


if __name__ == "__main__":
    run_agent()
