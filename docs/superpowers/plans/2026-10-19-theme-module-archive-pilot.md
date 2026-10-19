# Shared Theme Module and Archive Pilot Implementation Plan

> **For agentic workers:** Use executing-plans inline. The user already approved the overall theme design and current control/palette baseline; do not reopen those decisions.

**Goal:** Deliver a reusable three-theme module and an isolated entry using the actual project archive component.

**Architecture:** New theme-system owns palette, per-user/environment preferences, reversible document tokens, popup/grid adaptation and switcher. The existing production entry is unchanged during this pilot. A separate HTML entry on the existing5184 Vite server imports the actual archive component, uses an in-memory request adapter and fake records, and exercises the same form/query code without a backend.

**Tech Stack:** Existing Vue3, TypeScript, Element Plus, AG Grid, Pinia, Vue Router and Playwright. No dependencies or database changes.

## Constraints

- Workspace pms-theme-ui/PMS, detached564653d; no branch movement, commit, merge, push or deployment.
- Preserve approved compact dimensions and Noto Sans SC. Palettes exactly office blue/teal/graphite; fixed progress semantic colors red below50%, yellow below100%, green only truly complete.
- Preserve ProjectArchive.vue and business/form-draft/auth code. Only consume them in the isolated pilot. No server, OA or Kingdee access; never proxy unknown requests.
- Scope theme adaptation to an explicit document attribute. Dispose restores prior inline tokens. Do not enable theme switching on unreviewed production routes.
- Existing control preview remains available; the new pilot is a separate entry and uses the shared module.

## Task 1: Reusable Theme Behavior

Files: src/theme-system/core.ts; tests/theme-system.test.mjs.
Interface: createThemeSession({environment,root,storage,events}) provides setUser(id|null), choose(theme), subscribe(listener), dispose(), theme/active/key. Theme root uses standard attribute/style access only. No auth imports or network.

- [x] Write tests for A/B/environment separation, invalid value fallback, unavailable storage, same-user retained volatile choice, remote storage events, and disposal restoring existing tokens.
- [x] Run node --test tests/theme-system.test.mjs and confirm missing implementation failure.
- [x] Implement catalog, token mapping and session; fixed key version1 with only environment and user ID.
- [x] Run the same behavior tests to green.

## Task 2: Theme Components and Adapters

Files: src/theme-system/PmsThemeProvider.vue, PmsThemeSwitcher.vue, context.ts, theme.css, index.ts.
Interface: Provider consumes environment/userId, creates/provides session and owns cleanup; switcher consumes session and performs no query or routing. theme.css activates only under data-pms-theme.

- [x] Build provider/switcher using existing Element Plus controls; report storage failure without blocking switching.
- [x] Centralize approved dropdown/tree/calendar/checkbox/query/grid/drawer/button colors. Preserve existing form containers and dimensions.
- [x] Check types and build before mounting actual archive.

## Task 3: Actual Archive Pilot

Files: prototypes/theme-controls/archive-pilot.html, archive-pilot/{main.ts,App.vue,fixtures.ts}; update isolated vite.config.mjs inputs.
Interface: /archive-pilot.html uses a memory router for ProjectArchive.vue. A local axios adapter owns only synthetic data; unknown paths fail, all writes are local draft fixtures or rejected. No production app entry is altered.

- [x] Reuse current archive metadata fixture and create clearly synthetic rows/users/permissions.
- [x] Mount actual archive inside approved OA shell with shared provider/switcher.
- [x] Browser: open actual field/operator/reference/calendar and drawer; change theme with a draft and assert no reload/request/input or grid state loss. Test user preference separation, refresh, same-origin tabs, invalid/storage blocked and restore.
- [x] Verify one-instance/outside-close filter, metadata-driven required/readonly, validation without writes and approval preview display.
- [x] Run required style/list/system/archive contracts, npm run build, isolated multi-entry build and targeted browser checks. Record actual limitations rather than treating user acceptance as an AI blocker.
- [x] Independent read-only review, fix concrete findings, own change.md and evidence. Preserve source/production/Git boundaries and leave handoff here for coordinator.

Evidence: prototypes/theme-controls/ARCHIVE-PILOT-VERIFICATION.md and outputs/theme-module/browser-result.json. User-facing tab2 points to the actual archive isolated pilot. All plan items are complete within this phase; full-system migration is explicitly not represented as delivered.

This phase does not complete all-system migration. Continue approved independent work through this deliverable; concrete integration/production operations retain their separate boundaries.
