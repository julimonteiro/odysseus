# Projects Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task. Steps use checkbox syntax.

**Goal:** Add persistent directory-backed projects, related chats, file references and side-by-side change review to the user's Odysseus fork.
**Architecture:** Dedicated project service/routes/UI with narrow integration seams into sessions and chat streaming; bounded snapshots outside workspaces, respecting upstream path policy.
**Tech Stack:** Existing Python/FastAPI, atomic JSON storage, vanilla ES modules/CSS, pytest and Node tests.
**Spec:** docs/superpowers/specs/2026-10-18-projects-design.md

## Global constraints

Preserve upstream license, auth and approval policies, LAN UI and Qwen vision. No Git resets or index mutations in user projects. Admin-only host directory access. Metadata deletion never deletes host files. Keep fork modules separate and document explicit upstream merges.

## Review focus

Cross-user project/session IDs must fail closed. Symlink or parent traversal never escapes root. Snapshot truncation must be visible. Concurrent turns must not corrupt baselines. Existing unassociated chats must work unchanged.

## Task 1: Project service and API

Files: src/projects.py, routes/project_routes.py, app.py, tests/test_projects.py.
- [ ] Write failing tests for owner/admin checks, persistence, nested folders/cycles, session association, file references, path escapes and limits.
- [ ] Run and observe failures, implement atomic storage and API, rerun relevant tests.
- [ ] Commit cohesive backend change.

## Task 2: Turn scope and change tracking

Files: src/project_changes.py, routes/chat_routes.py, tests/test_project_changes.py, tests/test_project_chat_scope.py.
- [ ] Write failing tests for bounded snapshots, new/changed/deleted files, concurrent capture, shell changes, missing baselines and isolation.
- [ ] Implement before/after turn context wrapper, persisted read-only diffs and reference loading; integrate into the streaming chat path without bypassing auth.
- [ ] Run new and upstream workspace tests; commit.

## Task 3: Projects sidebar and composer

Files: static/js/projects.js, static/js/projectDiff.js, static/css/projects.css; narrow seams in static/app.js, static/index.html, static/js/sessions.js, static/js/chat.js, static/js/workspace.js.
- [ ] Add pure JS tests for line alignment, safe reference parsing and scoping; observe failures.
- [ ] Add tree/create/move/new-chat controls, file browser and @ references, active-root restoration and read-only diff viewer.
- [ ] Verify ordinary Chats exclude project chats and active roots do not leak into unrelated chats; commit.

## Task 4: Fork integration, video notes and validation

Files: docs/fork-maintenance.md, scripts/sync-upstream.sh, tests and documentation as needed.
- [ ] Document independent startup and safe upstream fetch/merge with preserved custom commits; no automatic destructive merges.
- [ ] Add video-derived configuration notes without treating source claims as verified facts.
- [ ] Run backend/frontend checks and isolated browser smoke; review diff and address defects.
- [ ] Push branch to origin, create fork PR, attach it to this chat and report tested capabilities and limitations.
