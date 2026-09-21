# Archive Region Snapshot

## Source and Scope

- Upstream: https://github.com/modood/Administrative-divisions-of-China
- Pinned revision: `c49d495b40ac73eb1a66f6eeae5f8fd10696f035`.
- Data cutoff: **2023-06-30**; upstream states publication on **2023-09-11**.
- Retrieved: **2026-09-20**. This is a historical snapshot, not a claim of current administrative divisions. Upstream says data updates have stopped.
- Coverage: **31 mainland provincial-level regions only**. The source files exclude Hong Kong, Macao and Taiwan; the selector does not support addresses in those regions or overseas. This is a dataset coverage limitation, not a statement about territorial status.
- Upstream derives the data from National Bureau of Statistics statistical division codes. These codes/options are for this address selector, not a substitute for authoritative current administrative determinations.
- License: upstream **WTFPL**, preserved verbatim in `LICENSE`.

`pc-code.json`, `pca-code.json`, `LICENSE` and `UPSTREAM-README.md` are unmodified downloads from the pinned revision. `source.json` records exact URLs and SHA-256 digests. No data is fetched at runtime.

## Selector Mapping

- Province codes retain the source's two-digit strings. Ordinary city codes retain four digits. Province order/names come from `pc-code.json`; city groups come from matching provinces in `pca-code.json`, because `pc-code.json` already flattens municipality districts as well as direct counties.
- For Beijing, Tianjin, Shanghai and Chongqing, `市辖区` displays the actual municipality name without changing its code.
- Chongqing's separate `5002` county group remains selectable as `重庆市（县）`; its code is not merged with `5001`.
- `省直辖县级行政区划` and `自治区直辖县级行政区划` are expanded using the matching province/group in the same pinned `pca-code.json`. Their actual county-level names and six-digit codes become second-level options. Group codes (such as `4290`) are not selectable. No synthetic cities/codes are invented.
- Ordinary districts/counties are not a third selector level; users include those in the detailed address.

## Integration Contract

`get_archive_regions()` returns fresh `{value, label, children}` province options with `{value, label}` children. `validate_archive_address(values)` accepts a mapping of the **merged final state** for `address_province`, `address_city`, and `address_detail`, not an unmerged PATCH payload. All empty is valid; any populated part requires all three. Values are code strings, not display names. It returns `None` on success or raises structured HTTP 422 on failure. It ignores surrounding whitespace but does not mutate input; callers normalize before persistence.

Future refreshes must deliberately pin a new revision, verify its license/scope/date, update all checksums, rerun the contract test, and assess stored-code compatibility. Do not silently replace these assets at startup.
