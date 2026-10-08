# Agent run outcomes

`Agent.run()` and `Agent.resume()` return the existing result dictionary with
explicit lifecycle fields. The CLI and TUI should render `status`, `stop_reason`,
and `error`, and show a resume hint only when `resumable` is true.

| Status | Meaning | Usual stop reason |
| --- | --- | --- |
| `success` | A decision declared completion without an error | `goal_complete` |
| `max_steps` | The saved total decision budget was consumed | `max_steps` |
| `paused` | A requested pause saved progress successfully | `paused` |
| `interrupted` | An interruption saved progress successfully | `interrupted` |
| `error` | A terminal runtime or finalization failure | See below |

Error reasons are `permanent_error`, `initialization_failed`,
`browser_start_failed`, `navigation_failed`, `state_load_failed`,
`state_save_failed`, `cleanup_failed`, and `log_write_failed`. `error` contains a
redacted diagnostic string or `None`. A terminal error always overrides a
contradictory completion result. `success` is true only for `status=success`.

`steps_taken` counts cumulative decisions attempted, including decisions that
finish, fail, or are interrupted. Pausing before a decision does not consume it.
`actions_taken` counts cumulative action dispatch attempts, including failed or
interrupted actions. Completion, observation, and internal recovery navigation
do not count as actions. Both counters survive resume; action history remains
bounded independently. Legacy snapshots that lack the monotonic action counter
use their retained history length and set `actions_count_estimated=true`.
Legacy decision counts retain their saved `current_step`; older checkpoint
semantics cannot be reconstructed exactly from bounded history.

Resume restores saved progress and clears the previous pause request. Its saved
budget remains in effect unless the caller supplies `resume(..., max_steps=N)`.
An exhausted saved budget does not start a browser or call a provider. To make
additional progress, the new total budget must exceed `steps_taken`.

Successful completion removes its checkpoint. Max-step, pause, interruption,
and terminal decision-error exits save checkpoints; save failure produces an error and cannot claim that a
new checkpoint is resumable. Resume navigation failure retains the loaded
checkpoint and its previous progress. Browser login state and cookies are not
part of this checkpoint contract.

A terminal exit that cannot save newer progress invalidates its older checkpoint
so a later resume cannot replay already attempted actions. Navigation failures
before resumed decisions explicitly preserve the unchanged loaded checkpoint.

Session-end logs contain status, stop reason, redacted error, decisions, and
actions. They do not retain model reasoning, raw prompts/responses, entered text,
or credential fields. Log sink failure is reported as `log_write_failed`.
