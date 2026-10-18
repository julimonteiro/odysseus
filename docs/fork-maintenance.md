# Projects fork: setup, use and upstream updates

This fork adds directory-backed Projects, project chats, selected-file context,
read-only side-by-side change review and explicit terminal commands to Odysseus.
The original license and normal setup remain in effect.

## Independent setup

Clone `https://github.com/julimonteiro/odysseus.git`, check out `codex/projects-workspaces`
(or `main` once its pull request is merged), then follow the existing native or
Docker setup guide. No Codex service is needed to run these features. Projects
and review state live in `ODYSSEUS_DATA_DIR/projects`, independently of Git.
Back up that directory together with the ordinary Odysseus data directory.
Project root paths belong to the server: remote clients use server files, not
their phone's or browser's local filesystem. Docker users must mount the
intended host directories into the container and select their container paths.

## Usage

1. In **Projects**, choose **+**, enter a name and browse to an existing directory.
2. Use the project's **+ Chat** to create related chats. Child project folders can
   group chats under the same root or another selected directory. The selected
   project's Git branch is shown beside its directory, including detached HEAD.
3. Open the project panel and click a file, or type **@** in a project chat to
   search text files. `@{src/my file.py}` supports paths containing spaces.
4. Start a message with **!** as its first character to execute a shell command
   directly, without sending it to the model. The composer changes to Terminal
   mode before submission. Example: `!git status`. Output is streamed into the
   chat, and the exit code is retained with history.
5. Open **Changes** beside the chat title/context indicator to browse this conversation’s tracked turns, including older pages. Select a file to see original text on the left and changed text on the right. Project-panel Changes still lists recent project turns. Snapshots remain readable from the conversation after its project is removed. Untracked historical changes cannot be reconstructed.

`!` commands run in a fresh shell in the bound directory. For multiple steps,
use `!cd subdirectory && command`. Shell state is not retained between messages;
interactive programs that require a TTY or input are not supported. Commands
stop after 120 seconds and output is capped at 256 KiB. A disconnected terminal
stream cancels its process group on POSIX. Explicit user commands are separate
from agent-generated shell tool calls; upstream agent approval checks remain.

## Project file work

Project membership provides a deterministic small file-tool set on every agent turn, including short/non-English continuations. It does not depend on English keywords or vector retrieval. Global/user tool restrictions, Plan mode, delegated-token restrictions and sealed-action approvals still apply. An approval shown in the chat must be accepted before its write occurs.

The native tools are `get_workspace`, `ls`, `glob`, `grep`, `read_file`, `write_file`, `edit_file` and `apply_patch`. Search uses ripgrep when installed and a bounded fallback otherwise; `read_file` supports line offsets/limits. Locate relevant code, read focused ranges, and apply precise edits. These operations work on text across languages and architectures without building a language-specific index of the entire repository. They do not guarantee that a model understands every language or makes correct edits.

`!` is reserved for direct terminal execution; app slash commands use `/`. The compact composer badge displays project/branch while the directory remains in the workspace/project panel.

## Access and change review boundaries

Projects and explicit terminal commands require an administrator browser
session. Delegated API tokens do not inherit host-project authority. File
references obey upstream sensitive-file and workspace rules. **A workspace is
not an operating-system sandbox**: shell commands retain the host user's file
and network access. Deleting a project removes it and its child project folders from the sidebar,
returns their chats to Chats, and never deletes host files. The × action on the
project row and Delete project in its panel use the same confirmation dialog. Files/directories on disk are created only by the explicit directory
action or commands/tools the user invokes.

Reviews compare a bounded snapshot taken before the turn with eligible files
after it finishes. They cover additions, changes and deletions, including shell
edits, without touching a Git index or creating user-repository commits. Manual
edits during the same interval may also appear. Overlapping roots are locked
against concurrent tracked turns, including parent/child projects.

Sensitive files, binary/non-UTF8 files, symlinks, common dependency/build trees
and files over 1 MiB are excluded. Snapshots stop at 2,000 files/directories or
20 MiB of text; partial coverage is displayed. File references allow 64 KiB per
file and 128 KiB total, and reject context overflow rather than silently clipping.
Large diffs use approximate alignment and display up to 5,000 rows, with a notice.
Review history contains file contents: keep Odysseus data private and include it
in your storage/retention policy. Review is read-only; there is no automatic
rollback of files or Git operations.

## Merge upstream while preserving fork features

Keep two remotes:

```
git remote add upstream https://github.com/odysseus-dev/odysseus.git
# origin is your own fork, not upstream.
```

Use `scripts/sync-upstream.sh --check main` to fetch and inspect changes from
the curated branch, then `scripts/sync-upstream.sh --merge main` on the branch
you want to update. The script refuses dirty worktrees and uses a normal merge,
never `reset --hard`, forced push or copying upstream files over custom code.
A merge can conflict. Resolve each conflict deliberately, run the tests below,
then push to your fork and review the update in a pull request. Keep custom
commits in history. The fork-owned modules are `src/projects.py`,
`src/project_changes.py`, `src/project_turns.py`, `src/project_terminal.py`,
`routes/project_routes.py`, `static/js/projects.js`, `static/js/projectDiff.js`
and `static/css/projects.css`; upstream integration seams are intentionally small.

```
python -m pytest tests/test_projects.py tests/test_project_changes.py tests/test_project_routes.py tests/test_project_terminal.py tests/test_project_chat_scope.py
node --test tests/project-ui.test.mjs
```

Also run upstream workspace/session tests before merging an upstream update.
At baseline `934d23c`, `test_workspace_confine.py::test_glob_confined_e2e` has a
macOS `/var` versus `/private/var` path-echo assertion failure; the other 24
workspace tests pass. It is unrelated to the Projects extension.
