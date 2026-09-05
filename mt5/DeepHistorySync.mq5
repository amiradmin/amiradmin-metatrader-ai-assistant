#property strict
#property script_show_inputs
#property version   "1.00"
#property description "One-shot chunked MT5 history uploader for multi-year MetaTrader AI training"

input string TradeSymbol = "XAUUSD_o";
input string BridgeBaseUrl = "http://127.0.0.1:8000";
input ENUM_TIMEFRAMES HistoryTimeframe = PERIOD_M15;
input int ChunkBars = 2500;
input int MaxBars = 0;                    // 0 = keep going as far back as the broker/terminal provides
input int RequestTimeoutMs = 20000;
input int BetweenChunksMs = 250;
input int RetryDelayMs = 1500;
input int MaxEmptyRetries = 5;
input int MaxHttpRetries = 5;

string TfText()
{
   if(HistoryTimeframe == PERIOD_M1) return "M1";
   if(HistoryTimeframe == PERIOD_M5) return "M5";
   if(HistoryTimeframe == PERIOD_M15) return "M15";
   if(HistoryTimeframe == PERIOD_M30) return "M30";
   if(HistoryTimeframe == PERIOD_H1) return "H1";
   if(HistoryTimeframe == PERIOD_H4) return "H4";
   if(HistoryTimeframe == PERIOD_D1) return "D1";
   return EnumToString(HistoryTimeframe);
}

string BrokerDate(const datetime value)
{
   MqlDateTime parts;
   TimeToStruct(value, parts);
   return StringFormat("%04d-%02d-%02d", parts.year, parts.mon, parts.day);
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   return value;
}

bool HttpPostJson(const string url, const string payload, string &response)
{
   char data[];
   char result[];
   string headers = "Content-Type: application/json\r\nAccept: application/json\r\n";
   string response_headers;

   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   if(ArraySize(data) > 0)
      ArrayResize(data, ArraySize(data) - 1);

   ResetLastError();
   int code = WebRequest("POST", url, headers, RequestTimeoutMs, data, result, response_headers);
   if(code < 0)
   {
      Print("DeepHistorySync WebRequest failed: ", GetLastError(),
            ". Add ", BridgeBaseUrl,
            " to Tools > Options > Expert Advisors > Allow WebRequest.");
      return false;
   }

   response = CharArrayToString(result, 0, -1, CP_UTF8);
   if(code < 200 || code >= 300)
   {
      Print("DeepHistorySync HTTP ", code, ": ", response);
      return false;
   }
   return true;
}

bool BuildChunkJson(
   const int start_pos,
   const int requested,
   string &payload,
   int &copied,
   datetime &oldest_time,
   datetime &newest_time
)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);

   ResetLastError();
   copied = CopyRates(TradeSymbol, HistoryTimeframe, start_pos, requested, rates);
   if(copied <= 0)
      return false;

   double point = SymbolInfoDouble(TradeSymbol, SYMBOL_POINT);
   if(point <= 0)
      return false;

   newest_time = rates[0].time;
   oldest_time = rates[copied - 1].time;

   payload = "{";
   payload += "\"symbol\":\"" + JsonEscape(TradeSymbol) + "\",";
   payload += "\"timeframe\":\"" + TfText() + "\",";
   payload += "\"point\":" + DoubleToString(point, 10) + ",";
   payload += "\"bars\":[";

   // Send oldest -> newest inside each chunk. The Bridge upserts by timestamp,
   // so chunks can overlap safely and can be re-run without duplicating bars.
   for(int i = copied - 1; i >= 0; i--)
   {
      payload += "{";
      payload += "\"time\":" + IntegerToString((int)rates[i].time) + ",";
      payload += "\"broker_date\":\"" + BrokerDate(rates[i].time) + "\",";
      payload += "\"open\":" + DoubleToString(rates[i].open, _Digits) + ",";
      payload += "\"high\":" + DoubleToString(rates[i].high, _Digits) + ",";
      payload += "\"low\":" + DoubleToString(rates[i].low, _Digits) + ",";
      payload += "\"close\":" + DoubleToString(rates[i].close, _Digits) + ",";
      payload += "\"spread_points\":" + IntegerToString((int)rates[i].spread) + "}";
      if(i > 0)
         payload += ",";
   }

   payload += "]}";
   return true;
}

void ShowProgress(
   const int chunks,
   const int total_sent,
   const int next_offset,
   const datetime oldest_time,
   const string state
)
{
   string oldest = oldest_time > 0 ? BrokerDate(oldest_time) : "-";
   Comment(
      "MetaTrader AI - Deep History Sync\n",
      "State: ", state, "\n",
      "Symbol / TF: ", TradeSymbol, " / ", TfText(), "\n",
      "Chunks sent: ", chunks, "\n",
      "Bars sent this run: ", total_sent, "\n",
      "Oldest bar reached: ", oldest, "\n",
      "Next MT5 offset: ", next_offset, "\n",
      "MaxBars: ", (MaxBars <= 0 ? "BROKER MAX" : IntegerToString(MaxBars))
   );
}

void OnStart()
{
   if(!SymbolSelect(TradeSymbol, true))
   {
      Alert("DeepHistorySync: could not select symbol ", TradeSymbol);
      return;
   }

   int chunk_size = MathMax(200, ChunkBars);
   int offset = 1; // Skip the currently-forming bar; sync completed bars only.
   int total_sent = 0;
   int chunks = 0;
   int empty_retries = 0;
   int http_retries = 0;
   datetime oldest_reached = 0;

   Print("DeepHistorySync started for ", TradeSymbol, " ", TfText(),
         ". ChunkBars=", chunk_size,
         ", MaxBars=", MaxBars,
         " (0 means broker/terminal maximum available history).");

   ShowProgress(chunks, total_sent, offset, oldest_reached, "STARTING");

   while(!IsStopped())
   {
      int requested = chunk_size;
      if(MaxBars > 0)
      {
         int remaining = MaxBars - total_sent;
         if(remaining <= 0)
            break;
         requested = MathMin(requested, remaining);
      }

      string payload;
      int copied = 0;
      datetime chunk_oldest = 0;
      datetime chunk_newest = 0;

      if(!BuildChunkJson(offset, requested, payload, copied, chunk_oldest, chunk_newest))
      {
         int err = GetLastError();
         empty_retries++;
         ShowProgress(chunks, total_sent, offset, oldest_reached, "WAITING FOR OLDER DATA");
         Print("DeepHistorySync CopyRates returned no data at offset ", offset,
               ", attempt ", empty_retries, "/", MaxEmptyRetries,
               ", error=", err, ". Waiting for terminal/broker history download...");

         if(empty_retries >= MathMax(1, MaxEmptyRetries))
         {
            Print("DeepHistorySync reached the oldest history currently available from MT5/broker at offset ", offset, ".");
            break;
         }
         Sleep(MathMax(250, RetryDelayMs));
         continue;
      }

      empty_retries = 0;
      string response;
      if(!HttpPostJson(BridgeBaseUrl + "/history/sync", payload, response))
      {
         http_retries++;
         ShowProgress(chunks, total_sent, offset, oldest_reached, "BRIDGE RETRY");
         if(http_retries >= MathMax(1, MaxHttpRetries))
         {
            Alert("DeepHistorySync stopped after repeated Bridge/WebRequest failures. Check the Bridge and WebRequest allow-list, then run the script again.");
            return;
         }
         Sleep(MathMax(250, RetryDelayMs));
         continue;
      }

      http_retries = 0;
      chunks++;
      total_sent += copied;
      offset += copied;
      oldest_reached = chunk_oldest;

      Print("DeepHistorySync chunk ", chunks,
            " uploaded: ", copied,
            " bars | ", BrokerDate(chunk_oldest),
            " -> ", BrokerDate(chunk_newest),
            " | total this run=", total_sent,
            " | Bridge=", response);
      ShowProgress(chunks, total_sent, offset, oldest_reached, "SYNCING");

      // A partial chunk often means we are close to the oldest available data.
      // We still advance and try again because MT5 may asynchronously download
      // another older block from the broker on the next CopyRates call.
      if(copied < requested)
         Sleep(MathMax(500, RetryDelayMs));
      else
         Sleep(MathMax(0, BetweenChunksMs));
   }

   ShowProgress(chunks, total_sent, offset, oldest_reached, "COMPLETE");
   string final_message = "DeepHistorySync complete. Uploaded " + IntegerToString(total_sent) +
                          " bars in " + IntegerToString(chunks) +
                          " chunks. Oldest reached: " +
                          (oldest_reached > 0 ? BrokerDate(oldest_reached) : "unknown") +
                          ". Refresh /train or /control to see the expanded date range.";
   Print(final_message);
   Alert(final_message);
}
