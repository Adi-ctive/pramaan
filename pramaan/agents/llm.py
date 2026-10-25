"""Reasoning LLM through Ollama with native tool calling, plus per-application budgets."""
import json
import os
import time

import httpx

URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    """Per-application limits: LLM steps, tokens and wall-clock seconds (05_SECURITY.md §9)."""

    def __init__(self, max_steps=None, max_tokens=None, seconds=None):
        self.max_steps = max_steps or int(os.environ.get("AGENT_MAX_STEPS", "90"))
        self.max_tokens = max_tokens or int(os.environ.get("AGENT_MAX_TOKENS", "200000"))
        self.deadline = time.time() + (seconds or int(os.environ.get("AGENT_TIMEOUT_S", "900")))
        self.steps = self.tokens_in = self.tokens_out = 0

    def charge(self, tin, tout):
        self.steps += 1
        self.tokens_in += tin
        self.tokens_out += tout
        if self.steps > self.max_steps:
            raise BudgetExceeded(f"step budget {self.max_steps} exceeded")
        if self.tokens_in + self.tokens_out > self.max_tokens:
            raise BudgetExceeded(f"token budget {self.max_tokens} exceeded")
        if time.time() > self.deadline:
            raise BudgetExceeded("wall-clock budget exceeded")


def reachable():
    try:
        r = httpx.get(f"{URL}/api/tags", timeout=2)
        return r.status_code == 200 and any(m.get("name") in (MODEL, MODEL + ":latest") for m in r.json().get("models", []))
    except Exception:
        return False


def chat(messages, tools=None, max_tokens=500):
    """One Ollama chat call. Returns (message, tokens_in, tokens_out, ms)."""
    t = time.perf_counter()
    body = {"model": MODEL, "messages": messages, "stream": False, "keep_alive": "15m",
            "options": {"temperature": 0, "num_predict": max_tokens, "num_ctx": 8192, "seed": 7}}
    if tools:
        body["tools"] = tools
    r = httpx.post(f"{URL}/api/chat", json=body, timeout=180)
    r.raise_for_status()
    j = r.json()
    return j["message"], j.get("prompt_eval_count", 0), j.get("eval_count", 0), round((time.perf_counter() - t) * 1000)


def dumps(o):
    return json.dumps(o, default=str, ensure_ascii=False)
