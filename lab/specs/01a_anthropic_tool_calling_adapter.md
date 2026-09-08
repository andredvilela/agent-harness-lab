# Stage 01A — Anthropic Tool Calling Adapter

Status: **SPEC — Stage 01 instrumentation/completeness work**  
Project: **Agent Harness Lab**

---

## 1. Purpose

Stage 01 already introduced the first real agent harness loop:

```text
MODEL
  ↓
structured tool request
  ↓
MiniHarness AgentLoop
  ↓
ToolRegistry
  ↓
list_files / read_file
  ↓
ToolResult
  ↓
MODEL
```

The current implementation successfully supports this loop through the OpenAI Responses API.

Anthropic support currently exists only for naked model calls from Stage 00B.

The Anthropic adapter must now be extended so that the **same provider-neutral Stage 01 AgentLoop** can operate through the Anthropic Messages API.

The objective is:

```text
same AgentLoop
same ToolDefinition
same ToolCall
same ToolResult
same tools
same task

different provider adapter
```

Target architecture:

```text
                        MiniHarness
                            
                    provider-neutral
                    AgentLoop
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
       OpenAI Adapter          Anthropic Adapter
             │                       │
             ▼                       ▼
     Responses API            Messages API
             │                       │
             ▼                       ▼
       tool calling             tool_use
             │                       │
             └───────────┬───────────┘
                         ▼
                    ToolRegistry
                         │
                 list_files/read_file
```

This change must **not add any new agent capability**.

---

# 2. Didactic objective

This implementation should make the adapter boundary concrete.

We want to learn that:

```text
AgentLoop semantics
        ≠
provider wire protocol
```

MiniHarness should think in concepts such as:

```text
Message
ToolDefinition
ToolCall
ToolResult
ModelTurn
```

while each provider adapter translates those concepts into its own API representation.

For Anthropic:

```text
ToolDefinition
      ↓
Anthropic tool definition with input_schema

Anthropic tool_use block
      ↓
ToolCall

ToolResult
      ↓
Anthropic user/tool_result block
```

Do not hide these differences behind LiteLLM or another normalization library.

Understanding them is part of the lab.

---

# 3. Scope

Implement only the Anthropic support required for the existing Stage 01 loop:

```text
tool definitions
tool_use parsing
assistant tool-use history
tool_result messages
multi-turn conversation
multiple tool calls in one response
tool errors through is_error
usage normalization
final text extraction
```

Do not add any new MiniHarness tools.

Available tools remain exactly:

```text
list_files
read_file
```

---

# 4. Preserve the existing AgentLoop

The existing Stage 01 `AgentLoop` should remain conceptually unchanged.

Do not create:

```text
AnthropicAgentLoop
ClaudeAgent
AnthropicToolRunner
provider-specific orchestration
```

There must continue to be only one MiniHarness-owned loop.

Conceptually:

```python
while not done:
    turn = model.generate(
        messages=messages,
        tools=tool_definitions,
    )

    if turn.tool_calls:
        execute tools
        append results
        continue

    return turn.text
```

Provider-specific behavior belongs inside the model adapter.

---

# 5. Preserve provider-neutral internal types

Do not redesign the existing model abstractions unless a minimal change is genuinely required.

Continue using the current concepts such as:

```text
Message
ToolDefinition
ToolCall
ToolResult
ModelTurn
```

The Anthropic adapter must convert between those internal concepts and Anthropic's Messages API format.

Avoid creating Anthropic-specific types outside the Anthropic adapter.

For example, the AgentLoop should never need to inspect:

```text
tool_use
tool_result
input_schema
stop_reason
```

Those are provider protocol details.

---

# 6. Anthropic request format

Use the official Python SDK:

```python
from anthropic import Anthropic
```

and:

```python
client.messages.create(...)
```

The request should conceptually look like:

```python
response = client.messages.create(
    model=model,
    max_tokens=max_output_tokens,
    messages=anthropic_messages,
    tools=anthropic_tools,
)
```

Do not explicitly set:

```text
temperature
top_p
top_k
thinking
tool_choice
system prompt
```

unless some existing Stage 01 configuration already requires them.

Use provider/model defaults.

The experiment must remain as comparable as reasonably possible to the existing Stage 01 OpenAI run.

---

# 7. Convert MiniHarness tool definitions to Anthropic format

MiniHarness currently has provider-neutral tool definitions conceptually equivalent to:

```text
name
description
JSON Schema parameters
```

Anthropic expects tools shaped conceptually as:

```json
{
  "name": "read_file",
  "description": "Read the contents of a repository-relative text file.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Repository-relative path of the text file to read."
      }
    },
    "required": ["path"]
  }
}
```

The important mapping is:

```text
MiniHarness parameters
        ↓
Anthropic input_schema
```

Implement this translation inside the Anthropic adapter.

Do not change the provider-neutral tool schemas merely to make Anthropic easier to support.

The existing `list_files` and `read_file` contracts must remain unchanged.

---

# 8. Parse Anthropic responses

Anthropic responses contain an ordered list of content blocks.

The adapter must iterate through:

```python
response.content
```

and recognize at least:

```text
text
tool_use
```

Do not assume that a response contains only one block.

Do not assume that a tool call is the last content block.

Do not assume that there can be only one tool call.

---

# 9. Extract text blocks

For every content block whose type is:

```text
text
```

collect the textual content.

The provider-neutral `ModelTurn.text` should contain the visible textual response assembled from those text blocks.

Preserve block ordering when combining visible text.

If there is no text:

```text
ModelTurn.text = ""
```

is acceptable.

Do not expose internal reasoning/thinking as `ModelTurn.text`.

---

# 10. Parse `tool_use` blocks

For every Anthropic content block with:

```text
type = "tool_use"
```

create a provider-neutral:

```python
ToolCall
```

mapping:

```text
Anthropic block.id
        → ToolCall.id

Anthropic block.name
        → ToolCall.name

Anthropic block.input
        → ToolCall.arguments
```

Conceptually:

```python
ToolCall(
    id=block.id,
    name=block.name,
    arguments=dict(block.input),
)
```

Do not reinterpret tool arguments.

Do not validate them in the adapter beyond what is required to construct the internal type.

Argument validation and execution belong to the ToolRegistry/tool implementation.

---

# 11. Multiple tool calls

Anthropic may return more than one `tool_use` block in a single response.

The adapter must preserve all of them.

Example conceptual response:

```text
assistant content:

tool_use → read_file(A)
tool_use → read_file(B)
tool_use → read_file(C)
```

must become:

```python
ModelTurn(
    tool_calls=[
        ToolCall(...A...),
        ToolCall(...B...),
        ToolCall(...C...),
    ]
)
```

Do not collapse them.

Do not execute them inside the adapter.

Execution remains the responsibility of the existing AgentLoop + ToolRegistry.

---

# 12. Anthropic tool-use conversation structure

This is a critical requirement.

When Claude returns a tool call, the next API request must preserve the assistant turn that produced the tool call.

The conversation should conceptually become:

```text
USER
original task

ASSISTANT
[
  tool_use(...)
]

USER
[
  tool_result(...)
]

ASSISTANT
next model response
```

Therefore the adapter must ensure that the assistant response containing the original `tool_use` blocks can be represented in the next Anthropic request.

Do not convert the assistant tool-use turn into plain text.

The `tool_use` structure must survive across calls.

---

# 13. Tool results

MiniHarness `ToolResult` objects must be translated into Anthropic `tool_result` blocks.

Conceptually:

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_...",
      "content": "..."
    }
  ]
}
```

The mapping is:

```text
ToolResult.tool_call_id
        ↓
tool_use_id

ToolResult.output
        ↓
content
```

The pairing must use the original Anthropic `tool_use` ID.

Do not generate a new ID.

---

# 14. Tool errors

The existing Stage 01 ToolRegistry returns explicit failed `ToolResult`s.

Map tool failure to Anthropic:

```text
is_error = true
```

Conceptually:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_...",
  "is_error": true,
  "content": "File not found: ..."
}
```

For successful results:

```text
is_error = false
```

may be supplied or omitted if the SDK/API defaults appropriately.

Prefer explicitness if it keeps the mapping clearer.

The important behavior is:

```text
tool execution failure
        ↓
Anthropic tool_result is_error=true
        ↓
Claude receives truthful environment observation
        ↓
Claude decides how to recover
```

Do not add automatic retry logic.

---

# 15. Multiple tool results

If one Anthropic model response requests several tools, the results should be returned together in the next user content message when compatible with the existing AgentLoop.

Conceptually:

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_A",
      "content": "..."
    },
    {
      "type": "tool_result",
      "tool_use_id": "toolu_B",
      "content": "..."
    }
  ]
}
```

Preserve the correspondence between each result and its `tool_use_id`.

Do not invent one user turn per result unless the existing internal AgentLoop architecture makes that unavoidable.

Prefer matching Anthropic's natural multiple-tool-result representation.

---

# 16. Preserve full assistant content for tool-use turns

Do not reconstruct an Anthropic assistant tool-use turn from only:

```text
text
+
normalized ToolCall
```

if doing so would discard provider content required for continuation.

Preserve the complete assistant content blocks required to continue the conversation correctly.

In particular, if the response contains provider-native blocks surrounding a `tool_use`, do not silently discard them before the subsequent request.

A minimal provider-private representation inside the Anthropic adapter is acceptable if required to preserve the original assistant turn.

Do not leak that representation into the rest of MiniHarness.

---

# 17. Thinking blocks

This deserves explicit handling even though Stage 01 should not enable thinking manually.

If Anthropic returns content blocks of type:

```text
thinking
redacted_thinking
```

during a tool-use turn, preserve them exactly as returned when replaying that assistant turn in the subsequent Messages API request.

Do not:

```text
summarize
rewrite
extract
reorder
partially remove
convert them into text
```

Do not surface thinking content to the user.

Do not add thinking content to `ModelTurn.text`.

Do not introduce custom thinking configuration.

The adapter's responsibility is simply:

> if provider-native continuation requires a block to be preserved, preserve it faithfully.

---

# 18. Provider-private conversation state

If the current provider-neutral `Message` representation cannot faithfully preserve Anthropic's assistant content blocks, solve this using the smallest possible mechanism.

Acceptable approaches include a small opaque/provider-private payload associated with an assistant turn.

For example, conceptually:

```text
Message
├── normalized semantic fields
└── provider_state (optional / opaque)
```

or equivalent.

However:

- do not redesign the entire conversation model;
- do not expose Anthropic types to AgentLoop;
- do not create a generic plugin/middleware architecture;
- do not force OpenAI to use Anthropic-specific concepts.

The purpose is only to preserve the provider wire semantics that cannot safely be reconstructed after normalization.

If the current design already preserves sufficient information, do not add anything.

---

# 19. Stop reason

Anthropic may return:

```text
stop_reason = "tool_use"
```

when Claude is requesting tools.

Parse this if useful for validation/debugging.

However, the MiniHarness AgentLoop should primarily decide whether to continue based on:

```text
ModelTurn.tool_calls
```

rather than embedding Anthropic-specific stop reasons in its control flow.

Do not expose `stop_reason` as a provider-neutral agent primitive unless already present.

---

# 20. Usage normalization

Populate existing provider-neutral usage fields:

```text
input_tokens
output_tokens
```

from Anthropic's:

```text
response.usage.input_tokens
response.usage.output_tokens
```

Do not yet add:

```text
cache_read_input_tokens
cache_creation_input_tokens
reasoning tokens
cost
```

Those belong to later observability/economics work.

Stage 01 semantic telemetry should continue aggregating:

```text
input_tokens
output_tokens
```

across model calls.

---

# 21. Do not modify the tools

The existing provider-neutral definitions for:

```text
list_files
read_file
```

must remain unchanged.

Do not change:

```text
tool names
descriptions
argument descriptions
required fields
path semantics
max_depth semantics
ToolRegistry execution behavior
```

Otherwise the Anthropic comparison would vary both:

```text
provider
+
tool interface
```

We want to vary only the provider adapter.

---

# 22. Do not modify the task

Use exactly:

```text
scenarios/01_read_only_agent/task.md
```

Do not create an Anthropic-specific prompt.

Do not add:

```text
"Use the tools."
"Inspect the repository."
"Call list_files first."
"You have read-only access."
```

The model must discover the action space through the same tool definitions exposed to OpenAI.

---

# 23. Do not add system instructions

Do not add an Anthropic-specific:

```text
system
```

message.

Stage 01 currently tests:

```text
task
+
tools
```

not prompt engineering.

Provider comparison must remain as clean as reasonably possible.

---

# 24. Do not use Anthropic's automatic tool runner

Even if the Anthropic SDK offers helper abstractions or automatic tool runners, do not use them.

Do not use something conceptually equivalent to:

```text
messages.tool_runner(...)
```

The Agent Harness Lab must retain ownership of:

```text
tool dispatch
tool execution
tool-result construction
agent loop
termination
telemetry
```

Otherwise Anthropic's SDK would silently become part of the harness and defeat the educational purpose.

Use only the basic Messages API call.

---

# 25. Do not use Anthropic server tools

Do not introduce any Anthropic-managed tool such as:

```text
web search
code execution
computer use
text editor
memory
bash/server tool
```

Only MiniHarness local tools are allowed:

```text
list_files
read_file
```

This distinction matters:

```text
Anthropic tool-use protocol
≠
Anthropic-managed tools
```

We are implementing the first, not adopting the second.

---

# 26. Existing OpenAI adapter

Do not refactor the OpenAI adapter unless a tiny change is required to maintain the common interface.

The already working OpenAI Stage 01 run is our regression baseline.

After this change:

```text
openai_luna
```

must continue behaving as before.

---

# 27. Stage 00 compatibility

Anthropic naked model calls from Stage 00B must continue to work.

The Anthropic adapter should support both:

```text
tools = []
```

and:

```text
tools = [list_files, read_file]
```

Do not make tool calling mandatory.

Stage 00B must remain reproducible.

---

# 28. Model profiles

Preserve the existing Anthropic profiles.

At minimum:

```text
anthropic_haiku
anthropic_opus
```

Do not add new Anthropic models as part of this change.

For the first tool-calling smoke test, prefer:

```text
anthropic_haiku
```

because the objective is adapter validation rather than frontier-model comparison.

---

# 29. First Anthropic Stage 01 run

After implementation, execute:

```powershell
$env:MODEL_PROFILE="anthropic_haiku"
python -m miniharness.run scenarios/01_read_only_agent/task.md
```

Do not change the task.

Inspect:

```text
events.jsonl
response.md
summary.json
```

Questions:

1. Did Claude receive both tool definitions?
2. Did it emit a structured `tool_use` block?
3. Did the adapter convert it correctly into `ToolCall`?
4. Did MiniHarness execute the tool through the existing ToolRegistry?
5. Did the corresponding `tool_result` preserve the correct `tool_use_id`?
6. Did Claude continue reasoning after receiving the result?
7. Did multiple tool calls in one response work correctly if they occurred?
8. Did tool errors reach Claude using `is_error=true`?
9. Did Claude eventually terminate with a normal text response?
10. Did it avoid falsely claiming mutation or verification?
11. Did the OpenAI Stage 01 path remain unaffected?

---

# 30. Recommended adapter flow

The implementation should conceptually follow:

```text
MiniHarness messages
MiniHarness ToolDefinitions
        │
        ▼
AnthropicModelClient
        │
        ├── convert messages
        ├── convert tools → input_schema
        │
        ▼
client.messages.create(...)
        │
        ▼
Anthropic response.content
        │
        ├── text
        ├── tool_use
        ├── possible provider-native blocks
        │
        ▼
preserve raw assistant continuation data
        │
        ▼
normalize
        │
        ▼
ModelTurn
        ├── text
        ├── tool_calls
        ├── input_tokens
        └── output_tokens
```

Then:

```text
AgentLoop
   ↓
ToolRegistry
   ↓
ToolResult
   ↓
AnthropicModelClient
   ↓
user content:
[
  tool_result(...)
]
   ↓
Messages API
```

---

# 31. Tool-error recovery test

Because Stage 01 already demonstrated useful error recovery with OpenAI Luna, deliberately validate that Anthropic can receive the same kind of failure observation.

Do not change the tool contract to force an error.

If the natural run produces one, inspect it.

Otherwise add a small unit/integration test at the adapter level using a synthetic failed:

```python
ToolResult(
    ok=False,
    ...
)
```

and verify that it becomes:

```json
{
  "type": "tool_result",
  "tool_use_id": "...",
  "is_error": true,
  "content": "..."
}
```

Do not create new runtime recovery logic.

---

# 32. Tests

Add focused tests for the adapter boundary.

At minimum verify:

### Tool definition conversion

```text
ToolDefinition.parameters
→ Anthropic input_schema
```

### Tool-use parsing

```text
tool_use.id
tool_use.name
tool_use.input
→ ToolCall
```

### Multiple tool calls

One Anthropic response containing multiple `tool_use` blocks becomes multiple MiniHarness `ToolCall`s.

### Text + tool use

A response containing both visible text and tool use preserves both correctly.

### Tool result success

Successful `ToolResult` maps to correct `tool_result`.

### Tool result failure

Failed `ToolResult` maps to:

```text
is_error=true
```

### Tool-use ID preservation

The original:

```text
tool_use.id
```

is used as:

```text
tool_result.tool_use_id
```

### Assistant-turn preservation

Provider-native assistant content required for the next Anthropic request survives normalization/replay.

### No-tools compatibility

Stage 00-style Anthropic call still works when no tools are supplied.

---

# 33. Validation checklist

Before considering the implementation complete:

```text
[ ] Stage 00 Anthropic naked call still works
[ ] Stage 01 OpenAI run still works
[ ] Stage 01 Anthropic run works
[ ] MiniHarness AgentLoop was not duplicated
[ ] Anthropic tools use input_schema
[ ] tool_use blocks become ToolCall
[ ] multiple tool_use blocks are preserved
[ ] text blocks become visible ModelTurn.text
[ ] tool_result references original tool_use_id
[ ] failed ToolResult becomes is_error=true
[ ] assistant tool-use turn is preserved correctly
[ ] thinking/redacted_thinking blocks are preserved if returned
[ ] thinking is not exposed as final text
[ ] no automatic Anthropic tool runner is used
[ ] no Anthropic server tools are used
[ ] no new MiniHarness capability was introduced
[ ] list_files/read_file definitions remain unchanged
[ ] task prompt remains unchanged
```

---

# 34. What NOT to implement

Do not implement:

```text
raw LLM tracing
llm_trace.jsonl
wire proxy
LiteLLM
streaming
retries
cost calculation
prompt caching configuration
context compaction
search
grep
editing
shell
pytest
git
AGENTS.md automatic injection
skills
MCP
LSP
permissions
sandbox
subagents
memory
planning
automatic graders
parallel tool execution
Anthropic automatic tool runner
Anthropic managed tools
```

Raw provider tracing is the next instrumentation change planned for Stage 01, but it must be implemented only **after this Anthropic adapter is working**.

---

# 35. Documentation

Do not add a large new README stage section.

Store this specification as:

```text
lab/specs/01a_anthropic_tool_calling_adapter.md
```

A very small README note is acceptable if provider support is currently documented there.

Do not duplicate this entire spec into README.

---

# 36. Definition of Done

This change is complete when the following statement is true:

```text
The same provider-neutral MiniHarness Stage 01 AgentLoop can execute
the same list_files/read_file tool workflow through either OpenAI's
Responses API or Anthropic's Messages API, with provider protocol
differences isolated inside their respective model adapters.
```

Concretely:

```text
[✓] OpenAI Stage 01 still works
[✓] Anthropic Stage 01 now works
[✓] same AgentLoop
[✓] same ToolRegistry
[✓] same ToolDefinitions
[✓] same task
[✓] same run telemetry
[✓] provider-specific protocol isolated in adapter
```

No additional agent capability should exist after this change.

At completion, report:

1. files created/modified;
2. how MiniHarness tool definitions map to Anthropic `input_schema`;
3. how `tool_use` maps to `ToolCall`;
4. how `ToolResult` maps to `tool_result`;
5. how multiple tool calls are handled;
6. how assistant content blocks are preserved across tool-use turns;
7. how thinking blocks are handled if present;
8. tests added;
9. result of one `anthropic_haiku` Stage 01 smoke run;
10. confirmation that the OpenAI path and Stage 00 behavior remain intact.