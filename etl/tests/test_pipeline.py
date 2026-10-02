"""End-to-end pipeline tests over the labeled fixture dataset (make test-etl).

They cover the five behaviors the ETL must guarantee: late arrivals update without duplicating,
idempotent re-runs, contract violations quarantined with their rule, content duplicates under a new
id quarantined, and business-key uniqueness policies (shared emails nulled, keep-first conflicts).
"""

from __future__ import annotations

import shutil

from conftest import TABLES_IN_FIXTURE, quarantine_rows, silver_rows

from etl.pipeline.run import run_pipeline
from etl.pipeline.state import StateStore


def run_all(cfg):
    """Run the pipeline over every table present in the fixture."""
    run_pipeline(cfg, tables=TABLES_IN_FIXTURE)


def test_late_arrival_updates_without_duplicating(cfg):
    late_dir = cfg.raw_dir / "transactions" / "year=2026" / "month=06" / "day=16"
    parked = cfg.raw_dir / "_parked_day16"
    late_dir.rename(parked)  # first delivery: day 15 only
    run_all(cfg)
    t1 = [r for r in silver_rows(cfg, "transactions", "transaction_id")
          if r["transaction_id"] == "TRX-T0001"]
    assert len(t1) == 1 and t1[0]["transaction_status"] == "Pending"

    parked.rename(late_dir)  # the late partition arrives with a newer process_date
    run_all(cfg)
    t1 = [r for r in silver_rows(cfg, "transactions", "transaction_id")
          if r["transaction_id"] == "TRX-T0001"]
    assert len(t1) == 1, "the late arrival must replace, not duplicate"
    assert t1[0]["transaction_status"] == "Approved"


def test_idempotent_second_run_is_a_noop(cfg):
    run_all(cfg)
    first = {t: silver_rows(cfg, t, "1") for t in TABLES_IN_FIXTURE}
    run_all(cfg)
    second = {t: silver_rows(cfg, t, "1") for t in TABLES_IN_FIXTURE}
    assert first == second
    state = StateStore(cfg)
    per_table = {}
    for run in state.runs():
        per_table[run[1]] = per_table.get(run[1], 0) + 1
    state.close()
    assert all(n == 1 for n in per_table.values()), f"second run must skip: {per_table}"


def test_contract_violations_go_to_quarantine(cfg):
    run_all(cfg)
    quarantined = {r["transaction_id"]: r for r in quarantine_rows(cfg, "transactions")}
    assert "contract.amount.greater_than_or_equal_to" in quarantined["TRX-T0005"]["rule_id"]
    assert "cast.amount" in quarantined["TRX-T0006"]["rule_id"]
    silver_ids = {r["transaction_id"] for r in silver_rows(cfg, "transactions", "transaction_id")}
    assert not {"TRX-T0005", "TRX-T0006"} & silver_ids


def test_content_duplicate_under_new_id_is_quarantined(cfg):
    run_all(cfg)
    quarantined = {r["transaction_id"]: r for r in quarantine_rows(cfg, "transactions")}
    assert "dedup.content_duplicate" in quarantined["TRX-T0004"]["rule_id"]
    silver_ids = {r["transaction_id"] for r in silver_rows(cfg, "transactions", "transaction_id")}
    assert "TRX-T0003" in silver_ids and "TRX-T0004" not in silver_ids


def test_business_key_uniqueness_policies(cfg):
    run_all(cfg)
    customers = {r["customer_id"]: r for r in silver_rows(cfg, "customers", "customer_id")}
    # shared email: nobody keeps it (null_all) and both rows are flagged
    assert customers["CLI-T001"]["email"] is None and customers["CLI-T001"]["email_shared"]
    assert customers["CLI-T002"]["email"] is None and customers["CLI-T002"]["email_shared"]
    assert customers["CLI-T003"]["email"] == "luz@mail.test" and not customers["CLI-T003"]["email_shared"]
    # a customer phone equal to an agent phone stays with the agent (rule B7)
    assert customers["CLI-T002"]["mobile_phone"] is None and customers["CLI-T002"]["phone_matches_agent"]
    # keep_first: the agent hired first keeps the duplicated employee code
    agents = {r["agent_id"]: r for r in silver_rows(cfg, "service_agents", "agent_id")}
    assert agents["AGT-T1"]["employee_code"] == "E90001" and not agents["AGT-T1"]["employee_code_conflict"]
    assert agents["AGT-T2"]["employee_code"] is None and agents["AGT-T2"]["employee_code_conflict"]
    # keep_first: the product opened first keeps the duplicated product number (then the column drops)
    products = {r["product_id"]: r for r in silver_rows(cfg, "products", "product_id")}
    assert not products["PRD-T002"]["product_number_conflict"]
    assert products["PRD-T003"]["product_number_conflict"]
    assert "product_number" not in products["PRD-T001"], "card/account numbers must not reach silver"


def test_standardization_and_derived_columns(cfg):
    run_all(cfg)
    customers = {r["customer_id"]: r for r in silver_rows(cfg, "customers", "customer_id")}
    assert customers["CLI-T001"]["country"] == "Mexico"
    assert customers["CLI-T002"]["document_type"] == "Passport"
    assert customers["CLI-T002"]["branch_unresolved"] and customers["CLI-T002"]["registration_branch_id"] is None
    assert "state" not in customers["CLI-T001"], "state is normalized into dim_cities"
    cities = {(r["city"], r["state"], r["country"]) for r in silver_rows(cfg, "dim_cities", "city")}
    assert ("Ciudad de México", "Ciudad de México", "Mexico") in cities

    products = {r["product_id"]: r for r in silver_rows(cfg, "products", "product_id")}
    assert products["PRD-T001"]["product_type"] == "Credit Card"
    assert products["PRD-T001"]["card_last4"] == "6475" and products["PRD-T001"]["card_brand"] == "visa"

    txns = {r["transaction_id"]: r for r in silver_rows(cfg, "transactions", "transaction_id")}
    assert txns["TRX-T0002"]["amount_usd"] == 10.0, "recomputed at the transaction-date rate"
    assert txns["TRX-T0002"]["amount_usd_source"] == 9.99
    assert txns["TRX-T0002"]["coords_invalid"] and txns["TRX-T0002"]["latitude"] is None
    assert txns["TRX-T0003"]["is_international"], "unaccented 'Mexico' marks a foreign purchase"
    assert not txns["TRX-T0001"]["is_international"]
    assert txns["TRX-T0001"]["transaction_country"] == "Mexico"


def test_dependencies_must_exist(cfg):
    import pytest

    with pytest.raises(SystemExit, match="needs silver"):
        run_pipeline(cfg, tables=["transactions"])


def test_schema_drift_fails_loudly(cfg):
    csv = cfg.raw_dir / "branches.csv"
    lines = csv.read_text(encoding="utf-8").splitlines()
    lines[0] += ",surprise_column"
    lines[1] += ",x"
    lines[2] += ",y"
    csv.write_text("\n".join(lines), encoding="utf-8")
    import pytest

    with pytest.raises(SystemExit, match="schema drift"):
        run_pipeline(cfg, tables=["branches"])
