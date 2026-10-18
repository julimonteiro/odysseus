# Local-model evaluation notes

Source: [video xcpCz6eTW48](https://www.youtube.com/watch?v=xcpCz6eTW48),
reviewed from its automatic English transcript on 2026-10-18. Names and flags
in automatic captions can be wrong; verify them against official model/runtime
documentation before executing anything.

The video is about Qwen3.8 27B. The author compares weight quantization, KV-cache precision, context stability,
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

## Optional Qwen3.8 installation evaluated on 2026-10-18

At the user's later request, installed the [GSQ-RCO IQ2_XS build](https://huggingface.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF), 8.42 GB plus its 0.93 GB BF16 vision projector. Both upstream SHA-256 values were checked. The local profile uses 8,192 tokens, one slot, f16 KV, no MTP, no RAM prompt cache and non-thinking generation. A llama.cpp router with `--models-max 1` loads only the requested model; Qwen3.5 remains the default and utility model. Gemma is not in the active presets.

Short checks passed numeric arithmetic, a function call, a simulated file-tool result and image total/code transcription. Generation measured approximately 6.7–7.1 tokens/s. The initial free-form arithmetic answer changed an operand in prose, and OCR misspelled a heading. Total system swap reached about 2.7 GiB with memory-pressure warning level 2. This heavily compressed build is optional and experimental; these checks do not establish general agent reliability or equivalence with higher-precision weights.

The router's catalog advertised the 262,144-token training maximum despite an 8,192-token preset. Odysseus now queries `/slots` with the selected model and `autoload=false`, and reads explicit child context/parallel arguments when unloaded. This prevents a metadata lookup from loading a model and prevents using the training maximum as the serving limit.
