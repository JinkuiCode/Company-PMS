# Approved Three-Theme Rollout, Development Only

User approval: continue the confirmed design through the three reports and all remaining pages, without waiting after the archive pilot; no production deployment. Reuse the current isolated worktree/base564653d and the approved module/control/progress baseline. Execute inline with executing-plans, TDD for behavior and browser verification for visual adapters. No main checkout, backend, schema, permissions, authentication flow, commit/merge/push or production changes.

## 1. Reports and Shared Progress

- [x] Add behavior tests in tests/theme-rollout.test.mjs for red below50, yellow50-to-below100, exact completion green, null/invalid/zero and rounded100 with incomplete original counts; observe RED.
- [x] Add src/theme-system/progress.ts exporting progressAppearance(value, counts?), and PmsProgressIndicator.vue consuming its result. Use count evidence only for color, never change rate formulas or report requests. Replace PurchaseOverviewList's private renderer with the shared component; preserve widths, columns, sort and drilldown.
- [x] Replace the purchase view-switch's old private colors with existing theme tokens. Verify purchase overview/detail, inventory and stock-detail using real components and isolated fixtures; reports remain pending on entry and stock required fields remain enforced.

## 2. Application Entry and Remaining Pages

- [x] Extend existing session tests before implementation: optional publicUser creates an anonymous appearance-only key, authenticated keys remain isolated, public tabs follow only appearance events and never gain identity or permissions.
- [x] In App.vue wrap router-view with one PmsThemeProvider; pass current user ID or anonymous public identity. Add the shared switcher to AppLayout. Independent help inherits the last appearance without adding another toolbar or initializing an identity. Do not edit router/auth/request behavior.
- [x] Replace native pagination choice with existing PmsSelectControl; preserve 15/20/50/100/200/300/500, event semantics and26px outer height. Verify keyboard, expanded menu and no overflow.
- [x] Reuse shared progress stage helper in Dashboard, ProjectList and ProjectProgress; keep calculated values and editing behavior. Dashboard chart options consume reactive theme tokens rather than fixed indigo/canvas font values.
- [x] Tokenize existing private accent leftovers in the shared stylesheet and affected project/system pages. Keep semantic error/warning/success colors distinct. Expand central theme adapters for messages, menus, tabs, sliders, loading, empty/error states and grid editors without per-page third-party overrides.

## 3. All-Page Verification and Handoff

- [x] Extend the5184 isolated host with an actual application entry (all routes, real App/layout/pages, fake user and fail-closed fixtures). Router history adaptation and fixture aliases live only in its Vite config. No backend proxy, no external data.
- [x] Run a browser acceptance against all actual route families in three themes. Check report entry/query, drawer/editor/reference/date/filter/menu states, user/environment memory, refresh, public help appearance, no theme-triggered business request, and compact OA dimensions at desktop/narrow widths. Collect route coverage, screenshots and page errors; explicitly separate mocked-data acceptance from live backend/Windows/OA.
- [x] Run core/new behavior tests; affected report/list/pagination/guide/project contracts; required style/list/system/archive checks; both actual and isolated builds. Fix introduced failures and perform independent read-only review.
- [x] Update own change.md, exact evidence, full-scope ledger and local handoff. Leave all-page development preview online. Do not deploy or merge. Completion refers to development implementation and applicable AI technical checks, not a claim of production/real-OA verification.

Interfaces: the existing createThemeSession gains only optional publicUser. The public key contains a theme ID, no user ID/token. Provider passes the option and owns cleanup as before. Shared progress returns width percentage plus stage (low/mid/complete/empty), a semantic token and fixed fallback color; callers preserve their established number formatting.
