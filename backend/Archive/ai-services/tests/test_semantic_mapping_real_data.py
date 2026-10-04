from pathlib import Path
import pandas as pd

from field_mapping.comparison import build_field_profiles
from field_mapping.semantic_mapper import map_fields

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "OneRecon_DataSet" / "Current Data" / "august"


def test_real_fa_gl_profiles_load():
    fa = pd.read_csv(DATA / "fa_report_202608.csv", nrows=500)
    gl = pd.read_xml(DATA / "gl_report_202608.xml", xpath="./*", parser="etree")
    sources = [
        {"source": "FA", "fields": build_field_profiles(fa)},
        {"source": "GL", "fields": build_field_profiles(gl)},
    ]
    assert len(sources[0]["fields"]) == 7
    assert "TransactionID" in {x["field"] for x in sources[1]["fields"]}


def test_real_crosswalk_maps_key_fields():
    fa = pd.read_csv(DATA / "fa_report_202608.csv", nrows=500)
    gl = pd.read_xml(DATA / "gl_report_202608.xml", xpath="./*", parser="etree")
    sources = [
        {"source": "FA", "fields": build_field_profiles(fa)},
        {"source": "GL", "fields": build_field_profiles(gl)},
    ]
    result = map_fields(sources, crosswalk_path=DATA / "join_map.txt")
    pairs = {
        (m["field"], m["matches"][0]["field"])
        for m in result["mappings"] if m["matches"]
    }
    assert ("fa_key", "gl_account_id") in pairs or ("gl_account_id", "fa_key") in pairs
    assert result["mapping_method"] == "crosswalk"
