import pandas as pd
from pathlib import Path

DB_TABLES_DIR = Path(".").joinpath("research", "data", "database_tables")

# Input files
tech_wq_opt_file = DB_TABLES_DIR / "technology_wqpar_pystimelaopt.csv"
wqtech_file = DB_TABLES_DIR / "waterqualityparameter_technology.csv"

techprop_opt_file = DB_TABLES_DIR / "technologyproperty_pystimelaopt.csv"
techprop_junction_file = DB_TABLES_DIR / "technology_property.csv"

# Output files
out_wq_norm = DB_TABLES_DIR / "technology_wqpar_pystimelaopt_normalized.csv"
out_wq_issues = DB_TABLES_DIR / "technology_wqpar_pystimelaopt_mapping_issues.csv"

out_prop_norm = DB_TABLES_DIR / "technologyproperty_pystimelaopt_normalized.csv"
out_prop_issues = DB_TABLES_DIR / "technologyproperty_pystimelaopt_mapping_issues.csv"


def normalize_columns(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def build_mapping(junction_df, left_col, right_col, id_col="id"):
    """
    Returns:
      mapping: dict[(left, right)] -> list of ids
      duplicate_keys: dataframe of duplicate key groups
    """
    grouped = (
        junction_df
        .groupby([left_col, right_col], dropna=False)[id_col]
        .apply(lambda s: list(pd.unique(s)))
        .reset_index(name="junction_ids")
    )
    grouped["match_count"] = grouped["junction_ids"].apply(len)

    mapping = {
        (row[left_col], row[right_col]): row["junction_ids"]
        for _, row in grouped.iterrows()
    }

    duplicate_keys = grouped[grouped["match_count"] > 1].copy()
    return mapping, duplicate_keys


def map_to_junction_id(source_df, mapping, left_col, right_col, new_fk_col):
    normalized_rows = []
    issue_rows = []

    for _, row in source_df.iterrows():
        key = (row[left_col], row[right_col])
        matches = mapping.get(key, [])

        if len(matches) == 1:
            normalized_rows.append({
                "id": row["id"],
                new_fk_col: matches[0],
                "pystim_name": row["pystim_name"],
            })
        elif len(matches) == 0:
            issue_rows.append({
                "source_id": row["id"],
                left_col: row[left_col],
                right_col: row[right_col],
                "pystim_name": row.get("pystim_name", None),
                "issue": "missing junction mapping",
                "matched_junction_ids": "",
            })
        else:
            issue_rows.append({
                "source_id": row["id"],
                left_col: row[left_col],
                right_col: row[right_col],
                "pystim_name": row.get("pystim_name", None),
                "issue": "ambiguous junction mapping",
                "matched_junction_ids": ";".join(map(str, matches)),
            })

    return pd.DataFrame(normalized_rows), pd.DataFrame(issue_rows)


# ---------------------------
# 1. technology_wqpar_pystimelaopt
# ---------------------------

tech_wq_opt = normalize_columns(pd.read_csv(tech_wq_opt_file))
wqtech = normalize_columns(pd.read_csv(wqtech_file))

# Expected source columns:
# technology_wqpar_pystimelaopt.csv: id, technology_id, wqpar_id, pystim_name
# waterqualityparameter_technology.csv: id, waterqualityparameter, technology
required_tech_wq = {"id", "technology_id", "wqpar_id", "pystim_name"}
required_wqtech_base = {"id", "technology"}

missing = required_tech_wq - set(tech_wq_opt.columns)
if missing:
    raise ValueError(f"{tech_wq_opt_file.name} missing columns: {missing}")

missing = required_wqtech_base - set(wqtech.columns)
if missing:
    raise ValueError(f"{wqtech_file.name} missing columns: {missing}")

if "waterqualityparameter" in wqtech.columns:
    wq_col = "waterqualityparameter"
elif "waterquality" in wqtech.columns:
    wq_col = "waterquality"
else:
    raise ValueError(
        f"{wqtech_file.name} must contain "
        "'waterqualityparameter' or 'waterquality'"
    )

wq_mapping, wq_duplicate_keys = build_mapping(
    junction_df=wqtech,
    left_col="technology",
    right_col=wq_col,
    id_col="id",
)

wq_norm, wq_issues = map_to_junction_id(
    source_df=tech_wq_opt,
    mapping=wq_mapping,
    left_col="technology_id",
    right_col="wqpar_id",
    new_fk_col="wqparameter_technology_id",
)

# Because source uses technology_id/wqpar_id but mapping keys use technology/waterquality,
# rebuild using matching key names.
wq_mapping = {
    (tech, waterquality): ids
    for (tech, waterquality), ids in wq_mapping.items()
}

wq_norm_rows = []
wq_issue_rows = []

for _, row in tech_wq_opt.iterrows():
    key = (row["technology_id"], row["wqpar_id"])
    matches = wq_mapping.get(key, [])

    if len(matches) == 1:
        wq_norm_rows.append({
            "id": row["id"],
            "wqparameter_technology_id": matches[0],
            "pystim_name": row["pystim_name"],
        })
    elif len(matches) == 0:
        wq_issue_rows.append({
            "source_id": row["id"],
            "technology_id": row["technology_id"],
            "wqpar_id": row["wqpar_id"],
            "pystim_name": row["pystim_name"],
            "issue": "missing junction mapping",
            "matched_junction_ids": "",
        })
    else:
        wq_issue_rows.append({
            "source_id": row["id"],
            "technology_id": row["technology_id"],
            "wqpar_id": row["wqpar_id"],
            "pystim_name": row["pystim_name"],
            "issue": "ambiguous junction mapping",
            "matched_junction_ids": ";".join(map(str, matches)),
        })

wq_norm = pd.DataFrame(wq_norm_rows)
wq_issues = pd.DataFrame(wq_issue_rows)

wq_norm.to_csv(out_wq_norm, index=False)
wq_issues.to_csv(out_wq_issues, index=False)


# ---------------------------
# 2. technologyproperty_pystimelaopt
# ---------------------------

techprop_opt = normalize_columns(pd.read_csv(techprop_opt_file))
techprop_junction = normalize_columns(pd.read_csv(techprop_junction_file))

# Expected source columns:
# technologyproperty_pystimelaopt.csv: id, technology_id, property_id, pystim_name
# technology_property.csv: id, technology, property
required_techprop_opt = {"id", "technology_id", "property_id", "pystim_name"}
required_techprop_junction = {"id", "technology", "property"}

missing = required_techprop_opt - set(techprop_opt.columns)
if missing:
    raise ValueError(f"{techprop_opt_file.name} missing columns: {missing}")

missing = required_techprop_junction - set(techprop_junction.columns)
if missing:
    raise ValueError(f"{techprop_junction_file.name} missing columns: {missing}")

prop_mapping, prop_duplicate_keys = build_mapping(
    junction_df=techprop_junction,
    left_col="technology",
    right_col="property",
    id_col="id",
)

prop_norm_rows = []
prop_issue_rows = []

for _, row in techprop_opt.iterrows():
    key = (row["technology_id"], row["property_id"])
    matches = prop_mapping.get(key, [])

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
            "issue": "missing junction mapping",
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

prop_norm.to_csv(out_prop_norm, index=False)
prop_issues.to_csv(out_prop_issues, index=False)


# ---------------------------
# 3. Validation summary
# ---------------------------

print("Generated:")
print(f"- {out_wq_norm}")
print(f"- {out_wq_issues}")
print(f"- {out_prop_norm}")
print(f"- {out_prop_issues}")

print("\nValidation summary")
print("------------------")
print(f"technology_wqpar_pystimelaopt rows: {len(tech_wq_opt)}")
print(f"technology_wqpar_pystimelaopt mapped rows: {len(wq_norm)}")
print(f"technology_wqpar_pystimelaopt issue rows: {len(wq_issues)}")

print(f"technologyproperty_pystimelaopt rows: {len(techprop_opt)}")
print(f"technologyproperty_pystimelaopt mapped rows: {len(prop_norm)}")
print(f"technologyproperty_pystimelaopt issue rows: {len(prop_issues)}")

print(f"wqparameter_technology ambiguous keys: {len(wq_duplicate_keys)}")
print(f"technology_property ambiguous keys: {len(prop_duplicate_keys)}")

if not prop_duplicate_keys.empty:
    print("\nAmbiguous technology_property keys:")
    print(prop_duplicate_keys.to_string(index=False))

if not wq_duplicate_keys.empty:
    print("\nAmbiguous wqparameter_technology keys:")
    print(wq_duplicate_keys.to_string(index=False))