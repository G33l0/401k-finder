from __future__ import annotations

import pytest

from app.core.constants import PlanFeature, ProviderRole
from app.evidence.trail import build_plan_evidence
from app.search.engine import SearchEngine, build_match_expression
from app.search.query import PlanQuery, ProviderQuery, QueryOptions, SortOrder


@pytest.fixture()
def engine_for(session, imported):
    return SearchEngine(session)


def test_text_search_finds_by_sponsor(engine_for):
    results = engine_for.search_plans(PlanQuery(text="acme"))
    assert results
    assert all("ACME" in (result.sponsor_name or "").upper() for result in results)


def test_text_search_finds_by_plan_name(engine_for):
    results = engine_for.search_plans(PlanQuery(text="401"))
    assert results


def test_query_parse_recognises_an_ein(engine_for, session):
    from sqlalchemy import select

    from app.database.models import Plan

    plan = session.execute(select(Plan).limit(1)).scalar_one()

    query = PlanQuery.parse(f"{plan.ein[:2]}-{plan.ein[2:]}")
    assert query.ein == plan.ein
    assert not query.text

    results = engine_for.search_plans(query)
    assert any(result.plan_id == plan.id for result in results)


def test_query_parse_recognises_ein_and_plan_number(session, engine_for):
    from sqlalchemy import select

    from app.database.models import Plan

    plan = session.execute(select(Plan).limit(1)).scalar_one()

    query = PlanQuery.parse(f"{plan.ein}/{plan.plan_number}")
    assert query.ein == plan.ein
    assert query.plan_number == plan.plan_number

    results = engine_for.search_plans(query)
    assert len(results) == 1
    assert results[0].plan_id == plan.id


def test_query_parse_lifts_a_trailing_state():
    query = PlanQuery.parse("acme manufacturing IL")
    assert query.state == "IL"
    assert query.text == "acme manufacturing"


def test_explicit_state_overrides_the_inferred_one():
    query = PlanQuery.parse("acme manufacturing IL", state="NY")
    assert query.state == "NY"


def test_feature_filter(engine_for):
    results = engine_for.search_plans(PlanQuery(features=(PlanFeature.K401.value,)))
    assert results
    assert all(PlanFeature.K401.value in result.features for result in results)


def test_feature_filter_does_not_match_by_substring(engine_for):
    """A '|'-delimited feature match must not let 401K match a longer token."""

    results = engine_for.search_plans(PlanQuery(features=("401",)))
    assert results == []


def test_provider_filter(engine_for):
    results = engine_for.search_plans(PlanQuery(provider_name="Fidelity"))
    assert results

    for result in results:
        names = {party.display_name for party in result.parties}
        assert any("Fidelity" in name for name in names)


def test_role_filter(engine_for):
    results = engine_for.search_plans(PlanQuery(roles=(ProviderRole.RECORDKEEPER.value,)))
    assert results

    for result in results:
        assert any(party.role == ProviderRole.RECORDKEEPER.value for party in result.parties)


def test_state_filter(engine_for):
    results = engine_for.search_plans(PlanQuery(state="IL"))
    assert results
    assert all(result.state == "IL" for result in results)


def test_participant_threshold(engine_for):
    results = engine_for.search_plans(PlanQuery(min_participants=100))
    assert results
    assert all((result.participants or 0) >= 100 for result in results)


def test_sort_by_assets_is_descending(engine_for):
    results = engine_for.search_plans(PlanQuery(sort=SortOrder.ASSETS, limit=10))
    assets = [result.total_assets for result in results if result.total_assets is not None]
    assert assets == sorted(assets, reverse=True)


def test_count_matches_result_length_when_under_the_limit(engine_for):
    query = PlanQuery(text="acme", limit=500)
    assert engine_for.count_plans(query) == len(engine_for.search_plans(query))


def test_empty_query_is_recognised():
    assert PlanQuery().is_empty()
    assert not PlanQuery(text="acme").is_empty()


def test_primary_providers_are_deduplicated_and_ordered(engine_for):
    results = engine_for.search_plans(
        PlanQuery(roles=(ProviderRole.RECORDKEEPER.value,)),
        QueryOptions(include_parties=True, max_parties=100),
    )

    ordered = results[0].primary_providers()
    keys = [(party.provider_id, party.role) for party in ordered]

    assert len(keys) == len(set(keys))
    assert ordered[0].role == ProviderRole.RECORDKEEPER.value


def test_match_expression_escapes_fts_operators():
    assert build_match_expression('acme "corp"') == '"acme" AND "corp"*'
    assert build_match_expression("") == ""
    assert build_match_expression("*") == ""


def test_search_survives_fts_operator_characters(engine_for):
    """A user typing quotes or a hyphen must not produce a query error."""

    for text in ['"', "acme -corp", "acme*", "(acme)", "acme: inc"]:
        engine_for.search_plans(PlanQuery(text=text))


def test_provider_search(engine_for):
    results = engine_for.search_providers(ProviderQuery(role=ProviderRole.RECORDKEEPER.value))
    assert results
    assert all(result.plan_count >= 0 for result in results)


def test_provider_roles_breakdown(session, engine_for):
    results = engine_for.search_providers(ProviderQuery(limit=1))
    roles = engine_for.provider_roles(results[0].provider_id)
    assert roles
    assert all(count > 0 for _, count in roles)


def test_plan_detail_includes_filings(session, engine_for):
    results = engine_for.search_plans(PlanQuery(text="acme", limit=1))
    detail = engine_for.get_plan(results[0].plan_id)

    assert detail is not None
    assert detail.filing_count >= 1


def test_evidence_package_explains_each_provider(session, engine_for):
    results = engine_for.search_plans(
        PlanQuery(roles=(ProviderRole.RECORDKEEPER.value,), limit=1)
    )

    package = build_plan_evidence(session, results[0].plan_id)

    assert package is not None
    assert package.findings

    recordkeeper = next(
        finding
        for finding in package.findings
        if finding.role == ProviderRole.RECORDKEEPER.value
    )

    assert recordkeeper.evidence, "a finding with no evidence is unverifiable"

    item = recordkeeper.evidence[0]
    assert item.dataset == "F_SCH_C_PART1_ITEM2"
    assert item.field_name == "PROVIDER_OTHER_NAME"
    assert item.source_row is not None

    text = package.explain()
    assert recordkeeper.display_name in text
    assert "Source:" in text


def test_evidence_report_names_its_source_dataset(session, engine_for, tmp_path):
    """
    A report handed to a client has to say where the facts came from, in the
    product's own words. Asserted against the constant, not a literal, so the
    attribution can be reworded in one place.
    """

    from app.core.constants import SOURCE_LABEL
    from app.services.export import export_evidence_report

    results = engine_for.search_plans(PlanQuery(text="acme", limit=1))
    package = build_plan_evidence(session, results[0].plan_id)

    path = export_evidence_report(package, tmp_path / "evidence.txt")
    content = path.read_text(encoding="utf-8")

    assert SOURCE_LABEL in content
    assert "https://" not in content, "exported reports carry no web addresses"


def test_csv_export_flattens_providers_into_columns(session, engine_for, tmp_path):
    import csv

    from app.services.export import export_plans_csv

    results = engine_for.search_plans(PlanQuery(roles=(ProviderRole.RECORDKEEPER.value,)))
    path = export_plans_csv(results, tmp_path / "plans.csv")

    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == len(results)
    assert rows[0]["recordkeeper"]
    assert rows[0]["ein"]


def test_json_export_round_trips(session, engine_for, tmp_path):
    import json

    from app.services.export import export_plans_json

    results = engine_for.search_plans(PlanQuery(text="acme"))
    path = export_plans_json(results, tmp_path / "plans.json")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["plan_count"] == len(results)
    assert payload["plans"][0]["providers"]
