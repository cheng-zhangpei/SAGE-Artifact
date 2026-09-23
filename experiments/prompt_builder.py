import json
# def build_system_prompt(description_md: str, tools_schema: list, policy_schema: dict) -> str:
#     guard_json_schema = {
#         "type": "array",
#         "items": {
#             "type": "object",
#             "properties": {
#                 "agent": {"type": "string"},
#                 "tool": {"type": "string"},
#                 "params": {"type": "object"},
#
#                 "forbidden_labels": {"type": "array", "items": {"type": "string"}}
#             },
#             "required": ["agent", "tool", "params", "forbidden_labels"]
#         }
#     }
#
#     return f"""You are an expert security engineer. Generate runtime guards to prevent forbidden data flows.
#
# ### System Description
# {description_md}
#
# # ### Tool Data-Flow Semantics (Human-Confirmed Model)
# # {json.dumps(tools_schema, indent=2)}
#
# ### Security Policy (Forbidden Flows)
# {json.dumps(policy_schema, indent=2)}
#
# ### Guard JSON Schema
# {json.dumps(guard_json_schema, indent=2)}
#
# ### Rules
# 1. Event taint (eta) = Gen(u) UNION (taint of all locations in Rd(u)).
# 2. Guard blocks if eta intersects with forbidden labels of Wr(u).
# 3. Consider same-invocation reads and parameter-dependent targets.
# 4. CRITICAL: Output ONLY the raw JSON array. NO markdown, NO explanations, NO thinking process. Start with '[' and end with ']'. Keep output under 2000 tokens.
# """


def build_system_prompt(description_md: str, tools_schema: list, policy_schema: dict) -> str:
    guard_json_schema = {
        "guards": [
            {
                "agent": "exact agent from Available Tools",
                "tool": "exact tool from Available Tools",
                "params": {
                    "exact_parameter_name": "exact_parameter_value"
                },
                "forbidden_labels": ["LABEL"]
            }
        ]
    }

    return f"""You are an expert security engineer. Generate runtime guards to prevent forbidden data flows.
### System Description
{description_md}
### Available Tools
{json.dumps(tools_schema, indent=2)}
### Security Policy
{json.dumps(policy_schema, indent=2)}
### Output Format
Output exactly one JSON object with a single top-level key named "guards":
{json.dumps(guard_json_schema, indent=2)}

### Rules
1. Event taint (eta) = Gen(u) UNION (taint of all locations in Rd(u)).
2. Guard blocks if eta intersects with forbidden labels of Wr(u).
3. Consider same-invocation reads and parameter-dependent targets.
4. Every guard's agent, tool, and complete params object MUST be copied exactly
   from one concrete entry in Available Tools. Params use exact matching only.
5. Never use "*" or another glob as a parameter value. Do not invent tools or
   parameter combinations that are absent from Available Tools.
6. The example above describes the output shape; do not copy its placeholder
   strings. If no guard is needed, output {{"guards":[]}}.
7. CRITICAL: Output ONLY the JSON object. NO markdown, explanations, schema
   wrappers, or thinking process. Start with '{{' and end with '}}'. Keep the
   output under 2000 tokens.
"""
def build_initial_user_prompt() -> str:
    return (
        'Generate initial guards. Output exactly {"guards":[...]} as one JSON '
        "object. Use only exact Available Tools entries."
    )

def build_counterexample_user_prompt(cex_json: dict, current_guards: list) -> str:
    return f"""VERIFICATION FAILED. Counterexample:
{json.dumps(cex_json, separators=(',', ':'))}

Fix your guards to block this event. Output ONLY the complete revised object
in the form {{"guards":[...]}}. Use exact Available Tools entries and never use
"*" as a parameter value. NO markdown or explanations.
"""

def build_self_review_user_prompt() -> str:
    return """Re-examine your guards against the system description and tool semantics above.

Systematically check each of the following:
1. For EVERY tool that writes to a location with forbidden labels: is there a guard covering it?
2. For each such tool: does the guard account for ALL locations in its 'reads' list (same-invocation reads)?
3. For each such tool: does the guard account for its 'gen' labels?
4. If a tool has multiple parameter values that write to DIFFERENT targets: are there separate guards for each sensitive target?
5. Are the 'forbidden_labels' in each guard correct and complete (OR semantics: ANY forbidden label triggers)?

If you find gaps, fix them. Output the COMPLETE revised object in the form
{"guards":[...]}. Use exact Available Tools entries and never use "*" as a
parameter value. CRITICAL: NO markdown or explanations.
"""
#
# def build_initial_user_prompt() -> str:
#     return "Please generate the initial set of candidate guards based on the system description and policy. Output strictly the raw JSON array starting with '['."
#
# def build_counterexample_user_prompt(cex_json: dict, current_guards: list) -> str:
#     return f"""The candidate guards you provided above failed verification.
# Here is the shortest counterexample (violating trace) found by the formal verifier:
#
# {json.dumps(cex_json, indent=2)}
#
# Analyze why your guards did not block this event, then output the COMPLETE revised list of guards.
#
# CRITICAL: Output ONLY a raw JSON array. No markdown, no explanations. Start with '[' and end with ']'. Keep the JSON compact (no unnecessary whitespace).
# """
#
# def build_self_review_user_prompt() -> str:
#     return """Please carefully review your guards for any missing rules, incorrect parameter filters, or overlooked data flows. Consider all tools, parameters, same-invocation resource reads, tool-generated labels, and parameter-dependent write targets. Output the complete revised list of guards.
#
# CRITICAL: Output ONLY a raw JSON array. No markdown, no explanations. Start with '[' and end with ']'.
# """
def build_verdict_only_user_prompt(violating_count: int) -> str:
    return f"""VERIFICATION FAILED.
The verifier found {violating_count} violating trace(s). Your guards are NOT safe.
Review and fix them. Output ONLY the complete revised object in the form
{{"guards":[...]}}. Use exact Available Tools entries and never use "*" as a
parameter value. NO markdown or explanations.
"""
