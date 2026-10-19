# PMS Shared Theme Module

## Ownership and Activation

This module owns the approved office-blue, teal and graphite tokens, appearance preferences and central Element Plus / AG Grid adapters. It does not own business state, authentication, permissions, data requests or routing.

Mount one `PmsThemeProvider` per document. Supply the effective user ID from the existing authenticated store and a stable environment identity. Put `PmsThemeSwitcher` inside that provider, normally in the page header. A null user removes the theme and restores prior inline tokens. Unmounting restores owned document styles and removes storage listeners.

Only `html[data-pms-theme]` activates the adapters. The approved development rollout now integrates the actual App and layout in this isolated worktree, following the archive pilot. This is not a production deployment. App observes the existing Pinia identity without constructing an authentication store on public routes; the router, authentication store and request layer are unchanged.

## Preferences

- Key: `pms:theme:v1:<encoded environment>:<encoded user ID>`.
- Missing or invalid preference: office blue.
- Different users and environments remain isolated.
- Same-origin tabs follow storage events for the current user only.
- Optional `publicUser` uses `pms:theme:public:v1:<encoded environment>` for public help and login appearance. The value is only a theme ID, never a user ID or credential. Private preference keys remain user-specific; public hint events cannot overwrite them. Authenticated changes also update this appearance-only hint.
- Storage failure keeps the current choice in memory and gives a visible warning when switching.
- No server write, token, password, query condition, column layout or draft is stored here.

## Adapters

`theme.css` centralizes body popups, select/tree/date controls, tags, checkbox focus, buttons, AG Grid and Element tables. Business pages must not add per-theme copies of these rules. Sizes and fonts remain with the existing form/list systems.

`--pms-host-top` defaults to zero. A standalone host-shell demonstration may set the actual external header offset; a real OA iframe normally leaves it zero because the iframe has its own viewport. It is a layout measurement, not a hard-coded production OA assumption.

The appearance trigger and its menu stay reachable above non-modal drawer overlays. Primary solid actions use the theme color; plain/secondary actions remain restrained. Link and text button hover states retain a light background and dark readable text.

## Semantic Colors

Success, warning and error semantics do not change with the chosen theme. Approved progress tokens: red below50%, yellow from50% to below100%, green only for genuine completion. Consumers must use original business counts, not rounded display percentages, to determine completion. Zero progress must not receive a fabricated visible bar. Theme switching does not change metric formulas.

Use `progressAppearance(value, counts?)` for shared stage decisions and `PmsProgressIndicator` for read-only report bars. Provide an accessible metric `label` and original completed/total counts where available. The component explains incomplete rounded100% through its title and accessible value. `useThemeTokens()` subscribes to the same session for canvas/chart consumers; it does not request business data.

## Validation and Preview

Core behavior: `node --test tests/theme-system.test.mjs`.

Actual archive pilot: `prototypes/theme-controls/archive-pilot.html`; full evidence and limitations are in `prototypes/theme-controls/ARCHIVE-PILOT-VERIFICATION.md`.

The actual all-page entry is `prototypes/theme-controls/application-pilot.html`, including the real App, layout, router and business components in a simulated OA iframe. Synthetic records, identity aliases and memory history adaptation exist only in the preview configuration, never the production build configuration. Unknown requests fail closed. The original archive entry remains available for focused draft, column-state and storage-failure checks.

All-page evidence and remaining platform boundaries are recorded in `prototypes/theme-controls/ALL-PAGES-VERIFICATION.md`. Future pages inherit the provider and central adapters; they must still validate their own expanded controls and business-state preservation. No page should create a second provider or use theme changes to refresh data.
