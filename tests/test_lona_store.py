from meta_trader_ai.lona_store import LonaReportStore


def test_lona_store_roundtrip(tmp_path):
    store = LonaReportStore(tmp_path / "lona.json")
    assert store.load()["status"] == "NOT_RUN"
    payload = {
        "status": "COMPLETED",
        "strategy_name": "demo",
        "metrics": {"win_rate": 55.0, "trades": 10},
    }
    assert store.save(payload) == payload
    assert store.load() == payload
