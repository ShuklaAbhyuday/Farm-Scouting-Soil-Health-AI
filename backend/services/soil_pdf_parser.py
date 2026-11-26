"""Soil lab report PDF text extraction and structured agronomic parameter parsing."""
from __future__ import annotations

import io
import re
from typing import Any, Optional

from pypdf import PdfReader

TEXTURE_OPTIONS = [
    "Clay Loam",
    "Sandy Loam",
    "Silty Clay",
    "Silty Loam",
    "Loamy",
    "Sandy",
    "Clay",
]

# Approximate 0-15 cm plow-layer bulk-density factor (~2.24M kg soil/ha) for kg/ha -> mg/kg (ppm)
KG_HA_TO_MG_KG_DIVISOR = 2.24


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> tuple[str, int]:
    """Extract selectable text across all pages of an uploaded PDF file."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt.strip():
            pages_text.append(txt)
    return "\n".join(pages_text), len(reader.pages)


def _classify_nutrient_level(kind: str, val_mg_kg: float) -> str:
    if kind == "n":
        if val_mg_kg < 20:
            return "low"
        if val_mg_kg <= 60:
            return "medium"
        return "high"
    if kind == "p":
        if val_mg_kg < 15:
            return "low"
        if val_mg_kg <= 45:
            return "medium"
        return "high"
    if val_mg_kg < 100:
        return "low"
    if val_mg_kg <= 220:
        return "medium"
    return "high"


def _extract_nutrient(
    text: str,
    full_label_patterns: list[str],
    short_code: str,
    kind: str,
    conversions: list[str],
) -> tuple[Optional[float], Optional[str]]:
    """
    Search for numeric nutrient value (with optional mg/kg, ppm, or kg/ha unit) or qualitative level.
    Handles key-value lines ('Nitrogen (N): 18 mg/kg') and tabular rows ('Available Nitrogen | kg/ha | 185').
    """
    unit_grp = r"(mg\s*/\s*kg|ppm|kg\s*/\s*ha)"

    for pat in full_label_patterns:
        # Pattern 1: Label (optional parenthetical) [optional qual/unit] number [optional unit]
        num_re = re.compile(
            rf"(?:{pat})\s*(?:\([^)\n]*\))?\s*[:=\-|]?\s*(?:low|medium|moderate|high|sufficient|deficient)?\s*(?:{unit_grp})?\s*[:=\-|]?\s*(\d+(?:\.\d+)?)\s*{unit_grp}?",
            re.IGNORECASE,
        )
        m = num_re.search(text)
        if m:
            unit_before, num_str, unit_after = m.group(1), m.group(2), m.group(3)
            raw_val = float(num_str)
            unit = ((unit_after or unit_before) or "mg/kg").lower().replace(" ", "")
            if "kg/ha" in unit:
                mg_kg = round(raw_val / KG_HA_TO_MG_KG_DIVISOR, 2)
                conversions.append(f"{kind.upper()}: converted {raw_val} kg/ha -> {mg_kg} mg/kg (~15 cm plow layer)")
            else:
                mg_kg = round(raw_val, 2)
            return mg_kg, _classify_nutrient_level(kind, mg_kg)

        # Pattern 2: Qualitative label without number
        qual_re = re.compile(
            rf"(?:{pat})\s*(?:\([^)\n]*\))?\s*[:=\-|]?\s*(very\s+low|low|medium|moderate|high|deficient|sufficient|optimal)",
            re.IGNORECASE,
        )
        qm = qual_re.search(text)
        if qm:
            word = qm.group(1).lower()
            if "low" in word or "deficient" in word:
                return None, "low"
            if "high" in word:
                return None, "high"
            return None, "medium"

    # Strict fallback for single-letter symbol (e.g., "N: 14 mg/kg", "P = 11", "K (ppm): 145")
    strict_short_re = re.compile(
        rf"(?<![A-Za-z.]){re.escape(short_code)}(?:\s*\([^)\n]*\))?\s*[:=\-]\s*(\d+(?:\.\d+)?)\s*{unit_grp}?",
        re.IGNORECASE,
    )
    sm = strict_short_re.search(text)
    if sm:
        raw_val = float(sm.group(1))
        unit = (sm.group(2) or "mg/kg").lower().replace(" ", "")
        if "kg/ha" in unit:
            mg_kg = round(raw_val / KG_HA_TO_MG_KG_DIVISOR, 2)
            conversions.append(f"{kind.upper()}: converted {raw_val} kg/ha -> {mg_kg} mg/kg (~15 cm plow layer)")
        else:
            mg_kg = round(raw_val, 2)
        return mg_kg, _classify_nutrient_level(kind, mg_kg)

    return None, None


def parse_soil_report_text(text: str, page_count: int = 1) -> dict[str, Any]:
    """Parse common lab soil report text into structured SoilSample form fields."""
    cleaned = re.sub(r"[ \t]+", " ", text or "").strip()
    conversions: list[str] = []

    n_val, n_lvl = _extract_nutrient(
        cleaned,
        [
            r"available\s+nitrogen",
            r"mineral\s+nitrogen",
            r"total\s+nitrogen",
            r"nitrate(?:\s*-\s*n)?",
            r"nitrogen\s*\(\s*n\s*\)",
            r"nitrogen",
            r"\bavail\.?\s*n\b",
        ],
        "N",
        "n",
        conversions,
    )
    p_val, p_lvl = _extract_nutrient(
        cleaned,
        [
            r"available\s+phosphorus",
            r"extractable\s+phosphorus",
            r"phosphorus\s*\(\s*p(?:2o5)?\s*\)",
            r"phosphorus",
            r"phosphate",
            r"\bp2o5\b",
            r"\bavail\.?\s*p\b",
        ],
        "P",
        "p",
        conversions,
    )
    k_val, k_lvl = _extract_nutrient(
        cleaned,
        [
            r"available\s+potassium",
            r"exchangeable\s+potassium",
            r"potassium\s*\(\s*k(?:2o)?\s*\)",
            r"potassium",
            r"potash",
            r"\bk2o\b",
            r"\bavail\.?\s*k\b",
        ],
        "K",
        "k",
        conversions,
    )

    ph_val: Optional[float] = None
    ph_match = re.search(
        r"(?:soil\s+ph|ph\s+value|\bph\b)\s*(?:\([^)\n]*\))?\s*[:=\-|]?\s*(\d+(?:\.\d+)?)",
        cleaned,
        re.IGNORECASE,
    )
    if ph_match:
        cand_ph = float(ph_match.group(1))
        if 3.0 <= cand_ph <= 10.5:
            ph_val = round(cand_ph, 2)

    moisture_lvl: Optional[str] = None
    moisture_pct: Optional[float] = None
    m_num = re.search(r"(?:soil\s+)?moisture(?:\s+content)?\s*[:=\-|]?\s*(\d+(?:\.\d+)?)\s*%", cleaned, re.IGNORECASE)
    if m_num:
        moisture_pct = float(m_num.group(1))
        moisture_lvl = "low" if moisture_pct < 15 else ("high" if moisture_pct > 35 else "medium")
    else:
        m_txt = re.search(r"(?:soil\s+)?moisture\s*[:=\-|]?\s*(low|medium|moderate|high|dry|wet)", cleaned, re.IGNORECASE)
        if m_txt:
            w = m_txt.group(1).lower()
            moisture_lvl = "low" if w in ("low", "dry") else ("high" if w in ("high", "wet") else "medium")

    detected_texture: Optional[str] = None
    for tex in TEXTURE_OPTIONS:
        if re.search(rf"\b{re.escape(tex)}\b", cleaned, re.IGNORECASE):
            detected_texture = tex
            break

    detected_keys: list[str] = []
    missing_keys: list[str] = []
    if n_val is not None or n_lvl is not None:
        detected_keys.append("nitrogen")
    else:
        missing_keys.append("nitrogen")
    if p_val is not None or p_lvl is not None:
        detected_keys.append("phosphorus")
    else:
        missing_keys.append("phosphorus")
    if k_val is not None or k_lvl is not None:
        detected_keys.append("potassium")
    else:
        missing_keys.append("potassium")
    if ph_val is not None:
        detected_keys.append("ph")
    else:
        missing_keys.append("ph")
    if moisture_lvl is not None:
        detected_keys.append("moisture")
    if detected_texture is not None:
        detected_keys.append("soil_texture")

    parsed_fields = {
        "nitrogen_level": n_lvl,
        "nitrogen_value": n_val,
        "phosphorus_level": p_lvl,
        "phosphorus_value": p_val,
        "potassium_level": k_lvl,
        "potassium_value": k_val,
        "ph_value": ph_val,
        "moisture_level": moisture_lvl,
        "moisture_value": moisture_pct,
        "soil_texture": detected_texture,
        "source": "lab",
        "is_validated": True,
    }

    return {
        "parsed_fields": parsed_fields,
        "detected_keys": detected_keys,
        "missing_keys": missing_keys,
        "unit_conversions": conversions,
        "page_count": page_count,
        "text_preview": cleaned[:360],
        "extraction_success": len(detected_keys) > 0,
    }
