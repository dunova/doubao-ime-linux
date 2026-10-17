# Changelog

## Unreleased

- Send original transcripts directly to official text organization by default.
- Make the optional local rewrite and semantic-check layer configurable with `organize_local_cleanup` or `DOUBAO_ORGANIZE_LOCAL_CLEANUP`; expose it in voice status.
- Add reproducible official-only versus local-rules comparison modes and document heuristic limitations.

## 0.1.0-rc.2 — 2026-10-17

- Upgrade the supported official Windows engine to 0.9.2.7.
- Add live dictation previews, Right Alt hold-to-talk and Right Alt+Space hands-free input.
- Add optional official smart text organization in a separate Wine runtime, with explicit spoken-correction handling, protected-content checks and accepted-transcript fallback (#2).
- Preserve speech recorded before the ASR connection is ready; add opt-in IPv4 voice connections and diagnostics.
- Fix candidate paging, add a settings tray action and distinct tray/launcher icons.
- Respect the Fcitx UI's candidate-layout preference (#4, thanks @dunova).
- Wait for a live keyboard test socket and document the one-request connection contract (#3).
- Expand local and CI validation, including cancellation, focus protections and reproducible source packaging.

Experimental source prerelease. Official components and the external ASR adapter
must be supplied separately. Windows smart undo and complete settings/account
synchronization parity remain unsupported.

## 0.1.0-rc.1

First source preview for the official DoubaoIME 0.9.0.0 keyboard engine on Fcitx 5.

- Native candidate/preedit UI, selection, segmented conversion and focus reset.
- Configurable Wine/Xvfb/MinGW paths and verified installer extraction.
- Separate official settings runtime with keyboard-only configuration merging.
- Optional Linux dictation coordinator and independent Fcitx delivery endpoint.
- User-level installation manifest, collision checks, rollback and removal.
- Private-display integration checks and an explicit source-package file list.
- Separate English and Chinese READMEs.
- GCC/Clang CI with mock-engine Fcitx/GTK tests and reproducible archive checks.
- Tagged GitHub Releases gated by the complete CI workflow.

Experimental release: fixed upstream ABI, incomplete Windows settings parity,
external ASR adapter required for voice, and no bundled official components.
