//+------------------------------------------------------------------+
//|  TradingAgentsEA.mq5                                             |
//|  Polls ~/mt5_bridge/order.json every 2s, executes the trade,    |
//|  then writes ~/mt5_bridge/status.json.                           |
//|                                                                  |
//|  Setup:                                                          |
//|    1. Copy this file to MT5 MQL5/Experts/ folder                |
//|    2. Compile (F7) in MetaEditor                                 |
//|    3. Attach to any chart, enable "Allow live trading"           |
//|    4. Set BRIDGE_PATH to the same path as MT5_BRIDGE_PATH env   |
//+------------------------------------------------------------------+
#property copyright "TradingAgents"
#property version   "1.00"
#property strict

input string BRIDGE_PATH = "/Users/user/mt5_bridge"; // Full path to bridge folder (Mac: /Users/<you>/mt5_bridge  Windows: C:\Users\<you>\mt5_bridge)

//--- file paths
string ORDER_FILE;
string STATUS_FILE;

int OnInit()
{
   ORDER_FILE  = BRIDGE_PATH + "\\order.json";
   STATUS_FILE = BRIDGE_PATH + "\\status.json";
   EventSetMillisecondTimer(2000);
   Print("TradingAgentsEA started. Watching: ", ORDER_FILE);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   if(!FileIsExist(ORDER_FILE, FILE_COMMON))
      return;

   // Read order.json
   int handle = FileOpen(ORDER_FILE, FILE_READ|FILE_TXT|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return;

   string raw = "";
   while(!FileIsEnding(handle))
      raw += FileReadString(handle);
   FileClose(handle);

   // Skip if already processed
   if(StringFind(raw, "\"processed\": true") >= 0 ||
      StringFind(raw, "\"processed\":true")  >= 0)
      return;

   // --- Parse fields ---
   string action = JsonGetString(raw, "action");
   string pair   = JsonGetString(raw, "pair");
   double lots   = StringToDouble(JsonGetString(raw, "lots"));
   int    sl_p   = (int)StringToInteger(JsonGetString(raw, "sl_pips"));
   int    tp_p   = (int)StringToInteger(JsonGetString(raw, "tp_pips"));

   if(action == "CLOSE")
   {
      long ticket = StringToInteger(JsonGetString(raw, "order_id"));
      ClosePosition(ticket);
      return;
   }

   if(pair == "" || lots <= 0)
   {
      WriteStatus("{\"status\":\"error\",\"message\":\"Invalid order fields\"}");
      return;
   }

   // --- Get current price ---
   MqlTick tick;
   if(!SymbolInfoTick(pair, tick))
   {
      WriteStatus("{\"status\":\"error\",\"message\":\"Cannot get tick for " + pair + "\"}");
      return;
   }

   bool   isBuy     = (action == "LONG");
   double pipSize   = (StringFind(pair, "JPY") >= 0) ? 0.01 : 0.0001;
   double price     = isBuy ? tick.ask : tick.bid;
   double sl        = isBuy ? price - sl_p * pipSize : price + sl_p * pipSize;
   double tp_price  = isBuy ? price + tp_p * pipSize : price - tp_p * pipSize;

   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = pair;
   req.volume    = lots;
   req.type      = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price     = price;
   req.sl        = NormalizeDouble(sl, (int)SymbolInfoInteger(pair, SYMBOL_DIGITS));
   req.tp        = NormalizeDouble(tp_price, (int)SymbolInfoInteger(pair, SYMBOL_DIGITS));
   req.deviation = 10;
   req.magic     = 20260101;
   req.comment   = "TradingAgents";
   req.type_time = ORDER_TIME_GTC;
   req.type_filling = ORDER_FILLING_IOC;

   if(!OrderSend(req, res))
   {
      WriteStatus("{\"status\":\"error\",\"message\":\"OrderSend failed: " + IntegerToString(res.retcode) + "\"}");
      return;
   }

   // Mark order as processed
   MarkProcessed(raw);

   // Write status.json
   string status = "{\"status\":\"filled\",\"order_id\":" + IntegerToString(res.order) +
                   ",\"open_price\":" + DoubleToString(res.price, 5) +
                   ",\"timestamp\":\"" + TimeToString(TimeCurrent()) + "\"}";
   WriteStatus(status);
   Print("Order filled: ", pair, " ", action, " @ ", res.price);
}

void ClosePosition(long ticket)
{
   if(!PositionSelectByTicket(ticket))
   {
      WriteStatus("{\"status\":\"error\",\"message\":\"Position not found\"}");
      return;
   }
   string sym   = PositionGetString(POSITION_SYMBOL);
   double vol   = PositionGetDouble(POSITION_VOLUME);
   long   ptype = PositionGetInteger(POSITION_TYPE);

   MqlTick tick;
   SymbolInfoTick(sym, tick);
   double price = (ptype == POSITION_TYPE_BUY) ? tick.bid : tick.ask;

   MqlTradeRequest req = {};
   MqlTradeResult  res = {};
   req.action   = TRADE_ACTION_DEAL;
   req.symbol   = sym;
   req.volume   = vol;
   req.type     = (ptype == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.position = ticket;
   req.price    = price;
   req.deviation = 10;
   req.magic    = 20260101;
   req.comment  = "Close:TradingAgents";
   req.type_time    = ORDER_TIME_GTC;
   req.type_filling = ORDER_FILLING_IOC;

   if(OrderSend(req, res))
   {
      double profit = PositionGetDouble(POSITION_PROFIT);
      string status = "{\"status\":\"closed\",\"close_price\":" + DoubleToString(price, 5) +
                      ",\"pips\":0,\"profit\":" + DoubleToString(profit, 2) + "}";
      WriteStatus(status);
   }
   else
      WriteStatus("{\"status\":\"error\",\"message\":\"Close failed: " + IntegerToString(res.retcode) + "\"}");
}

void WriteStatus(string content)
{
   int h = FileOpen(STATUS_FILE, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      FileWriteString(h, content);
      FileClose(h);
   }
}

void MarkProcessed(string original)
{
   string updated = original;
   StringReplace(updated, "\"processed\": false", "\"processed\": true");
   StringReplace(updated, "\"processed\":false",  "\"processed\":true");
   int h = FileOpen(ORDER_FILE, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(h != INVALID_HANDLE)
   {
      FileWriteString(h, updated);
      FileClose(h);
   }
}

string JsonGetString(string json, string key)
{
   string search = "\"" + key + "\"";
   int pos = StringFind(json, search);
   if(pos < 0) return "";
   pos += StringLen(search);
   // skip whitespace and colon
   while(pos < StringLen(json) && (StringGetCharacter(json, pos) == ' ' || StringGetCharacter(json, pos) == ':'))
      pos++;
   if(pos >= StringLen(json)) return "";
   bool isString = StringGetCharacter(json, pos) == '"';
   if(isString) pos++;
   string result = "";
   while(pos < StringLen(json))
   {
      ushort c = StringGetCharacter(json, pos);
      if(isString && c == '"') break;
      if(!isString && (c == ',' || c == '}' || c == ' ' || c == '\n' || c == '\r')) break;
      result += ShortToString(c);
      pos++;
   }
   return result;
}
