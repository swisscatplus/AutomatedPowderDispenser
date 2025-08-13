# streamlit_app.py
import streamlit as st
import json
from typing import Any, Dict, List, Tuple

# Adjust these imports to your actual package/module
from automatedsampler import AutomatedSampler, DispenserClient, ScaleController

st.set_page_config(page_title="Powder Sampler")
st.title("Automated Powder Sampler")

# ---- Helper: validation ----
def _material_has_pct(mat: Dict[str, Any]) -> bool:
    tol = mat.get("tolerance", {})
    return ("tol_pct" in mat) or ("pct" in tol)

def _material_has_abs(mat: Dict[str, Any]) -> bool:
    tol = mat.get("tolerance", {})
    return (
        ("tol_upper" in mat and "tol_lower" in mat) or
        ("upper" in tol and "lower" in tol)
    )

def validate_recipe(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if "vials" not in data or not isinstance(data["vials"], list) or len(data["vials"]) == 0:
        errors.append("Top-level key 'vials' must be a non-empty list.")
        return False, errors

    for vi, vial in enumerate(data["vials"], start=1):
        if not isinstance(vial, dict):
            errors.append(f"Vial #{vi}: must be an object.")
            continue

        if "materials" not in vial or not isinstance(vial["materials"], list) or len(vial["materials"]) == 0:
            errors.append(f"Vial #{vi}: 'materials' must be a non-empty list.")
            continue

        # Optional slot
        if "slot" in vial and not isinstance(vial["slot"], int):
            errors.append(f"Vial #{vi}: 'slot' must be an integer if provided.")

        for mi, mat in enumerate(vial["materials"], start=1):
            path = f"Vial #{vi} / Material #{mi}"
            if not isinstance(mat, dict):
                errors.append(f"{path}: must be an object.")
                continue

            name = mat.get("name")
            if not name or not isinstance(name, str):
                errors.append(f"{path}: 'name' is required and must be a string.")

            if "target_mg" not in mat:
                errors.append(f"{path} ({name or '?'}) : 'target_mg' is required.")
            else:
                try:
                    float(mat["target_mg"])
                except Exception:
                    errors.append(f"{path} ({name or '?'}) : 'target_mg' must be numeric.")

            # Tolerance: either pct OR abs (upper/lower[/unit]) possibly under 'tolerance'
            has_pct = _material_has_pct(mat)
            has_abs = _material_has_abs(mat)
            if not (has_pct or has_abs):
                errors.append(f"{path} ({name or '?'}) : provide 'tol_pct' "
                              f"or 'tol_upper'+'tol_lower' (optionally 'tol_unit'), "
                              f"or a nested 'tolerance' object with those fields.")
            else:
                if has_pct:
                    pct = mat.get("tol_pct", mat.get("tolerance", {}).get("pct"))
                    try:
                        float(pct)
                    except Exception:
                        errors.append(f"{path} ({name or '?'}) : tolerance.pct must be numeric.")
                if has_abs:
                    tol = mat.get("tolerance", {})
                    up = mat.get("tol_upper", tol.get("upper"))
                    lo = mat.get("tol_lower", tol.get("lower"))
                    if up is None or lo is None:
                        errors.append(f"{path} ({name or '?'}) : abs tolerance requires both upper and lower.")
                    else:
                        try:
                            float(up); float(lo)
                        except Exception:
                            errors.append(f"{path} ({name or '?'}) : tol_upper/lower must be numeric.")
                    unit = mat.get("tol_unit", tol.get("unit", "mg"))
                    if not isinstance(unit, str):
                        errors.append(f"{path} ({name or '?'}) : 'tol_unit' must be a string if provided.")

    return (len(errors) == 0), errors

# ---- Helper: concise summary for UI ----
def summarize_recipe(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for vi, vial in enumerate(data.get("vials", []), start=1):
        slot = vial.get("slot", vi)
        for mat in vial.get("materials", []):
            name = mat.get("name")
            target = mat.get("target_mg")

            tol = mat.get("tolerance", {})
            if "tol_pct" in mat or "pct" in tol:
                pct = mat.get("tol_pct", tol.get("pct"))
                tol_str = f"±{pct}%"
            else:
                up = mat.get("tol_upper", tol.get("upper", 0.0))
                lo = mat.get("tol_lower", tol.get("lower", 0.0))
                unit = mat.get("tol_unit", tol.get("unit", "mg"))
                tol_str = f"+{up}{unit} / -{lo}{unit}"

            rows.append({"Vial (slot)": slot, "Material": name, "Target (mg)": target, "Tolerance": tol_str})
    return rows

# ------------- UI -------------
st.markdown("#### Paste JSON recipe or upload a `.json` file")

placeholder = '''{
  "vials": [
    {
      "slot": 1,
      "materials": [
        { "name": "PowderA", "target_mg": 5.0, "tol_pct": 2.5 },
        { "name": "PowderB", "target_mg": 12.0,
          "tol_upper": 0.2, "tol_lower": 0.2, "tol_unit": "mg" }
      ]
    },
    {
      "slot": 2,
      "materials": [
        { "name": "PowderC", "target_mg": 1.75,
          "tolerance": { "upper": 0.03, "lower": 0.02, "unit": "mg" } }
      ]
    }
  ]
}'''

json_text = st.text_area("Recipe JSON", height=260, placeholder=placeholder)
uploaded = st.file_uploader("…or upload a .json file", type="json")

# Determine source of JSON
payload_raw = None
if uploaded:
    payload_raw = uploaded.read().decode("utf-8")
elif json_text and json_text.strip():
    payload_raw = json_text

col_run, col_preview = st.columns([1, 1])

with col_preview:
    if payload_raw:
        try:
            preview = json.loads(payload_raw)
            st.subheader("Preview")
            st.json(preview, expanded=False)
            rows = summarize_recipe(preview)
            if rows:
                st.dataframe(rows, use_container_width=True)
        except Exception as e:
            st.error(f"Cannot preview JSON: {e}")

with col_run:
    if st.button("Run Recipe", type="primary", use_container_width=True):
        if not payload_raw:
            st.error("▶ Please paste a JSON recipe or upload a `.json` file.")
        else:
            try:
                data = json.loads(payload_raw)
            except Exception as e:
                st.error(f"JSON parse error: {e}")
            else:
                ok, errs = validate_recipe(data)
                if not ok:
                    st.error("Validation failed. Please fix these issues:")
                    for err in errs:
                        st.markdown(f"- {err}")
                else:
                    st.info("▶ Starting automated sampling…")
                    # Instantiate your system. Adjust arguments to your real constructors.
                    system = AutomatedSampler(
                        robot_ip="192.168.0.2",
                        dispenser_class=DispenserClient,
                        scale_controller_class=ScaleController,
                        dispenser_args={"port": "COM3"},
                        scale_args={}
                    )
                    try:
                        with st.spinner("Running recipe on UR3e…"):
                            # Assuming your AutomatedSampler accepts raw JSON text
                            system.run(payload_raw)
                        st.success("✅ All vials processed successfully!")
                    except Exception as e:
                        st.error(f"Runtime error: {e}")
                    finally:
                        try:
                            system.disconnect()
                        except Exception:
                            pass
