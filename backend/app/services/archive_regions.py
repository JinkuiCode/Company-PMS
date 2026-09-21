"""Offline archive address options from the bundled 2023 mainland snapshot."""
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "regions"
ADDRESS_FIELDS = ("address_province", "address_city", "address_detail")
MUNICIPALITIES = {"11", "12", "31", "50"}
DIRECT_COUNTY_GROUPS = {"省直辖县级行政区划", "自治区直辖县级行政区划"}


@lru_cache(maxsize=1)
def _load_regions() -> list[dict[str, Any]]:
    provinces = json.loads((DATA_DIR / "pc-code.json").read_text(encoding="utf-8"))
    county_provinces = json.loads((DATA_DIR / "pca-code.json").read_text(encoding="utf-8"))
    city_groups = {province["code"]: province["children"] for province in county_provinces}
    regions = []
    for province in provinces:
        children = []
        # pc-code flattens municipality districts; pca-code preserves city groups.
        for city in city_groups[province["code"]]:
            if city["name"] in DIRECT_COUNTY_GROUPS:
                # Flatten only source-defined direct counties, never ordinary districts.
                children.extend(
                    {"value": county["code"], "label": county["name"]}
                    for county in city["children"]
                )
                continue
            label = city["name"]
            if province["code"] in MUNICIPALITIES:
                if label == "市辖区":
                    label = province["name"]
                elif label == "县":
                    label = f"{province['name']}（县）"
            children.append({"value": city["code"], "label": label})
        regions.append({"value": province["code"], "label": province["name"], "children": children})
    return regions


def get_archive_regions() -> list[dict[str, Any]]:
    """Return province/city selector options without exposing the cached source."""
    return deepcopy(_load_regions())


def validate_archive_address(values: Mapping[str, Any]) -> None:
    """Validate a complete/merged address, not a raw partial PATCH payload.

    All three parts may be empty. Otherwise they must be complete and the city
    must belong to the selected province. Whitespace is ignored for validation;
    persistence normalization and merging updates remain the caller's job.
    """
    normalized = {}
    errors = []
    for key in ADDRESS_FIELDS:
        value = values.get(key)
        if value is not None and not isinstance(value, str):
            errors.append({"field_key": key, "message": "地址字段必须为文本"})
            normalized[key] = ""
        else:
            normalized[key] = value.strip() if value is not None else ""

    if not errors and not any(normalized.values()):
        return

    invalid_fields = {error["field_key"] for error in errors}
    for key in ADDRESS_FIELDS:
        if not normalized[key] and key not in invalid_fields:
            errors.append({"field_key": key, "message": "填写地址时，省份、城市和详细地址须全部填写"})

    province = normalized["address_province"]
    city = normalized["address_city"]
    if province:
        selected = next((item for item in _load_regions() if item["value"] == province), None)
        if selected is None:
            errors.append({"field_key": "address_province", "message": "请选择有效的省份"})
        elif city and city not in {item["value"] for item in selected["children"]}:
            errors.append({"field_key": "address_city", "message": "请选择该省份下的有效城市"})

    if errors:
        raise HTTPException(
            status_code=422,
            detail={"code": "FIELD_POLICY_VALIDATION_FAILED", "fields": errors},
        )
