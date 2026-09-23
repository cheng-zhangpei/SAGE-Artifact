"""
@function      :
@time          :2026/8/3 15:38
"""
# sage/v2/tests/conftest.py

from __future__ import annotations

import pytest

from sage.v2.model import (
    Location,
    ToolModel,
    make_action,
    make_policy,
    make_state,
)


@pytest.fixture
def minimal_leak():
    """
    最小同调用读取泄露场景：

    - support Agent 上下文干净；
    - slot:file.T1 带 PII；
    - send_file 同一次调用读取 file.T1 并写 external.slack；
    - policy: external.slack 禁止 PII。

    无约束时应出现一步反例。
    DirectSAGE 应生成一条 guard 并阻断。
    """

    agent = "support"

    ctx = Location.ctx(agent)
    file_loc = Location.slot("file", "T1")
    external = Location.slot("external", "slack")

    send_file = make_action(
        agent=agent,
        tool="send_file",
        params={
            "file": "T1",
            "channel": "external",
        },
        reads=[ctx, file_loc],
        writes=[external],
        gen=[],
    )

    model = ToolModel(
        agents=frozenset({agent}),
        tools=frozenset({"send_file"}),
        locations=frozenset({ctx, file_loc, external}),
        labels=frozenset({"PII"}),
        actions=(send_file,),
    )

    policy = make_policy(
        {
            external: {"PII"},
        }
    )

    initial_state = make_state(
        {
            file_loc: {"PII"},
        }
    )

    return model, policy, initial_state
