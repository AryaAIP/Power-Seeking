"""Control Tower's built-in honest policy, with DeepSeek V4.1 Flash on OpenRouter pinned to DeepInfra fp8.

Use: ct run eval --policy ds_policy:deepseek_honest_policy ...   (with this folder on PYTHONPATH)
Everything except the model (prompts, planning phase, tools, 150-step cap) is the stock `honest` policy.
"""
from inspect_ai.agent import Agent, AgentSubmit
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import TaskState
from pydantic import Field

from control_tower.protocols.function_registry.tracked_model import TrackedModel
from control_tower.protocols.policies.policies.honest_untrusted.policy import HonestArgs, honest_policy

MODEL = "openrouter/deepseek/deepseek-v4.1-flash-1017"
PROVIDER = {"order": ["deepinfra/fp8"], "allow_fallbacks": False}


def _model() -> TrackedModel:
    return TrackedModel(
        MODEL,
        config=GenerateConfig(
            extra_body={"provider": dict(PROVIDER)},
            max_tokens=16000,
            reasoning_effort="medium",
            attempt_timeout=300,
            max_connections=10,
        ),
    )


class DeepSeekHonestArgs(HonestArgs):
    model: TrackedModel = Field(default_factory=_model)


def deepseek_honest_policy(state: TaskState, submit: AgentSubmit, args: DeepSeekHonestArgs | None) -> Agent:
    """Stock honest policy (exploration -> planning -> execution) driven by pinned DeepSeek V4.1 Flash."""
    return honest_policy(state, submit, args or DeepSeekHonestArgs())
