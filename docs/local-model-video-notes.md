# Local-model evaluation notes

Source: [video xcpCz6eTW48](https://www.youtube.com/watch?v=xcpCz6eTW48),
reviewed from its automatic English transcript on 2026-10-18. Names and flags
in automatic captions can be wrong; verify them against official model/runtime
documentation before executing anything.

The author compares weight quantization, KV-cache precision, context stability,
offloading and speculative decoding for a larger Qwen model on discrete GPUs.
He stresses testing tool calls, repetition and multi-turn tasks rather than
judging a model from a single attractive generated page. Speed and accuracy
profiles can have different trade-offs, and a nominally larger context is not
necessarily reliable. His results and numerical recommendations are specific
to his configurations, not verified measurements of this fork or this Mac.

Applied here: test actual file/tool operations, bounded context references and
recovery from cancellation; keep project chats focused and change review visible.
Explicit `!` commands bypass model reasoning entirely. Keep the working Qwen3.5
4B Q5/f16 profile and its image projector; do not substitute a severely compressed
large model merely to advertise more parameters or context. The Mac's 16 GB is
unified system memory, not a separate 16 GB graphics allocation plus spare RAM.
Gemma setup was deferred at the user's request.

This video does not establish that the installed model matches a cloud model's
capability. Fork reliability and model capability are distinct; integration
checks prove the former only for the tested cases.
