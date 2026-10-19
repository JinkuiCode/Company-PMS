# Shared Theme Module / Actual Archive Pilot

Date: 2026-10-19. Worktree: `/Users/jin/.codex/worktrees/pms-theme-ui/PMS`, detached source base `564653da4f1461eb985515517ece697a1c378793`.

## Delivered Scope

- New `src/theme-system/` owns the approved three palettes, document token lifecycle, environment/user preference isolation, storage-event synchronization, switcher, and centralized control/popup/grid/table adapters.
- `/archive-pilot.html` mounts the actual ProjectArchive component inside the approved compact OA demonstration shell. It uses64 synthetic records, a fixture identity, an in-memory draft adapter and no API proxy. Unknown requests fail closed.
- Production entry, actual archive component, auth store, request interceptor, backend, database, permissions, main checkout and server are unchanged.
- The original control and approved red/yellow/green progress previews remain available on5184. Their separate preview preference keys are intentionally retained; the new module uses its own versioned environment/user keys.

## Verification

Commands in this worktree's frontend directory, all exit0:

```sh
node --test tests/theme-system.test.mjs tests/theme-controls.test.mjs tests/theme-controls-ui.test.mjs
./node_modules/.bin/vue-tsc -p prototypes/theme-controls/tsconfig.json --noEmit
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/archive-filter-contract.test.mjs
npm run build
./node_modules/.bin/vite build --config prototypes/theme-controls/vite.config.mjs
THEME_PILOT_BASE=http://127.0.0.1:5185 node tests/theme-archive-pilot-browser.mjs
```

- Core theme behavior: six new tests, RED missing implementation to GREEN. Together with prior controls checks:11 passed.
- Browser uses the isolated production build temporarily served at5185, not the main PMS build. The persistent demonstration remains at5184.
- Actual field/operator/reference/drawer/calendar popups checked in all three themes. Secondary buttons remain restrained; link/text hover remains legible.
- Theme changes preserve a nonempty query, ascending sort, page2, a resized column, selected rows, scroll position and dirty form inputs. No archive query is triggered by a theme change.
- Same-origin tab changes preserve the first tab's open draft. Required validation submits no backend write; approval preview uses the real archive confirmation component.
- A fresh browser with an inaccessible localStorage getter still loads the isolated production build, changes theme and reports inability to remember it. The development-only Pinia devtools initialization itself accesses localStorage; this is why the complete denial scenario is tested against the production build. The original production auth code is not silently changed to claim full authenticated-system support.
- 1366x768,768x900 and390x844 CSS viewports keep the host layout and real drawer inside the viewport. The test does not certify every business field's mobile usability.
- Browser result: `outputs/theme-module/browser-result.json`; screenshots in the same directory. No page errors, no real API/external request.
- Build emits existing chunk-size advisories; no build failure.

## Read-Only Review Closure

Independent reviewer found five P2 items; each was addressed:

1. Isolated identity/request dependencies avoid real auth storage assumptions; production-build storage-denial browser test passes.
2. Solid primary hover excludes link/text/plain; a browser style probe checks the approved light background and readable hover text for all palettes.
3. Host offset token keeps the real drawer below the actual pilot header. Appearance trigger/menu remain reachable above the non-modal overlay; direct dirty-draft switching passes.
4. Scoped Element table tokens and hover adapter remove old blue from the archive approval table; browser computed-color check passes in teal.
5. Browser regression explicitly establishes and checks nondefault query/sort/page/width/selection/scroll state, plus same-page and sibling-tab dirty drafts.

The reviewer inspected existing screenshots/core tests and did not re-run the final browser suite; the implementation owner ran the closure tests above.

## Integration Boundary

The shared module and actual-archive isolated pilot are delivered, not an all-page production migration. Subsequent report/page batches and the main-layout integration retain the existing single-writer coordination and review boundaries. No commit, merge, push or deployment was performed. Windows rasterization, real OA iframe/SSO and production data were not tested or represented as passing. These evidence limits are not a new request for the user to repeat the already-approved palette decision.
