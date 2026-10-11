# Approved List Toolbar Implementation

Baseline: approved `frontend/prototypes/list-toolbar/` on 2026-10-11. Preserve
the existing query, authorization, personal-scheme and report-export behavior.
This batch is development-only: no production deployment, merge or push.

## Delivery Steps

- [x] Shared palette, equal-height controls, reference summaries and frameless removal.
- [x] Archive pilot: new action first, initialization tools in the right-side menu.
- [x] Reports: retain purchase view switch; put inventory/stock utilities in the scheme row.
- [x] Remaining lists: reuse shared module; business-only export coverage completed.
- [x] Current-version contract/build tests, real-browser interactions and change.md.

Separately approved scope: business documents and reports export; system management
does not export. New archive/project export permissions and the archive initialization
parameter were implemented and verified in development. The local SQLite database
was independently upgraded after a verified online backup; production remains unchanged.

Local revision: `2026-10-11-business-export-01`. Archive initialization defaults on;
turning it off hides tools and rejects workbook, preview, apply and line assignment.
Rollback remains available through its existing authorized API.

Verification: first add failing behavior/visual contracts; implement; run query
workspace/reference tests, style/list/system/archive contracts and frontend build.
Compare the real development pages to the approved mockup, including 24px control
height, long multi-reference values and responsive overflow.

Final export verification: 38 backend export/upgrade/response cases passed. Source
projection follows the query and visible-column contracts separately. A bounded
primary-key cursor prevents OFFSET page shifts during concurrent insert/delete;
external sorting restores the visible list order. This is not a point-in-time DB
snapshot. Response cleanup covers invalid ranges, send failures and cancellation.
After the final development backend restart, the real archive page returned 102
rows and its downloaded workbook contained 102 data rows, 14 columns and no formulas.
