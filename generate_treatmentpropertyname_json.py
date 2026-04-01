import csv
import json

csv_path = r"c:\Users\vriesdi\Code\to-drinq-dst\research\data\database_tables\technologyproperty.csv"
json_path = r"c:\Users\vriesdi\Code\to-drinq-dst\drinq\utils\treatmentpropertyname.json"

dict_out = {}
with open(csv_path, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row["name"]
        key = name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_per_").replace("%", "percent").replace("-", "_").replace(",", "").replace(".", "").replace("*", "star").replace("^", "").replace("__", "_").lower()
        key = key.replace("__", "_")
        dict_out[key] = name

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(dict_out, f, indent=2, ensure_ascii=False)
