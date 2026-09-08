# Stage 01B — LLM Provider I/O Trace

Status: **SPEC — passive observability**  
Project: **Agent Harness Lab**

---

## 1. Purpose

We are still in:

```text
Stage 01 — Read-Only Agent
```

The current agent capabilities remain exactly:

```text
AgentLoop
+
list_files
+
read_file
```

This change must **not add a new agent capability**.

The objective is purely didactic observability:

> Record the complete provider request payload immediately before each LLM SDK call and the complete provider response immediately after it returns.

We want to inspect the full transformation:

```text
MiniHarness internal state
        ↓
provider adapter
        ↓
PROVIDER REQUEST PAYLOAD
        ↓
OpenAI / Anthropic API
        ↓
PROVIDER RAW RESPONSE
        ↓
provider adapter normalization
        ↓
ModelTurn
        ↓
AgentLoop
```

This trace should make visible:

- how conversation history grows across turns;
- how tool definitions are retransmitted;
- how tool calls are represented by each provider;
- how tool results are replayed;
- how OpenAI Responses and Anthropic Messages differ;
- what information is discarded when converting the provider response into `ModelTurn`;
- how `raw_output` differs from the complete raw provider response.

---

# 2. Current architecture

The current implementation has no common `ModelClient` class.

Provider implementations live in:

```text
src/miniharness/model.py
```

Current clients:

```text
OpenAIModelClient
AnthropicModelClient
```

The provider-neutral state lives in:

```text
src/miniharness/types.py
```

including:

```text
Message
ToolDefinition
ToolCall
ToolResult
ModelTurn
```

`Message` and `ModelTurn` already contain:

```python
raw_output
```

This field is used to preserve provider-native assistant output required for later conversation replay.

For Anthropic, for example:

```text
response.content
        ↓
_dump_anthropic_block()
        ↓
ModelTurn.raw_output
        ↓
Message.raw_output
        ↓
_messages_to_anthropic()
```

This behavior must remain intact.

---

# 3. Critical distinction: `raw_output` is NOT the new trace

Do not treat:

```text
ModelTurn.raw_output
```

as the complete provider response.

It is only the provider-private content needed for continuation.

For Anthropic it currently preserves:

```text
response.content blocks
```

but not necessarily the complete Messages response including:

```text
id
model
role
stop_reason
stop_sequence
usage
content
other response metadata
```

For OpenAI it currently preserves:

```text
response.output items
```

but not the complete Responses object.

Therefore:

```text
raw_output
=
provider-private conversation continuation state
```

while:

```text
llm_trace
=
complete provider request / response observability
```

They serve different purposes and must remain separate.

---

# 4. Trace modes

Implement exactly three modes:

```text
off
file
stdout
```

Default:

```text
off
```

Meaning raw LLM request/response data is neither persisted nor printed during normal runs.

---

# 5. Configuration

Extend `config.toml`:

```toml
[debug]
llm_trace = "off"
```

Accepted values:

```text
off
file
stdout
```

Add a minimal configuration type, for example:

```python
@dataclass(frozen=True)
class DebugConfig:
    llm_trace: str
```

and include it in:

```python
LabConfig
```

Validate the configured value.

If it is not one of:

```text
off
file
stdout
```

fail clearly during configuration loading.

Do not add other debug configuration yet.

---

# 6. CLI overrides

Extend `run.py` with:

```text
--llm-trace
```

meaning:

```text
file
```

and:

```text
--llm-trace-stdout
```

meaning:

```text
stdout
```

Examples:

```powershell
python -m miniharness.run `
  scenarios/01_read_only_agent/task.md `
  --llm-trace
```

and:

```powershell
python -m miniharness.run `
  scenarios/01_read_only_agent/task.md `
  --llm-trace-stdout
```

Precedence:

```text
CLI override
    >
config.toml
```

If both CLI flags are provided:

```text
--llm-trace
--llm-trace-stdout
```

terminate with a clear CLI error.

Do not implement:

```text
--no-persist
```

The normal run artifacts should always continue to be persisted.

---

# 7. New module

Create:

```text
src/miniharness/trace.py
```

Implement a deliberately small:

```python
class LLMTracer:
    ...
```

Suggested interface:

```python
class LLMTracer:
    def request(
        self,
        *,
        turn: int,
        provider: str,
        model: str,
        endpoint: str,
        payload: object,
    ) -> None:
        ...

    def response(
        self,
        *,
        turn: int,
        provider: str,
        model: str,
        endpoint: str,
        payload: object,
    ) -> None:
        ...
```

The tracer may internally know:

```text
mode
optional output path
```

Do not create:

```text
middleware framework
hooks system
OpenTelemetry
spans
plugins
interceptor chains
database logging
web interface
```

---

# 8. Tracer lifecycle

Create one tracer per run.

The run directory is already created before the model client is instantiated.

Use that fact.

Conceptually in `run.py`:

```python
run_dir = new_run_dir(...)

tracer = LLMTracer(
    mode=effective_trace_mode,
    file_path=run_dir / "llm_trace.jsonl",
)
```

Then pass it into:

```python
create_model_client(...)
```

Suggested change:

```python
create_model_client(
    config.model,
    tracer=tracer,
)
```

Each provider client may retain the tracer as an instance attribute.

Do not use a global tracer.

---

# 9. Minimal changes to model clients

Update constructors conceptually to:

```python
class OpenAIModelClient:
    def __init__(
        self,
        model: str,
        max_output_tokens: int,
        tracer: LLMTracer | None = None,
    ):
        ...
```

and:

```python
class AnthropicModelClient:
    def __init__(
        self,
        model: str,
        max_output_tokens: int,
        tracer: LLMTracer | None = None,
    ):
        ...
```

Tracing disabled should behave as a no-op.

Do not create a new model-client hierarchy solely for tracing.

---

# 10. Turn correlation

The trace turn number must match:

```text
events.jsonl
```

exactly.

For Stage 01:

```text
events.jsonl turn=3
```

must correspond to:

```text
llm_trace request turn=3
llm_trace response turn=3
```

The cleanest implementation is to make `generate_turn()` accept an optional turn number.

For example:

```python
def generate_turn(
    self,
    messages: list[Message],
    tools: list[ToolDefinition],
    *,
    turn: int | None = None,
) -> ModelTurn:
```

Then change the existing AgentLoop call only minimally:

```python
model.generate_turn(
    messages,
    tools,
    turn=turn,
)
```

This is an observability-only parameter.

It must not affect model behavior or request construction.

For Stage 00 `generate()`, use:

```text
turn = 1
```

internally for tracing.

---

# 11. Request tracing rule

The tracer must capture the **actual dictionary passed to the provider SDK**.

Do not reconstruct a simplified version afterward.

For OpenAI Stage 01, the current code builds:

```python
kwargs = {
    "model": self.model,
    "input": _messages_to_openai_input(messages),
    "max_output_tokens": self.max_output_tokens,
}

if tools:
    kwargs["tools"] = _openai_tools(tools)
```

The trace must happen after `kwargs` is fully built and immediately before:

```python
self.client.responses.create(**kwargs)
```

Conceptually:

```python
self.tracer.request(
    turn=turn,
    provider="openai",
    model=self.model,
    endpoint="responses",
    payload=kwargs,
)

response = self.client.responses.create(**kwargs)
```

---

# 12. Anthropic request tracing

The current Anthropic Stage 01 flow is:

```python
kwargs = _anthropic_request_kwargs(...)
response = self.client.messages.create(**kwargs)
```

Trace the actual output of:

```python
_anthropic_request_kwargs(...)
```

immediately before:

```python
self.client.messages.create(**kwargs)
```

Conceptually:

```python
self.tracer.request(
    turn=turn,
    provider="anthropic",
    model=self.model,
    endpoint="messages",
    payload=kwargs,
)

response = self.client.messages.create(**kwargs)
```

This should expose the real Anthropic continuation structure, including sequences such as:

```text
user task

assistant:
  text
  tool_use

user:
  tool_result
```

Do not reconstruct that structure separately for tracing.

Trace the actual `kwargs`.

---

# 13. Stage 00 tracing

Tracing should also work for existing Stage 00 calls.

For:

```python
OpenAIModelClient.generate()
```

construct the request payload explicitly before calling the SDK.

Instead of tracing a separately reconstructed dictionary, use the same object for both:

```python
payload = {
    "model": self.model,
    "input": prompt,
    "max_output_tokens": self.max_output_tokens,
}

trace(payload)

response = self.client.responses.create(**payload)
```

Do the equivalent for:

```python
AnthropicModelClient.generate()
```

This allows the tracer to be used for both:

```text
Stage 00
Stage 01
```

without changing either stage's semantics.

---

# 14. Response tracing rule

The raw provider response must be captured:

```text
after SDK call returns
but before normalization
```

For OpenAI:

```text
responses.create()
        ↓
RAW RESPONSE
        ↓
TRACE HERE
        ↓
extract usage
extract function calls
build ModelTurn
```

For Anthropic:

```text
messages.create()
        ↓
RAW RESPONSE
        ↓
TRACE HERE
        ↓
_anthropic_turn_from_content()
        ↓
ModelTurn
```

This ordering is mandatory.

---

# 15. Serialize the COMPLETE OpenAI response

Do not trace only:

```text
response.output
```

Trace the complete response object returned by:

```python
client.responses.create(...)
```

Prefer the SDK object's official serialization mechanism.

For example, if supported:

```python
response.model_dump(
    mode="json",
    exclude_none=True,
)
```

The trace should preserve fields such as those actually returned by the SDK, potentially including:

```text
id
model
status
output
usage
error
incomplete_details
parallel_tool_calls
tool_choice
other response-level metadata
```

Do not manually curate only the fields currently used by MiniHarness.

The purpose is precisely to observe information the harness currently ignores.

---

# 16. Serialize the COMPLETE Anthropic response

Do not trace only:

```text
response.content
```

Trace the complete object returned by:

```python
client.messages.create(...)
```

Prefer official SDK serialization.

Preserve the provider's complete response representation, potentially including:

```text
id
type
role
model
content
stop_reason
stop_sequence
usage
container
other returned metadata
```

Again, do not reduce this to what `_anthropic_turn_from_content()` needs.

---

# 17. Existing serialization helpers

The repository already contains:

```python
_dump_item()
_dump_anthropic_block()
```

These exist to support current provider normalization / replay behavior.

Do not automatically reuse them for complete response tracing if they only serialize partial objects.

It is acceptable to introduce one small generic helper in `trace.py`, for example:

```python
def to_jsonable(value: object) -> object:
    ...
```

Prefer:

```text
model_dump(mode="json")
```

when available.

Support recursively serializable Python:

```text
dict
list
tuple
str
int
float
bool
None
```

Avoid introspecting SDK client internals.

---

# 18. File mode

When trace mode is:

```text
file
```

create:

```text
runs/<run-id>/llm_trace.jsonl
```

Each entry must be one complete JSON object.

Required top-level structure:

```json
{
  "ts": "...",
  "type": "request",
  "turn": 1,
  "provider": "openai",
  "model": "gpt-5.6-luna",
  "endpoint": "responses",
  "payload": {}
}
```

and:

```json
{
  "ts": "...",
  "type": "response",
  "turn": 1,
  "provider": "openai",
  "model": "gpt-5.6-luna",
  "endpoint": "responses",
  "payload": {}
}
```

Anthropic uses:

```text
endpoint = "messages"
```

Do not use actual HTTP URLs.

The semantic endpoint name is sufficient.

---

# 19. Chronological append-only trace

Use one chronological JSONL stream:

```text
request turn 1
response turn 1
request turn 2
response turn 2
...
```

Do not create:

```text
requests.jsonl
responses.jsonl
one file per turn
one file per provider
```

The chronological stream is easier to inspect as an agent-loop execution transcript.

Flush each entry after writing so partial runs remain inspectable.

---

# 20. Stdout mode

When trace mode is:

```text
stdout
```

print each request and response in pretty JSON.

Example:

```text
=== LLM REQUEST — TURN 2 — ANTHROPIC / MESSAGES ===

{
  ...
}

=== LLM RESPONSE — TURN 2 — ANTHROPIC / MESSAGES ===

{
  ...
}
```

Do not persist:

```text
llm_trace.jsonl
```

in this mode.

Continue persisting normal run artifacts.

---

# 21. Off mode

When:

```text
llm_trace = "off"
```

there must be:

```text
no raw trace file
no raw trace stdout
```

The agent should behave exactly as it does now.

Tracing must be disabled by default.

---

# 22. Security boundary

Never trace:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
Authorization headers
x-api-key
.env
SDK client configuration
HTTP headers
```

The trace begins at:

```text
provider SDK request body
```

not at the complete HTTP request.

This feature is therefore a:

```text
provider application-level I/O trace
```

not a network packet or HTTP wire trace.

---

# 23. Sensitive content warning

Raw provider payloads can contain:

```text
prompts
tool schemas
source code
tool outputs
repository contents
business data
model output
```

Therefore tracing must remain explicit opt-in.

Document:

> Raw LLM tracing can persist the complete context sent to a provider, including source code and tool outputs. Do not enable file tracing on sensitive workloads unless storing that data is acceptable.

Do not implement redaction yet.

Redaction would make the didactic trace incomplete.

---

# 24. Relationship to `events.jsonl`

Do not change the purpose of:

```text
events.jsonl
```

Current semantic events such as:

```json
{
  "event": "model_response",
  "turn": 3,
  "input_tokens": 1412,
  "output_tokens": 78,
  "tool_call_count": 1
}
```

should remain.

The distinction is:

```text
events.jsonl
=
provider-neutral semantic harness telemetry
```

while:

```text
llm_trace.jsonl
=
provider-native request/response telemetry
```

Do not place complete raw payloads into `events.jsonl`.

---

# 25. Relationship to `raw_output`

Maintain this conceptual separation:

```text
ModelTurn.raw_output
        ↓
needed for provider-native conversation continuation
```

versus:

```text
llm_trace.jsonl
        ↓
needed for human observability and learning
```

Do not make AgentLoop depend on `llm_trace`.

Do not make replay depend on `llm_trace`.

Deleting the trace file must have zero effect on execution semantics.

---

# 26. Anthropic-specific didactic requirement

The trace must make it possible to observe the exact tool-use cycle.

For example:

```text
REQUEST TURN 1

messages:
  user task

tools:
  list_files
  read_file
```

Then:

```text
RESPONSE TURN 1

content:
  text
  tool_use(id=toolu_...)
```

Then:

```text
REQUEST TURN 2

messages:
  user task

  assistant:
    original content blocks
    including tool_use

  user:
    tool_result(
      tool_use_id=toolu_...
    )
```

The trace must preserve:

```text
tool_use.id
tool_result.tool_use_id
is_error
full assistant content blocks
```

If:

```text
thinking
redacted_thinking
```

blocks are returned, they should naturally appear in the raw response and subsequent raw request because the adapter already preserves them through `raw_output`.

Do not specially expose them elsewhere.

---

# 27. OpenAI-specific didactic requirement

The trace must make the equivalent Responses API flow observable.

We should be able to inspect:

```text
function_call
call_id
function_call_output
```

and see how:

```text
_messages_to_openai_input()
```

reconstructs the next `input`.

The trace should also make visible that:

```text
tools
```

are present again in later requests when the current adapter sends them again.

Do not suppress repeated tools for tracing purposes.

---

# 28. Multiple tool calls

The current MiniHarness can represent:

```text
multiple ToolCall objects in one ModelTurn
```

and Anthropic can replay grouped tool results.

The tracer must preserve this provider-native structure exactly.

Do not flatten:

```text
4 tool_use blocks
```

into one synthetic object.

Do not flatten:

```text
4 tool_result blocks
```

into one text string.

---

# 29. Tool errors

When ToolRegistry returns:

```python
ToolResult(
    ok=False,
    output="..."
)
```

Anthropic converts this to:

```text
is_error=true
```

The subsequent raw Anthropic request must show that exact structure.

For OpenAI, the raw next request should show the corresponding:

```text
function_call_output
```

with the returned error text.

This is especially important because Stage 01 demonstrated that tool errors can become useful observations for model recovery.

---

# 30. Summary artifact

Add:

```text
llm_trace_mode
```

to Stage 00 and Stage 01 `summary.json`.

Example:

```json
{
  "llm_trace_mode": "file"
}
```

Do not add:

```text
trace byte size
request count
response count
context size
cost
cache hit estimation
```

yet.

---

# 31. Files expected to change

Expected minimal change set:

```text
src/miniharness/trace.py        NEW

src/miniharness/config.py       MODIFY
src/miniharness/model.py        MODIFY
src/miniharness/run.py          MODIFY
src/miniharness/agent.py        MINIMAL MODIFY for turn correlation

config.toml                     MODIFY

tests/...                       ADD focused tracer tests
```

Avoid modifying:

```text
src/miniharness/tools.py
src/miniharness/types.py
```

unless a genuinely necessary tracing issue appears.

The current `raw_output` design already provides provider-private continuation state and should not need redesign for this feature.

---

# 32. Do NOT add a network proxy

Do not implement:

```text
LiteLLM
mitmproxy
HTTP relay
custom provider proxy
requests interception
network packet capture
```

This stage is intentionally observing the SDK application boundary.

A future wire-level measurement proxy may be justified by cost-accounting needs, but that is a separate component.

---

# 33. Do NOT add observability infrastructure

Do not introduce:

```text
OpenTelemetry
LangSmith
Langfuse
Phoenix
Datadog
Honeycomb
trace database
dashboard
distributed tracing
```

The desired implementation is intentionally primitive:

```text
one tracer
one JSONL file
one stdout mode
```

---

# 34. Do NOT alter agent capabilities

Do not add:

```text
search
grep
editing
write_file
apply_patch
shell
test runner
git
AGENTS.md injection
context compaction
skills
MCP
LSP
subagents
permissions
sandbox
memory
planning
```

Stage 01 remains a read-only agent.

---

# 35. Do NOT alter tool contracts

Do not change:

```text
list_files
read_file
```

including:

```text
names
descriptions
JSON schemas
path behavior
error behavior
```

We want the traced runs to remain comparable with the existing Stage 01 runs.

---

# 36. Do NOT alter provider behavior

Do not add or change:

```text
system prompts
temperature
tool_choice
reasoning settings
thinking configuration
max turns
model profiles
max output tokens
retry behavior
```

Tracing must remain passive.

---

# 37. Tests — tracer core

Add focused tests verifying:

### Off

```text
no file written
no stdout trace
```

### File

```text
request and response appended to JSONL
valid JSON per line
chronological order preserved
```

### Stdout

```text
request and response printed
no llm_trace.jsonl created
```

### Invalid config

Invalid trace mode fails clearly.

### CLI conflict

Both trace CLI flags together fail clearly.

---

# 38. Tests — request fidelity

Mock the provider SDK.

For OpenAI:

1. build a Stage 01 request;
2. capture the kwargs passed to:

```python
responses.create(...)
```

3. compare them to the traced request payload.

They must represent the same application payload.

Do the equivalent for Anthropic:

```python
messages.create(...)
```

Do not test against a manually simplified expected payload only.

The purpose is to verify that the tracer observes the actual provider call.

---

# 39. Tests — response completeness

Mock a provider response containing metadata beyond what MiniHarness currently uses.

For Anthropic, include values such as:

```text
id
model
role
stop_reason
content
usage
```

Verify that these survive in:

```text
llm_trace
```

even though `ModelTurn` normalizes only part of them.

Do the equivalent for OpenAI with fields outside:

```text
response.output
response.output_text
usage
```

where practical.

---

# 40. Tests — `raw_output` independence

Explicitly verify:

```text
ModelTurn.raw_output
```

continues to work exactly as before.

Tracing enabled or disabled must not change:

```text
raw_output
_messages_to_openai_input()
_messages_to_anthropic()
```

This guards against accidentally turning the tracer into provider continuation state.

---

# 41. Tests — turn correlation

For a Stage 01 mocked run with multiple turns, verify:

```text
events model_request turn 1
↔
trace request/response turn 1

events model_request turn 2
↔
trace request/response turn 2
```

No independent tracer turn counter should drift from the AgentLoop.

---

# 42. Validation with real OpenAI run

After implementation:

```powershell
$env:MODEL_PROFILE="openai_luna"

python -m miniharness.run `
  scenarios/01_read_only_agent/task.md `
  --llm-trace
```

Inspect:

```text
runs/<run-id>/llm_trace.jsonl
```

Confirm visually that:

```text
Turn 1
→ task + tools

later turns
→ accumulated provider-native conversation + tools
```

and that:

```text
function_call
function_call_output
```

are visible.

---

# 43. Validation with real Anthropic run

Then:

```powershell
$env:MODEL_PROFILE="anthropic_haiku"

python -m miniharness.run `
  scenarios/01_read_only_agent/task.md `
  --llm-trace
```

Confirm visually that:

```text
tool_use
tool_result
tool_use_id
is_error
```

are visible and that assistant content is replayed correctly.

The existing Anthropic Stage 01 run required seven model calls and six tool calls, so a new trace should provide a rich multi-turn example.

Do not expect the new run to reproduce the exact same trajectory.

Model stochasticity has already been observed in the lab.

---

# 44. Expected educational output

After this feature exists, we should be able to place side-by-side:

```text
TURN 3 — MiniHarness events
```

```text
TURN 3 — OpenAI provider payload
```

```text
TURN 3 — OpenAI raw response
```

and separately:

```text
TURN 3 — Anthropic provider payload
```

```text
TURN 3 — Anthropic raw response
```

This should make the Adapter responsibility directly visible:

```text
same harness semantics
        ↓
different provider protocols
```

---

# 45. Definition of Done

This change is complete when:

```text
[✓] tracing is disabled by default

[✓] file mode writes complete provider request/response JSONL

[✓] stdout mode prints complete provider request/response
    without persisting raw trace

[✓] OpenAI generate() is traceable

[✓] OpenAI generate_turn() is traceable

[✓] Anthropic generate() is traceable

[✓] Anthropic generate_turn() is traceable

[✓] requests are traced immediately before SDK calls

[✓] responses are traced immediately after SDK calls
    and before normalization

[✓] full provider response objects are serialized

[✓] raw_output remains unchanged in purpose and behavior

[✓] trace turns correlate exactly with AgentLoop turns

[✓] no credentials or HTTP headers are logged

[✓] events.jsonl remains provider-neutral semantic telemetry

[✓] tracing does not alter tool schemas, prompts,
    provider parameters, or AgentLoop behavior

[✓] Stage 00 remains reproducible

[✓] Stage 01 remains reproducible

[✓] no new agent capability is introduced
```

At completion, report:

1. files created and modified;
2. effective trace-mode precedence;
3. where request tracing occurs in each provider method;
4. where response tracing occurs;
5. how full SDK responses are serialized;
6. how turn correlation is implemented;
7. tests added;
8. results of one OpenAI trace run;
9. results of one Anthropic trace run;
10. confirmation that `raw_output`, AgentLoop semantics, tools and task prompts were not changed.