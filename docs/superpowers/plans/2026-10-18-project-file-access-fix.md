# Project file access and conversation changes

User reports real project chats cannot read/write files and requests a compact project badge and per-chat Changes header action.

Evidence: persisted chats tried web_fetch(file://...), hallucinated Docker and claimed edits without file tools. Legacy slash commands still captured !. File implementations already support rg search, line ranges, exact edits and patches; selection depended on English intent and retrieval.

Implementation: give server-bound project turns a deterministic native filesystem tool set, preserve privilege/plan/delegated/approval restrictions, and state runtime host truth. Route ! to the existing direct terminal stream. Reuse bounded read/search/patch tools across text languages, not per-language whole-tree indexing. Add owner/session-scoped paginated change history and snapshot diff, including after project movement/removal. Remove redundant root text from badge; reuse existing header button design for Changes.

Validation: regression tests for changes isolation/pagination/deleted projects, real confined read/write/patch with change snapshots, ! browser regression, project natural-language file write via the local model, header Changes diff, scoped relevant suite. Publish fork and fast-forward installed checkout after checks.
