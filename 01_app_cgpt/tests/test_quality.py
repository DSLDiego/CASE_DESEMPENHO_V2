"""Qualidade: desvio historico, reconciliacao, source_change, completude."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl import quality as Q


def test_source_change_10_to_20():
    iss = Q.check_source_change(10.0, 20.0, "SHELL", "2T2026", "REVENUE")
    assert iss is not None and iss.rule == "SOURCE_CHANGE" and "100" in iss.message


def test_deviation_thresholds():
    out = Q.check_deviation({"REVENUE": 30.0}, {"REVENUE": 100.0}, "X", "2T2026")
    assert out and out[0].severity == "WARNING"
    ok = Q.check_deviation({"REVENUE": 105.0}, {"REVENUE": 100.0}, "X", "2T2026")
    assert ok == []


def test_reconciliation():
    assert Q.reconcile(20.7, "A", 20.7, "B") == "RECONCILED"
    assert Q.reconcile(20.7, "A", 18.9, "B") == "RECONCILIATION_WARNING"


def test_completeness_matrix():
    iss = Q.check_completeness({"REVENUE"}, {"REVENUE", "OCF"}, "PETROBRAS", "2T2026")
    assert len(iss) == 1 and iss[0].indicator_id == "OCF"
