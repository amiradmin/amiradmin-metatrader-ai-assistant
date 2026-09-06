from pathlib import Path


EA = Path("mt5/MetaTraderAI_DecisionTree.mq5")


def test_mt5_decision_tree_keeps_guarded_live_execution_path() -> None:
    source = EA.read_text(encoding="utf-8")

    assert 'BridgeBaseUrl+"/analyze"' in source
    assert "if(!MarketSessionOpenNow()) return;" in source
    assert "if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;" in source
    assert 'if(!JsonBool(json,"trade_allowed",false)) return;' in source
    assert 'if(side!="BUY" && side!="SELL") return;' in source
    assert "if(completed_bar<=0 || completed_bar<=LastExecutedBarTime) return;" in source
    assert "if(ManagedOpenPositions() >= effective_max) return;" in source
    assert "if(!BuildTradePlan(side,effective_risk,effective_rr,stop,target,volume,risk_money))" in source
    assert "Trade.Buy(" in source
    assert "Trade.Sell(" in source


def test_mt5_execution_is_demo_guarded_by_default() -> None:
    source = EA.read_text(encoding="utf-8")

    assert "input bool EnableAutoTrading = true;" in source
    assert "input bool DemoOnly = true;" in source
    assert 'if(DemoOnly && AccountModeText() != "DEMO") return;' in source
