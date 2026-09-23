"""Minimal OpenAI-compatible client used by the SAGE LLM experiments.

The official SDK is preferred when installed.  A standard-library transport is
kept as a reproducibility fallback so that an unavailable optional dependency
does not prevent a run.
"""

import json
import os
import re
import urllib.request

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class SAGE_LLM_Client:
    def __init__(self, model="mimo-v2.5-pro"):
        self.api_key = os.environ.get("MIMO_API_KEY")
        if not self.api_key:
            raise ValueError("Please set MIMO_API_KEY environment variable.")

        self.base_url = "https://token-plan-cn.xiaomimimo.com/v1"
        self.client = (
            OpenAI(api_key=self.api_key, base_url=self.base_url)
            if OpenAI is not None
            else None
        )
        self.transport = "openai-sdk" if self.client is not None else "stdlib-urllib"
        self.model = model
        self.total_tokens = 0
        self.cache_hit_tokens = 0
        self.last_raw_content = None
        self.last_parse_error = None
        self.last_finish_reason = None

    def reset_stats(self):
        self.total_tokens = 0
        self.cache_hit_tokens = 0

    def _create_completion(self, messages, temperature, max_tokens, json_mode=True):
        """Return a completion normalized to a small plain-dictionary shape."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        if self.client is not None:
            response = self.client.chat.completions.create(**kwargs)
            usage = response.usage
            choice = response.choices[0]
            return {
                "content": choice.message.content,
                "finish_reason": choice.finish_reason,
                "usage": {
                    "total_tokens": getattr(usage, "total_tokens", 0) or 0,
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "prompt_cache_hit_tokens": getattr(
                        usage, "prompt_cache_hit_tokens", 0
                    )
                    or 0,
                },
            }

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(kwargs).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SAGE-experiment/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        choice = payload["choices"][0]
        usage = payload.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        return {
            "content": (choice.get("message") or {}).get("content"),
            "finish_reason": choice.get("finish_reason"),
            "usage": {
                "total_tokens": usage.get("total_tokens", 0) or 0,
                "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                "prompt_cache_hit_tokens": (
                    usage.get("prompt_cache_hit_tokens", 0)
                    or prompt_details.get("cached_tokens", 0)
                    or 0
                ),
            },
        }

    def chat(self, messages, temperature=0.2, max_tokens=4096 * 4):
        self.last_raw_content = None
        self.last_parse_error = None
        self.last_finish_reason = None
        try:
            response = self._create_completion(
                messages, temperature, max_tokens, json_mode=True
            )
            usage = response["usage"]
            finish_reason = response["finish_reason"]
            self.last_finish_reason = finish_reason
            self.total_tokens += usage["total_tokens"]
            self.cache_hit_tokens += usage["prompt_cache_hit_tokens"]

            cache_info = ""
            if usage["prompt_cache_hit_tokens"] > 0:
                cache_info = (
                    f" [Cache Hit: {usage['prompt_cache_hit_tokens']}/"
                    f"{usage['prompt_tokens']} tokens]"
                )
            print(
                f"  LLM Call: tokens={usage['total_tokens']}{cache_info} "
                f"| Finish: {finish_reason} | Transport: {self.transport}"
            )

            content = response["content"]
            self.last_raw_content = content
            if finish_reason == "length":
                print("  [Warning] Output truncated. Trying partial JSON extraction.")

            if not content:
                print("  [Fallback] Empty content. Retrying without JSON mode.")
                fallback_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            'Output ONLY one JSON object in the form '
                            '{"guards":[...]}. No text. Max 300 tokens.'
                        ),
                    }
                ]
                response = self._create_completion(
                    fallback_messages, temperature, max_tokens, json_mode=False
                )
                content = response["content"]
                self.last_raw_content = content
                self.last_finish_reason = response["finish_reason"]
                self.total_tokens += response["usage"]["total_tokens"]
                self.cache_hit_tokens += response["usage"][
                    "prompt_cache_hit_tokens"
                ]
                if not content:
                    self.last_parse_error = "empty response content"
                    return None

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            markdown = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if markdown:
                try:
                    return json.loads(markdown.group(1))
                except json.JSONDecodeError:
                    pass

            # Legacy providers occasionally return a bare guard array.  The
            # strict candidate parser records that response as a format error.
            array = re.search(r"\[[\s\S]*\]", content)
            if array:
                try:
                    return json.loads(array.group(0))
                except json.JSONDecodeError:
                    pass

            if finish_reason == "length":
                bracket_count = 0
                last_valid_pos = -1
                for index, character in enumerate(content):
                    if character == "[":
                        bracket_count += 1
                    elif character == "]":
                        bracket_count -= 1
                    elif character == "}" and bracket_count == 1:
                        last_valid_pos = index
                if last_valid_pos > 0:
                    try:
                        return json.loads(content[: last_valid_pos + 1] + "]")
                    except json.JSONDecodeError:
                        pass

            print("  [Error] Failed to parse JSON.")
            print(f"  Raw (first 500): {content[:500]}")
            self.last_parse_error = "response content is not valid JSON"
            return None
        except Exception as error:
            print(f"  [Error] API call failed: {error}")
            self.last_parse_error = f"{type(error).__name__}: {error}"
            return None
