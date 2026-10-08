# Provider requests and troubleshooting

Existing saved provider/model choices are preserved. `blackreach models` lists
known model IDs, not the models your account has permission to call. For a custom
ID, choose the provider first and use `/model <id>` or `run --provider ... --model ...`.

OpenAI GPT-5/6 and o-series reasoning models use Responses in auto mode. Legacy
OpenAI models and compatible providers keep Chat Completions. `api_mode: chat`
or `api_mode: responses` can explicitly select an OpenAI endpoint; a compatible
endpoint may not support Responses. The adapter never substitutes another model.
Responses requests set `store: false`; reasoning models do not receive temperature.

Provider entries under `providers` in the existing config accept these settings:

```yaml
providers:
  openai:
    default_model: gpt-6-luna
    max_tokens: 4096
    timeout_seconds: 60
    max_retries: 3
    retry_delay: 1
    reasoning_effort: low
    api_mode: auto
```

This excerpt is not a replacement for your configuration. Keep credentials in
an environment variable or the supported keyring workflow; do not paste them
into diagnostics or public reports. Model choices shown here require account access.

`max_retries` retains its historical name but means total attempts, including
the first. Only transient connection, timeout, rate-limit, and service failures
are retried. SDK retries are disabled where available so loops do not multiply.
Authentication, permissions, missing models, billing quota and invalid settings
stop immediately. After retries are exhausted, the agent receives a terminal
provider error rather than calling the same failing provider every step.

Responses reasoning and visible output share `max_tokens`. If that budget is
exhausted, no partial JSON action is accepted. Increase the configured budget or
reduce reasoning effort deliberately; the agent does not raise spend itself.
Timeouts bound transport operations, not a strict whole-run wall-clock deadline.
A cancelled or retried request may still have incurred provider usage.

`blackreach doctor --offline --json` checks local prerequisites without model
requests. It confirms the browser executable exists, not that Chromium launched.
The controlled recovery example tests browser launch and state recovery locally.

Provider adapters are covered with mocked SDK responses. Successful tests do not
prove that an account can access every listed model or that a live model can
complete arbitrary tasks. Current API guidance: https://developers.openai.com/api/docs/guides/reasoning
