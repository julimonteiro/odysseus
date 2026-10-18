# Projects with local workspaces and change review

## User request and scope

Add a Projects section next to the existing Chats sidebar area. A user can create project folders, bind each to a selected directory on the Odysseus host, create related chats inside it, refer to files under that directory, and review edits with original text on the left and current text on the right. Publish changes to julimonteiro/odysseus, maintaining the ability to merge changes from odysseus-dev/odysseus. Preserve native/local-model functionality and LAN access. Gemma installation is explicitly deferred.

This is a fork feature on the currently installed curated main baseline, not a wholesale migration to upstream dev. The fork remains independently installable under the upstream license, with origin pointing at the user's fork and upstream at the original project. Keep extension code in dedicated modules and minimal upstream seams. Upstream updates are explicit merges with tests, never resets or promises of conflict-free synchronization.

## Proposed behavior

Projects are owned metadata records with name, directory and optional parent project. A project folder in the sidebar is an organizational container, not an implicit directory creation or deletion on disk. A root directory is chosen using the existing server directory picker. Child project folders may inherit the parent's root. No project deletion deletes host files. Project access to host directories remains admin-only, matching upstream file and workspace privileges.

Each chat may belong to one project. Project membership persists server-side. Opening or creating a project chat restores its bound workspace, and the backend derives that workspace from the project membership rather than trusting a browser's active global selection. Ordinary chats remain in Chats. Moving a chat to another project rebinds the root for future requests, without moving files or history. Archived/deleted projects do not leave chats able to access orphaned roots.

A project panel browses files/directories within the selected root. Choosing a file adds a reference chip to the composer; typing @ searches the project's relative paths, including names with spaces. Requests send structured paths and the backend loads bounded text from those paths, marking it untrusted context. Never interpret file text as user authorization. Show clear errors for missing files, binary files or overlarge context instead of silently including partial data. Keep per-file and aggregate text budgets and enforce symlink and traversal confinement using upstream's sensitive-file policy.

Before a project turn executes, record a bounded snapshot of eligible text files; after the turn, compare the current workspace with that baseline. This captures dedicated file-tool edits and shell edits within the project without depending on Git, and without touching the user's Git index or committing their work. Persist snapshots in Odysseus data, outside the project root. Clearly label comparison as changes since that turn's snapshot: concurrent manual edits can also appear, so do not claim cryptographic AI attribution. Capture additions, modifications and deletions; explicitly exclude binary, oversized, ignored and sensitive files and report limits. If a baseline cannot be captured, do not imply a complete diff. Block overlapping tracked turns for the same project to prevent misleading baselines.

The review panel shows changed files and line-aligned, escaped text side by side, with additions/deletions highlighted. Original and changed panes scroll together; narrow screens can scroll horizontally. Review is read-only in this iteration: no automatic undo, checkout, delete or Git stage actions. Original project files are only changed by the agent tools the user invokes.

## Architecture and limits

Use dedicated project storage/service and routes; versioned JSON persistence with atomic writes and a lock is suitable for this fork and avoids invasive session table migrations. Bind project membership by existing session IDs and validate ownership on every access. Use an event-driven frontend module integrated with existing session create/load hooks, composer submission and workspace picker. Use a narrow chat route integration to derive project scope, add references and bracket the streaming turn with snapshots. Use dedicated static CSS and testable pure JS diff/reference helpers.

Conservative file budgets: 1 MiB per snapshotted text file, 20 MiB total baseline, 2,000 files; 64 KiB per referenced file and 128 KiB aggregate per request. No broad home-directory scans. Respect .git, node_modules, virtualenvs, build output and upstream sensitive-file restrictions. A non-Git directory works. Do not silently increase shell authority or disable upstream approval gates. This workspace is not an OS security boundary: shell subprocesses retain host-user permissions.

## Validation

Test persistence, ownership, parent cycles, session association, workspace restoration, project scoping over browser input, path/symlink escapes, sensitive and binary files, size limits, changed/new/deleted files, concurrent turns, clean baseline versus dirty Git worktree and escaped rendering. Run relevant upstream workspace/session tests plus frontend unit checks and a browser smoke test of project create, chat creation, file reference and diff. Smoke test against isolated app state, not the user's auth database. Preserve Qwen vision configuration.

## Video application

Study xcpCz6eTW48 from its transcript and distinguish measurements for discrete VRAM from this Mac's 16 GB unified memory. Apply reliable tool-call and long-context evaluation to the feature tests; keep the existing Qwen profile and avoid installing a much larger model, aggressive KV quantization or speculative decoding without hardware-specific evidence. Save source-derived notes with explicit attribution and limitations.


## Accepted follow-up requirements

The first character `!` switches the existing composer into a visibly indicated Terminal mode and executes the remainder as an explicit human command in the project directory, with output in the chat. Removing the prefix restores AI appearance. No persistent interactive shell is required; the user explicitly requested the simpler prefix behavior. Apply a 120-second timeout and 256 KiB output limit; keep upstream agent approval separate. Show the actual current Git branch for an active project, refresh it, and handle detached HEAD/non-Git directories. Preserve the app's existing visual design, typography and theme variables; use scoped styles and its modal surface rather than a separate visual identity.
