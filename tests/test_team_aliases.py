import pandas as pd

from src.data_collection.team_aliases import ALIASES, canonical_team, normalize_matches


def test_alias_maps_to_canonical():
    assert canonical_team("GK ESPORTS") == "GEEKAY ESPORTS"
    assert canonical_team("MAN CITY") == "MANCHESTER CITY"


def test_lookup_is_case_and_whitespace_insensitive():
    assert canonical_team("  nrg ") == "NRG ESPORTS"


def test_unknown_and_none_pass_through():
    assert canonical_team("TEAM FALCONS") == "TEAM FALCONS"
    assert canonical_team(None) is None


def test_canonical_names_are_never_aliases():
    assert not set(ALIASES.values()) & set(ALIASES)


def test_normalize_matches_rewrites_file(tmp_path):
    path = tmp_path / "matches.parquet"
    pd.DataFrame(
        {"blue_team_name": ["MIBR", "TSM"], "orange_team_name": ["TSM", "GK ESPORTS"]}
    ).to_parquet(path)
    assert normalize_matches(path) == 2
    out = pd.read_parquet(path)
    assert out["blue_team_name"].tolist() == ["MADE IN BRAZIL", "TSM"]
    assert out["orange_team_name"].tolist() == ["TSM", "GEEKAY ESPORTS"]
