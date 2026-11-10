"""Validate and normalize the pystimela_optim name mapping CSVs.

Cross-checks the curated pystim-name CSVs (mapping DRINQ technology
properties / water-quality parameters to pystimela_optim parameter names)
against the corresponding junction tables, flags mapping rows that don't
resolve to a real junction, and reports which `sent_to_optimizer` junctions
still have no pystim mapping at all.
"""
import pandas as pd
from pathlib import Path

DB_TABLES_DIR = Path(".").joinpath("research", "data", "database_tables")

# --- Water quality parameter <-> pystim name mapping -----------------------
# technology_wqpar_pystimelaopt.csv already stores the resolved
# WaterqualityParameterTechnologyJunction id directly (as
# wqparameter_technology_id), matching
# TechnologyWaterqualityParameterPystimelaoptJunction.wqparameter_technology.
# No join is needed here, only a validity check against the junction table.
WQ_PYSTIM_FILE = DB_TABLES_DIR / "technology_wqpar_pystimelaopt.csv"
WQ_JUNCTION_FILE = DB_TABLES_DIR / "waterqualityparameter_technology.csv"
WATERQUALITYPARAMETER_FILE = DB_TABLES_DIR / "waterqualityparameter.csv"

# --- Technology property <-> pystim name mapping ---------------------------
# technologyproperty_pystimelaopt.csv references (technology_id, property_id)
# pairs, which must be resolved to the technology_property.csv junction id;
# that junction id is what is stored in
# TechnologyPropertyPystimelaoptJunction.technology_property_id in the DB.
PROP_PYSTIM_FILE = DB_TABLES_DIR / "technologyproperty_pystimelaopt.csv"
PROP_JUNCTION_FILE = DB_TABLES_DIR / "technology_property.csv"
TECHNOLOGY_FILE = DB_TABLES_DIR / "technology.csv"
TECHNOLOGYPROPERTY_FILE = DB_TABLES_DIR / "technologyproperty.csv"

# Output files
OUT_WQ_NORM = DB_TABLES_DIR / "technology_wqpar_pystimelaopt_normalized.csv"
OUT_WQ_ISSUES = (
    DB_TABLES_DIR / "technology_wqpar_pystimelaopt_mapping_issues.csv"
)
OUT_WQ_MISSING = DB_TABLES_DIR / "technology_wqpar_pystimelaopt_missing.csv"

OUT_PROP_NORM = (
    DB_TABLES_DIR / "technologyproperty_pystimelaopt_normalized.csv"
)
OUT_PROP_ISSUES = (
    DB_TABLES_DIR / "technologyproperty_pystimelaopt_mapping_issues.csv"
)
OUT_PROP_MISSING = (
    DB_TABLES_DIR / "technologyproperty_pystimelaopt_missing.csv"
)


def normalize_columns(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def load_csv(path, required_columns):
    df = normalize_columns(pd.read_csv(path))
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns: {missing}")
    return df


def find_duplicate_targets(df, target_col, name_col="pystim_name"):
    """Rows where the same target junction id has conflicting pystim names."""
    if df.empty:
        return df.copy()
    grouped = df.groupby(target_col)[name_col].apply(lambda s: sorted(set(s)))
    conflicting_ids = grouped[grouped.apply(len) > 1].index
    return df[df[target_col].isin(conflicting_ids)].copy()


# ---------------------------------------------------------------------------
# 1. technology_wqpar_pystimelaopt -> waterqualityparameter_technology
# ---------------------------------------------------------------------------

wq_pystim = load_csv(
    WQ_PYSTIM_FILE, {"id", "wqparameter_technology_id", "pystimela_name"})
wq_junction = load_csv(
    WQ_JUNCTION_FILE,
    {"id", "waterqualityparameter", "technology", "sent_to_optimizer"},
)
wq_names = load_csv(WATERQUALITYPARAMETER_FILE, {"id", "name"})

wq_junction_ids = set(wq_junction["id"])

wq_norm_rows = []
wq_issue_rows = []
for _, row in wq_pystim.iterrows():
    junction_id = row["wqparameter_technology_id"]
    pystim_name = row["pystimela_name"]
    if junction_id in wq_junction_ids:
        wq_norm_rows.append({
            "id": row["id"],
            "wqparameter_technology_id": junction_id,
            "pystim_name": pystim_name,
        })
    else:
        wq_issue_rows.append({
            "source_id": row["id"],
            "wqparameter_technology_id": junction_id,
            "pystim_name": pystim_name,
            "issue": (
                "wqparameter_technology_id not found in "
                f"{WQ_JUNCTION_FILE.name}"
            ),
        })

wq_norm = pd.DataFrame(wq_norm_rows)
wq_issues = pd.DataFrame(wq_issue_rows)
wq_duplicate_targets = find_duplicate_targets(
    wq_norm, "wqparameter_technology_id")

wq_flagged = wq_junction[wq_junction["sent_to_optimizer"] == 1].copy()
wq_mapped_ids = (
    set(wq_norm["wqparameter_technology_id"]) if not wq_norm.empty else set()
)
wq_missing = wq_flagged[~wq_flagged["id"].isin(wq_mapped_ids)].copy()
wq_missing = wq_missing.merge(
    wq_names.rename(columns={
        "id": "waterqualityparameter",
        "name": "waterqualityparameter_name",
    }),
    on="waterqualityparameter", how="left",
)
wq_missing = wq_missing[
    ["id", "technology", "waterqualityparameter", "waterqualityparameter_name"]
]

wq_norm.to_csv(OUT_WQ_NORM, index=False)
wq_issues.to_csv(OUT_WQ_ISSUES, index=False)
wq_missing.to_csv(OUT_WQ_MISSING, index=False)


# ---------------------------------------------------------------------------
# 2. technologyproperty_pystimelaopt -> technology_property
# ---------------------------------------------------------------------------

prop_pystim = load_csv(
    PROP_PYSTIM_FILE, {"id", "technology_id", "property_id", "pystim_name"})
prop_junction = load_csv(
    PROP_JUNCTION_FILE,
    {"id", "technology", "property", "sent_to_optimizer"},
)
tech_names = load_csv(TECHNOLOGY_FILE, {"id", "name"})
property_names = load_csv(TECHNOLOGYPROPERTY_FILE, {"id", "name"})

prop_key_to_ids = (
    prop_junction
    .groupby(["technology", "property"])["id"]
    .apply(lambda s: list(pd.unique(s)))
)
prop_duplicate_keys = prop_key_to_ids[prop_key_to_ids.apply(len) > 1]

prop_norm_rows = []
prop_issue_rows = []

for _, row in prop_pystim.iterrows():
    key = (row["technology_id"], row["property_id"])
    matches = prop_key_to_ids.get(key, [])

    if len(matches) == 1:
        prop_norm_rows.append({
            "id": row["id"],
            "technology_property_id": matches[0],
            "pystim_name": row["pystim_name"],
        })
    elif len(matches) == 0:
        prop_issue_rows.append({
            "source_id": row["id"],
            "technology_id": row["technology_id"],
            "property_id": row["property_id"],
            "pystim_name": row["pystim_name"],
            "issue": f"no matching junction row in {PROP_JUNCTION_FILE.name}",
            "matched_junction_ids": "",
        })
    else:
        prop_issue_rows.append({
            "source_id": row["id"],
            "technology_id": row["technology_id"],
            "property_id": row["property_id"],
            "pystim_name": row["pystim_name"],
            "issue": "ambiguous junction mapping",
            "matched_junction_ids": ";".join(map(str, matches)),
        })

prop_norm = pd.DataFrame(prop_norm_rows)
prop_issues = pd.DataFrame(prop_issue_rows)
prop_duplicate_targets = find_duplicate_targets(
    prop_norm, "technology_property_id")

prop_flagged = prop_junction[prop_junction["sent_to_optimizer"] == 1].copy()
prop_mapped_ids = (
    set(prop_norm["technology_property_id"]) if not prop_norm.empty else set()
)
prop_missing = prop_flagged[~prop_flagged["id"].isin(prop_mapped_ids)].copy()
prop_missing = prop_missing.merge(
    tech_names.rename(columns={"id": "technology", "name": "technology_name"}),
    on="technology", how="left",
)
prop_missing = prop_missing.merge(
    property_names.rename(columns={"id": "property", "name": "property_name"}),
    on="property", how="left",
)
prop_missing = prop_missing[
    ["id", "technology", "technology_name", "property", "property_name"]
]

prop_norm.to_csv(OUT_PROP_NORM, index=False)
prop_issues.to_csv(OUT_PROP_ISSUES, index=False)
prop_missing.to_csv(OUT_PROP_MISSING, index=False)


# ---------------------------------------------------------------------------
# 3. Validation summary
# ---------------------------------------------------------------------------

print("Generated:")
for path in (
    OUT_WQ_NORM, OUT_WQ_ISSUES, OUT_WQ_MISSING,
    OUT_PROP_NORM, OUT_PROP_ISSUES, OUT_PROP_MISSING,
):
    print(f"- {path}")

print("\nValidation summary")
print("------------------")
print(f"technology_wqpar_pystimelaopt rows: {len(wq_pystim)}")
print(f"  mapped: {len(wq_norm)}, issues: {len(wq_issues)}")
print(
    "  sent_to_optimizer wq junctions with no pystim mapping: "
    f"{len(wq_missing)}"
)
print(f"  duplicate/conflicting pystim rows: {len(wq_duplicate_targets)}")

print(f"technologyproperty_pystimelaopt rows: {len(prop_pystim)}")
print(f"  mapped: {len(prop_norm)}, issues: {len(prop_issues)}")
print(
    "  sent_to_optimizer property junctions with no pystim mapping: "
    f"{len(prop_missing)}"
)
print(f"  ambiguous technology_property keys: {len(prop_duplicate_keys)}")
print(f"  duplicate/conflicting pystim rows: {len(prop_duplicate_targets)}")

if not wq_issues.empty:
    print("\ntechnology_wqpar_pystimelaopt mapping issues:")
    print(wq_issues.to_string(index=False))

if not wq_missing.empty:
    print("\nsent_to_optimizer WQ junctions with no pystim mapping:")
    print(wq_missing.to_string(index=False))

if not prop_issues.empty:
    print("\ntechnologyproperty_pystimelaopt mapping issues:")
    print(prop_issues.to_string(index=False))

if not prop_missing.empty:
    print("\nsent_to_optimizer property junctions with no pystim mapping:")
    print(prop_missing.to_string(index=False))

if not prop_duplicate_keys.empty:
    print("\nAmbiguous technology_property keys (technology, property):")
    print(prop_duplicate_keys.to_string())
