import json
import os
import zipfile
from pathlib import Path

# ========== SETTINGS ==========
CAP_ROOT = "melilo_raw_texts/case-law-archive"   # folder that contains the .zip files
OUTPUT_DIR = "raw_texts"
MAX_FILES = 50          # set to None when you want everything
CONUS_ONLY = True
# ==============================

os.makedirs(OUTPUT_DIR, exist_ok=True)

SKIP_JURISDICTIONS = {"Hawaii", "Alaska", "Haw.", "Alaska"}

def is_conus(jurisdiction_name):
    if not jurisdiction_name:
        return True
    return not any(skip.lower() in jurisdiction_name.lower() for skip in SKIP_JURISDICTIONS)

count = 0

# Walk through all zip files in CAP_ROOT
for root, dirs, files in os.walk(CAP_ROOT):
    for file in files:
        if not file.endswith(".zip"):
            continue

        zip_path = os.path.join(root, file)
        print(f"\nScanning zip: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                # Look for JSON files inside the zip
                json_files = [name for name in z.namelist() if name.endswith(".json") and "metadata" not in name.lower()]

                for json_name in json_files:
                    try:
                        with z.open(json_name) as f:
                            data = json.load(f)
                    except Exception as e:
                        print(f"  Skipping {json_name}: {e}")
                        continue

                    # Jurisdiction filter
                    jurisdiction = (
                        data.get("jurisdiction", {}).get("name_long")
                        or data.get("jurisdiction", {}).get("name", "")
                    )
                    if CONUS_ONLY and not is_conus(jurisdiction):
                        continue

                    # Get opinion text
                    opinions = data.get("casebody", {}).get("opinions", [])
                    if not opinions:
                        continue

                    text = opinions[0].get("text", "").strip()
                    if not text or len(text) < 200:
                        continue

                    # ----- Metadata header -----
                    name = data.get("name") or data.get("name_abbreviation") or "Unknown Case"
                    name_abbr = data.get("name_abbreviation", "")
                    decision_date = data.get("decision_date", "")
                    court = data.get("court", {}).get("name", "")

                    citations = [c.get("cite") for c in data.get("citations", []) if c.get("cite")]
                    citation_str = " | ".join(citations) if citations else "No citation"

                    header = f"""Case: {name}
Abbreviation: {name_abbr}
Court: {court}
Jurisdiction: {jurisdiction}
Decision Date: {decision_date}
Citations: {citation_str}
--------------------------------------------------

"""

                    # Clean filename
                    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in (name_abbr or name))
                    safe_name = safe_name[:80].strip().replace(" ", "_")
                    if not safe_name:
                        safe_name = Path(json_name).stem

                    out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.txt")

                    # Avoid overwriting if same name already exists
                    if os.path.exists(out_path):
                        safe_name = f"{safe_name}_{count}"
                        out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.txt")

                    with open(out_path, "w", encoding="utf-8") as out:
                        out.write(header)
                        out.write(text)

                    count += 1
                    print(f"  Extracted: {out_path}")

                    if MAX_FILES and count >= MAX_FILES:
                        print(f"\nReached limit of {MAX_FILES} files (smoke test mode).")
                        break

        except Exception as e:
            print(f"Error reading zip {zip_path}: {e}")
            continue

        if MAX_FILES and count >= MAX_FILES:
            break

    if MAX_FILES and count >= MAX_FILES:
        break

print(f"\nDone! Extracted {count} cases into '{OUTPUT_DIR}/'")