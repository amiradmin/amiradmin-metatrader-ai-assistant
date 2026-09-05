#property strict
#property version   "0.24"
#property description "Six-factor explainable MT5 decision tree with guarded DEMO auto-execution, bridge controls, live tick-volume context and historical replay sync"

#include <Trade/Trade.mqh>

input string TradeSymbol = "XAUUSD_o";
input string BridgeBaseUrl = "http://127.0.0.1:8000";
input ENUM_TIMEFRAMES AnalysisTimeframe = PERIOD_M15;
input int SnapshotBars = 120;
input int SignalSeconds = 15;
input int RequestTimeoutMs = 10000;
input int HistorySyncBars = 5000;
input int HistorySyncSeconds = 600;
input int HistoryInitialRetrySeconds = 10;

input bool EnableAutoTrading = true;
input bool DemoOnly = true;
// Backward-compatible fallbacks. EA v0.23+ normally receives these from Bridge /control.
input double RiskPercent = 0.50;
input double RewardRiskRatio = 2.0;
// Local hard ceiling. Bridge /control can choose 1..5, but can never exceed this.
input int MaxOpenTrades = 5;
input int SlippagePoints = 20;
input ulong MagicNumber = 26090501;
input int AtrPeriod = 14;
input double AtrMultiplier = 1.50;
input int MinStopPoints = 150;
input int MaxStopPoints = 1200;

input int PanelLeft = 20;
input int PanelTop = 30;
input int PanelWidth = 610;
input int PanelHeight = 480;
input int PanelFontSize = 12;

CTrade Trade;
int AtrHandle = INVALID_HANDLE;
ulong LastSignalCheckMs = 0;
ulong LastHistorySyncMs = 0;
ulong LastHistoryAttemptMs = 0;
string HistorySyncState = "PENDING";
string LastExecutedSignalId = "";
datetime LastExecutedBarTime = 0;
string PanelPrefix = "MTAI6_";

string ExecutedBarGlobalName()
{
   return "MTAI6_LASTBAR_" + TradeSymbol + "_" + IntegerToString((int)MagicNumber);
}

string PositionRiskGlobalName(const long position_id)
{
   return "MTAI6_RISK_" + IntegerToString((int)position_id);
}

string AccountModeText()
{
   ENUM_ACCOUNT_TRADE_MODE mode = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode == ACCOUNT_TRADE_MODE_DEMO) return "DEMO";
   if(mode == ACCOUNT_TRADE_MODE_REAL) return "REAL";
   if(mode == ACCOUNT_TRADE_MODE_CONTEST) return "CONTEST";
   return "UNKNOWN";
}

string TfText()
{
   if(AnalysisTimeframe == PERIOD_M15) return "M15";
   if(AnalysisTimeframe == PERIOD_M5) return "M5";
   if(AnalysisTimeframe == PERIOD_H1) return "H1";
   return EnumToString(AnalysisTimeframe);
}

string BrokerDate(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   return StringFormat("%04d-%02d-%02d", parts.year, parts.mon, parts.day);
}

bool MarketSessionOpenNow()
{
   datetime now = TimeTradeServer();
   if(now <= 0) now = TimeCurrent();
   if(now <= 0) return false;

   MqlDateTime now_parts;
   TimeToStruct(now, now_parts);
   ENUM_DAY_OF_WEEK day = (ENUM_DAY_OF_WEEK)now_parts.day_of_week;
   int now_seconds = now_parts.hour * 3600 + now_parts.min * 60 + now_parts.sec;

   datetime from = 0;
   datetime to = 0;
   for(uint session = 0; session < 20; session++)
   {
      if(!SymbolInfoSessionTrade(TradeSymbol, day, session, from, to))
         break;
      MqlDateTime from_parts, to_parts;
      TimeToStruct(from, from_parts);
      TimeToStruct(to, to_parts);
      int from_seconds = from_parts.hour * 3600 + from_parts.min * 60 + from_parts.sec;
      int to_seconds = to_parts.hour * 3600 + to_parts.min * 60 + to_parts.sec;
      if(from_seconds == to_seconds)
         return true;
      if(from_seconds < to_seconds)
      {
         if(now_seconds >= from_seconds && now_seconds < to_seconds)
            return true;
      }
      else
      {
         if(now_seconds >= from_seconds || now_seconds < to_seconds)
            return true;
      }
   }
   return false;
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   return value;
}

bool JsonBool(const string json, const string key, const bool fallback=false)
{
   string needle = "\"" + key + "\"";
   int p = StringFind(json, needle);
   if(p < 0) return fallback;
   p = StringFind(json, ":", p + StringLen(needle));
   if(p < 0) return fallback;
   string tail = StringSubstr(json, p + 1, 8);
   StringTrimLeft(tail);
   if(StringFind(tail, "true") == 0) return true;
   if(StringFind(tail, "false") == 0) return false;
   return fallback;
}

string JsonString(const string json, const string key, const string fallback="")
{
   string needle = "\"" + key + "\"";
   int p = StringFind(json, needle);
   if(p < 0) return fallback;
   p = StringFind(json, ":", p + StringLen(needle));
   if(p < 0) return fallback;
   p++;
   int n = StringLen(json);
   while(p < n && (StringGetCharacter(json,p)==32 || StringGetCharacter(json,p)==9)) p++;
   if(p >= n || StringGetCharacter(json,p) != 34) return fallback;
   int e = StringFind(json, "\"", p + 1);
   if(e < 0) return fallback;
   return StringSubstr(json, p + 1, e - p - 1);
}

double JsonNumber(const string json, const string key, const double fallback=0.0)
{
   string needle = "\"" + key + "\"";
   int p = StringFind(json, needle);
   if(p < 0) return fallback;
   p = StringFind(json, ":", p + StringLen(needle));
   if(p < 0) return fallback;
   p++;
   int n = StringLen(json);
   while(p < n && (StringGetCharacter(json,p)==32 || StringGetCharacter(json,p)==9)) p++;
   int e = p;
   while(e < n)
   {
      ushort c = StringGetCharacter(json,e);
      if(c==44 || c==125 || c==93 || c==32 || c==10 || c==13) break;
      e++;
   }
   string value = StringSubstr(json,p,e-p);
   if(value == "null" || value == "") return fallback;
   return StringToDouble(value);
}

int EffectiveMaxOpenTrades(const string json)
{
   int bridge_max=(int)JsonNumber(json,"max_open_trades",1);
   bridge_max=MathMax(1,MathMin(5,bridge_max));
   int local_max=MathMax(1,MathMin(5,MaxOpenTrades));
   return MathMin(local_max,bridge_max);
}

double EffectiveRiskPercent(const string json)
{
   double value=JsonNumber(json,"risk_percent",RiskPercent);
   return MathMax(0.05,MathMin(5.0,value));
}

double EffectiveRewardRiskRatio(const string json)
{
   double value=JsonNumber(json,"reward_risk_ratio",RewardRiskRatio);
   return MathMax(0.5,MathMin(10.0,value));
}

string FactorObject(const string json, const string factor_name)
{
   string needle = "\"name\":\"" + factor_name + "\"";
   int p = StringFind(json, needle);
   if(p < 0)
   {
      needle = "\"name\": \"" + factor_name + "\"";
      p = StringFind(json, needle);
   }
   if(p < 0) return "";
   int start = p;
   while(start >= 0 && StringGetCharacter(json,start) != 123) start--;
   if(start < 0) return "";
   int depth = 0;
   for(int i=start; i<StringLen(json); i++)
   {
      ushort c = StringGetCharacter(json,i);
      if(c == 123) depth++;
      if(c == 125)
      {
         depth--;
         if(depth == 0) return StringSubstr(json,start,i-start+1);
      }
   }
   return "";
}

bool BuildSnapshotJson(string &payload)
{
   MqlTick tick;
   if(!SymbolInfoTick(TradeSymbol, tick) || tick.bid <= 0 || tick.ask <= 0)
      return false;

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int need = MathMax(60, SnapshotBars);
   int copied = CopyRates(TradeSymbol, AnalysisTimeframe, 1, need, rates);
   if(copied < 60)
      return false;

   double point = SymbolInfoDouble(TradeSymbol, SYMBOL_POINT);
   if(point <= 0) return false;
   long spread = SymbolInfoInteger(TradeSymbol, SYMBOL_SPREAD);

   double d1h = iHigh(TradeSymbol, PERIOD_D1, 1);
   double d1l = iLow(TradeSymbol, PERIOD_D1, 1);
   double d1c = iClose(TradeSymbol, PERIOD_D1, 1);

   payload = "{";
   payload += "\"symbol\":\"" + JsonEscape(TradeSymbol) + "\",";
   payload += "\"timeframe\":\"" + TfText() + "\",";
   payload += "\"bid\":" + DoubleToString(tick.bid, _Digits) + ",";
   payload += "\"ask\":" + DoubleToString(tick.ask, _Digits) + ",";
   payload += "\"point\":" + DoubleToString(point, 10) + ",";
   payload += "\"spread_points\":" + IntegerToString((int)spread) + ",";
   payload += "\"news_risk\":\"UNKNOWN\",";
   payload += "\"account_mode\":\"" + AccountModeText() + "\",";
   if(d1h > 0 && d1l > 0 && d1c > 0)
   {
      payload += "\"previous_day\":{";
      payload += "\"high\":" + DoubleToString(d1h,_Digits) + ",";
      payload += "\"low\":" + DoubleToString(d1l,_Digits) + ",";
      payload += "\"close\":" + DoubleToString(d1c,_Digits) + "},";
   }
   payload += "\"bars\":[";
   for(int i=copied-1; i>=0; i--)
   {
      payload += "{";
      payload += "\"time\":" + IntegerToString((int)rates[i].time) + ",";
      payload += "\"open\":" + DoubleToString(rates[i].open,_Digits) + ",";
      payload += "\"high\":" + DoubleToString(rates[i].high,_Digits) + ",";
      payload += "\"low\":" + DoubleToString(rates[i].low,_Digits) + ",";
      payload += "\"close\":" + DoubleToString(rates[i].close,_Digits) + ",";
      payload += "\"tick_volume\":" + IntegerToString((int)rates[i].tick_volume) + "}";
      if(i > 0) payload += ",";
   }
   payload += "]}";
   return true;
}

bool BuildHistorySyncJson(string &payload)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int requested = MathMax(200, HistorySyncBars);
   int copied = CopyRates(TradeSymbol, AnalysisTimeframe, 1, requested, rates);
   if(copied < 60)
      return false;

   double point = SymbolInfoDouble(TradeSymbol, SYMBOL_POINT);
   if(point <= 0) return false;

   payload = "{";
   payload += "\"symbol\":\"" + JsonEscape(TradeSymbol) + "\",";
   payload += "\"timeframe\":\"" + TfText() + "\",";
   payload += "\"point\":" + DoubleToString(point,10) + ",";
   payload += "\"bars\":[";
   for(int i=copied-1; i>=0; i--)
   {
      payload += "{";
      payload += "\"time\":" + IntegerToString((int)rates[i].time) + ",";
      payload += "\"broker_date\":\"" + BrokerDate(rates[i].time) + "\",";
      payload += "\"open\":" + DoubleToString(rates[i].open,_Digits) + ",";
      payload += "\"high\":" + DoubleToString(rates[i].high,_Digits) + ",";
      payload += "\"low\":" + DoubleToString(rates[i].low,_Digits) + ",";
      payload += "\"close\":" + DoubleToString(rates[i].close,_Digits) + ",";
      payload += "\"spread_points\":" + IntegerToString((int)rates[i].spread) + "}";
      if(i > 0) payload += ",";
   }
   payload += "]}";
   return true;
}

bool HttpPostJson(const string url, const string payload, string &response)
{
   char data[];
   char result[];
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";
   string response_headers;
   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(ArraySize(data) > 0) ArrayResize(data, ArraySize(data)-1);
   ResetLastError();
   int code = WebRequest("POST", url, headers, RequestTimeoutMs, data, result, response_headers);
   if(code < 0)
   {
      Print("MetaTraderAI WebRequest failed: ", GetLastError(), ". Add ", BridgeBaseUrl, " to Tools > Options > Expert Advisors > Allow WebRequest.");
      return false;
   }
   response = CharArrayToString(result, 0, -1, CP_UTF8);
   if(code < 200 || code >= 300)
   {
      Print("MetaTraderAI HTTP ", code, ": ", response);
      return false;
   }
   return true;
}

bool SyncHistoryNow()
{
   string payload;
   if(!BuildHistorySyncJson(payload))
   {
      HistorySyncState = "WAIT_DATA";
      Print("MetaTraderAI history sync: not enough M15 history yet; retrying soon.");
      return false;
   }
   string response;
   if(!HttpPostJson(BridgeBaseUrl+"/history/sync", payload, response))
   {
      HistorySyncState = "FAILED";
      Print("MetaTraderAI history sync failed; retrying soon.");
      return false;
   }
   HistorySyncState = "SYNCED";
   Print("MetaTraderAI history synced to Bridge: ", response);
   return true;
}

void EnsurePanelObject(const string name, const int x, const int y, const int font_size=12)
{
   string id = PanelPrefix + name;
   if(ObjectFind(0,id) < 0)
      ObjectCreate(0,id,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,PanelLeft + x);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,PanelTop + y);
   ObjectSetInteger(0,id,OBJPROP_FONTSIZE,font_size);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
   ObjectSetString(0,id,OBJPROP_FONT,"DejaVu Sans Mono");
}

void SetPanelText(const string name, const string text, const int x, const int y, color clr=clrWhite, const int font_size=12)
{
   EnsurePanelObject(name,x,y,font_size);
   string id = PanelPrefix + name;
   ObjectSetInteger(0,id,OBJPROP_COLOR,clr);
   ObjectSetString(0,id,OBJPROP_TEXT,text);
}

void DrawPanelBackground()
{
   string id = PanelPrefix + "BG";
   if(ObjectFind(0,id) < 0)
      ObjectCreate(0,id,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,id,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,id,OBJPROP_XDISTANCE,PanelLeft);
   ObjectSetInteger(0,id,OBJPROP_YDISTANCE,PanelTop);
   ObjectSetInteger(0,id,OBJPROP_XSIZE,PanelWidth);
   ObjectSetInteger(0,id,OBJPROP_YSIZE,PanelHeight);
   ObjectSetInteger(0,id,OBJPROP_BGCOLOR,C'22,26,33');
   ObjectSetInteger(0,id,OBJPROP_BORDER_COLOR,C'70,78,90');
   ObjectSetInteger(0,id,OBJPROP_BACK,false);
   ObjectSetInteger(0,id,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,id,OBJPROP_HIDDEN,true);
}

string PassMark(const bool passed) { return passed ? "PASS" : "FAIL"; }
color PassColor(const bool passed) { return passed ? clrLime : clrTomato; }

void DrawDecisionPanel(const string json)
{
   DrawPanelBackground();
   string candidate = JsonString(json,"candidate","WAIT");
   string decision = JsonString(json,"decision","WAIT");
   double buy_score = JsonNumber(json,"buy_score",0);
   double sell_score = JsonNumber(json,"sell_score",0);
   int passed_count = (int)JsonNumber(json,"passed_count",0);
   int min_pass = (int)JsonNumber(json,"min_pass_count",4);
   int bridge_max = MathMax(1,MathMin(5,(int)JsonNumber(json,"max_open_trades",1)));
   int effective_max = EffectiveMaxOpenTrades(json);
   double effective_risk = EffectiveRiskPercent(json);
   double effective_rr = EffectiveRewardRiskRatio(json);
   bool bridge_allowed = JsonBool(json,"trade_allowed",false);
   bool market_open = MarketSessionOpenNow();
   bool algo_ready = TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) && MQLInfoInteger(MQL_TRADE_ALLOWED);
   bool demo_ready = !DemoOnly || AccountModeText() == "DEMO";
   bool local_ready = market_open && algo_ready && demo_ready;
   bool execution_ready = bridge_allowed && local_ready;

   color decision_color = decision == "BUY" ? clrLime : decision == "SELL" ? clrTomato : clrGold;
   SetPanelText("TITLE","META TRADER AI v2 | SIX-FACTOR DECISION TREE",14,12,clrWhite,PanelFontSize+1);
   SetPanelText("HEAD",TradeSymbol+" | "+TfText()+" | candidate="+candidate+" | FINAL="+decision,14,40,decision_color,PanelFontSize);
   SetPanelText("SCORES","BUY "+DoubleToString(buy_score,1)+" | SELL "+DoubleToString(sell_score,1)+" | passed "+IntegerToString(passed_count)+"/6 | need "+IntegerToString(min_pass)+"/6",14,65,clrWhite,PanelFontSize);

   string names[6] = {"dynamic_levels","static_levels","fibonacci","patterns","pivots","divergence"};
   string labels[6] = {"Dynamic levels","Static / OrderBlock","Fibonacci","Patterns / Harmonic","Pivots","Divergence / Momentum"};
   for(int i=0;i<6;i++)
   {
      string obj = FactorObject(json,names[i]);
      double score = JsonNumber(obj,"candidate_score",0);
      double min_score = JsonNumber(obj,"min_score",0);
      bool passed = JsonBool(obj,"passed",false);
      string prefix = (i == 5 ? "`- " : "|- ");
      string line = prefix + labels[i] + "  " + DoubleToString(score,1) + "/" + DoubleToString(min_score,0) + "  " + PassMark(passed);
      SetPanelText("F"+IntegerToString(i),line,24,96+i*35,PassColor(passed),PanelFontSize);
   }

   string perf = "PERF: trades="+IntegerToString((int)JsonNumber(json,"trades",0))+
                 "  E="+DoubleToString(JsonNumber(json,"expectancy_r",0),2)+"R"+
                 "  WR="+DoubleToString(JsonNumber(json,"win_rate",0),1)+"%"+
                 "  DD="+DoubleToString(JsonNumber(json,"max_drawdown_r",0),2)+"R"+
                 "  trend="+JsonString(json,"trend","COLLECTING");
   SetPanelText("PERF",perf,14,320,clrAqua,PanelFontSize);

   string status;
   color status_color;
   if(execution_ready)
   {
      status = "EXECUTION: ARMED - signal may open a DEMO position";
      status_color = clrLime;
   }
   else if(bridge_allowed && !market_open)
   {
      status = "EXECUTION: BLOCKED - MARKET CLOSED";
      status_color = clrTomato;
   }
   else if(bridge_allowed && !algo_ready)
   {
      status = "EXECUTION: BLOCKED - ALGO TRADING DISABLED";
      status_color = clrTomato;
   }
   else
   {
      status = "EXECUTION: BLOCKED / WAIT";
      status_color = clrGold;
   }
   SetPanelText("EXEC",status,14,350,status_color,PanelFontSize);

   string blocker=JsonString(json,"primary_blocker","");
   if(bridge_allowed && !market_open) blocker="market closed for "+TradeSymbol;
   else if(bridge_allowed && !algo_ready) blocker="Algo Trading is disabled in terminal or EA";
   else if(bridge_allowed && !demo_ready) blocker="DemoOnly=true but account is not DEMO";
   SetPanelText("WHY",blocker=="" ? "WHY: all decision + local execution gates passed" : "WHY: "+blocker,14,375,blocker=="" ? clrLime : clrTomato,PanelFontSize-1);
   SetPanelText("CFG","Thresholds + replay: Bridge /control | History="+HistorySyncState,14,400,HistorySyncState=="SYNCED"?clrSilver:clrGold,PanelFontSize-1);
   SetPanelText("SAFE","Session="+(market_open?"OPEN":"CLOSED")+" | MaxOpen="+IntegerToString(effective_max)+" (B"+IntegerToString(bridge_max)+"/L"+IntegerToString(MaxOpenTrades)+") | risk="+DoubleToString(effective_risk,2)+"% | RR=1:"+DoubleToString(effective_rr,1),14,425,market_open?clrSilver:clrTomato,PanelFontSize-1);
   ChartRedraw();
}

int ManagedOpenPositions()
{
   int count=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0 || !PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL)!=TradeSymbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      count++;
   }
   return count;
}

double NormalizeVolumeDown(double volume)
{
   double minv = SymbolInfoDouble(TradeSymbol,SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(TradeSymbol,SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(TradeSymbol,SYMBOL_VOLUME_STEP);
   if(step <= 0 || maxv <= 0) return 0.0;
   volume = MathMin(volume,maxv);
   volume = MathFloor(volume/step + 1e-9)*step;
   if(volume < minv) return 0.0;
   int digits = 2;
   if(step < 0.01) digits=3;
   if(step < 0.001) digits=4;
   return NormalizeDouble(volume,digits);
}

bool BuildTradePlan(const string side, const double risk_percent, const double reward_risk_ratio, double &stop, double &target, double &volume, double &risk_money)
{
   MqlTick tick;
   if(!SymbolInfoTick(TradeSymbol,tick)) return false;
   double atr_buf[];
   ArraySetAsSeries(atr_buf,true);
   if(CopyBuffer(AtrHandle,0,1,1,atr_buf) < 1 || atr_buf[0] <= 0) return false;
   double point = SymbolInfoDouble(TradeSymbol,SYMBOL_POINT);
   if(point <= 0) return false;
   double entry = side == "BUY" ? tick.ask : tick.bid;
   double stop_points = MathMax((double)MinStopPoints, atr_buf[0]*AtrMultiplier/point);
   if(MaxStopPoints > 0) stop_points = MathMin(stop_points,(double)MaxStopPoints);
   long broker_level = SymbolInfoInteger(TradeSymbol,SYMBOL_TRADE_STOPS_LEVEL);
   stop_points = MathMax(stop_points,(double)broker_level+5.0);
   int digits = (int)SymbolInfoInteger(TradeSymbol,SYMBOL_DIGITS);
   if(side == "BUY")
   {
      stop = NormalizeDouble(entry-stop_points*point,digits);
      target = NormalizeDouble(entry+stop_points*reward_risk_ratio*point,digits);
   }
   else
   {
      stop = NormalizeDouble(entry+stop_points*point,digits);
      target = NormalizeDouble(entry-stop_points*reward_risk_ratio*point,digits);
   }
   ENUM_ORDER_TYPE type = side == "BUY" ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   double one_lot_profit=0.0;
   if(!OrderCalcProfit(type,TradeSymbol,1.0,entry,stop,one_lot_profit)) return false;
   double one_lot_loss=MathAbs(one_lot_profit);
   if(one_lot_loss<=0) return false;
   double target_risk=AccountInfoDouble(ACCOUNT_EQUITY)*risk_percent/100.0;
   volume=NormalizeVolumeDown(target_risk/one_lot_loss);
   if(volume<=0) return false;
   double actual_loss=0.0;
   if(!OrderCalcProfit(type,TradeSymbol,volume,entry,stop,actual_loss)) return false;
   risk_money=MathAbs(actual_loss);
   return risk_money>0;
}

void MaybeExecute(const string json)
{
   if(!EnableAutoTrading) return;
   if(DemoOnly && AccountModeText() != "DEMO") return;
   if(!MarketSessionOpenNow()) return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
   if(!JsonBool(json,"trade_allowed",false)) return;
   string side=JsonString(json,"decision","WAIT");
   if(side!="BUY" && side!="SELL") return;
   string signal_id=JsonString(json,"signal_id","");
   if(signal_id=="" || signal_id==LastExecutedSignalId) return;
   datetime completed_bar=iTime(TradeSymbol,AnalysisTimeframe,1);
   if(completed_bar<=0 || completed_bar<=LastExecutedBarTime) return;
   int effective_max=EffectiveMaxOpenTrades(json);
   if(ManagedOpenPositions() >= effective_max) return;
   double effective_risk=EffectiveRiskPercent(json);
   double effective_rr=EffectiveRewardRiskRatio(json);

   double stop=0,target=0,volume=0,risk_money=0;
   if(!BuildTradePlan(side,effective_risk,effective_rr,stop,target,volume,risk_money))
   {
      Print("MetaTraderAI: trade plan failed; no order sent.");
      return;
   }

   Trade.SetExpertMagicNumber(MagicNumber);
   Trade.SetDeviationInPoints(SlippagePoints);
   Trade.SetTypeFillingBySymbol(TradeSymbol);
   Trade.SetAsyncMode(false);
   bool ok = side=="BUY"
      ? Trade.Buy(volume,TradeSymbol,0.0,stop,target,"MTAI6 "+signal_id)
      : Trade.Sell(volume,TradeSymbol,0.0,stop,target,"MTAI6 "+signal_id);
   if(!ok)
   {
      Print("MetaTraderAI order failed: ",Trade.ResultRetcode()," ",Trade.ResultRetcodeDescription());
      return;
   }
   LastExecutedSignalId=signal_id;
   LastExecutedBarTime=completed_bar;
   GlobalVariableSet(ExecutedBarGlobalName(),(double)LastExecutedBarTime);

   ulong entry_deal=Trade.ResultDeal();
   if(entry_deal>0 && HistoryDealSelect(entry_deal))
   {
      long position_id=(long)HistoryDealGetInteger(entry_deal,DEAL_POSITION_ID);
      if(position_id>0)
         GlobalVariableSet(PositionRiskGlobalName(position_id),risk_money);
   }
   Print("MetaTraderAI OPENED ",side," signal=",signal_id," volume=",DoubleToString(volume,3)," risk=$",DoubleToString(risk_money,2)," riskPct=",DoubleToString(effective_risk,2)," RR=",DoubleToString(effective_rr,1)," maxOpen=",effective_max);
}

string EntrySignalForPosition(const long position_id)
{
   if(position_id<=0 || !HistorySelectByPosition((ulong)position_id)) return "";
   int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
   {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      if((ulong)HistoryDealGetInteger(ticket,DEAL_MAGIC)!=MagicNumber) continue;
      string comment=HistoryDealGetString(ticket,DEAL_COMMENT);
      if(StringFind(comment,"MTAI6 ")==0)
         return StringSubstr(comment,6);
   }
   return "";
}

void RecordClosedDeal(const ulong deal_ticket)
{
   if(deal_ticket==0 || !HistoryDealSelect(deal_ticket)) return;
   if(HistoryDealGetString(deal_ticket,DEAL_SYMBOL)!=TradeSymbol) return;
   if((ulong)HistoryDealGetInteger(deal_ticket,DEAL_MAGIC)!=MagicNumber) return;
   ENUM_DEAL_ENTRY entry=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal_ticket,DEAL_ENTRY);
   if(entry!=DEAL_ENTRY_OUT && entry!=DEAL_ENTRY_OUT_BY) return;

   double pnl=HistoryDealGetDouble(deal_ticket,DEAL_PROFIT)+HistoryDealGetDouble(deal_ticket,DEAL_SWAP)+HistoryDealGetDouble(deal_ticket,DEAL_COMMISSION);
   ENUM_DEAL_TYPE type=(ENUM_DEAL_TYPE)HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
   long position_id=(long)HistoryDealGetInteger(deal_ticket,DEAL_POSITION_ID);
   string risk_name=PositionRiskGlobalName(position_id);
   double initial_risk=GlobalVariableCheck(risk_name) ? GlobalVariableGet(risk_name) : 0.0;
   string signal_id=EntrySignalForPosition(position_id);
   if(initial_risk<=0 || signal_id=="")
   {
      Print("MetaTraderAI close outcome could not be linked to entry position_id=",position_id);
      return;
   }
   double r=pnl/initial_risk;
   string closed_side = type==DEAL_TYPE_SELL ? "BUY" : "SELL";
   string payload="{";
   payload+="\"signal_id\":\""+JsonEscape(signal_id)+"\",";
   payload+="\"symbol\":\""+JsonEscape(TradeSymbol)+"\",";
   payload+="\"side\":\""+closed_side+"\",";
   payload+="\"pnl_money\":"+DoubleToString(pnl,2)+",";
   payload+="\"r_multiple\":"+DoubleToString(r,6)+"}";
   string response;
   if(HttpPostJson(BridgeBaseUrl+"/performance/trades",payload,response))
      Print("MetaTraderAI recorded outcome: ",DoubleToString(r,2),"R | signal=",signal_id," | ",response);
   GlobalVariableDel(risk_name);
}

void AnalyzeNow()
{
   string payload;
   if(!BuildSnapshotJson(payload))
   {
      SetPanelText("ERROR","Waiting for enough market data...",14,40,clrGold,PanelFontSize);
      return;
   }
   string response;
   if(!HttpPostJson(BridgeBaseUrl+"/analyze",payload,response))
   {
      DrawPanelBackground();
      SetPanelText("TITLE","META TRADER AI v2 | BRIDGE OFFLINE",14,12,clrTomato,PanelFontSize+1);
      SetPanelText("ERROR","Check Python bridge and MT5 WebRequest allow-list: "+BridgeBaseUrl,14,48,clrGold,PanelFontSize);
      return;
   }
   DrawDecisionPanel(response);
   MaybeExecute(response);
}

int OnInit()
{
   if(!SymbolSelect(TradeSymbol,true))
      return INIT_FAILED;
   AtrHandle=iATR(TradeSymbol,AnalysisTimeframe,AtrPeriod);
   if(AtrHandle==INVALID_HANDLE)
      return INIT_FAILED;
   if(GlobalVariableCheck(ExecutedBarGlobalName()))
      LastExecutedBarTime=(datetime)GlobalVariableGet(ExecutedBarGlobalName());
   EventSetTimer(1);
   DrawPanelBackground();
   SetPanelText("TITLE","META TRADER AI v2 | STARTING...",14,12,clrWhite,PanelFontSize+1);
   return INIT_SUCCEEDED;
}

void OnTimer()
{
   ulong now=GetTickCount64();

   ulong history_interval_ms = (ulong)MathMax(1, HistoryInitialRetrySeconds) * 1000;
   if(LastHistorySyncMs > 0)
      history_interval_ms = (ulong)MathMax(60, HistorySyncSeconds) * 1000;

   ulong history_anchor_ms = LastHistorySyncMs > 0 ? LastHistorySyncMs : LastHistoryAttemptMs;
   if(LastHistoryAttemptMs == 0 || now-history_anchor_ms >= history_interval_ms)
   {
      LastHistoryAttemptMs = now;
      if(SyncHistoryNow())
         LastHistorySyncMs = now;
   }

   if(now-LastSignalCheckMs < (ulong)MathMax(1,SignalSeconds)*1000) return;
   LastSignalCheckMs=now;
   AnalyzeNow();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
{
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
      RecordClosedDeal(trans.deal);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(AtrHandle!=INVALID_HANDLE) IndicatorRelease(AtrHandle);
   ObjectsDeleteAll(0,PanelPrefix);
}
