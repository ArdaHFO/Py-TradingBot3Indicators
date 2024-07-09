import ccxt
import pandas as pd
import numpy as np
pd.set_option('display.max_rows', None)
import warnings
warnings.filterwarnings('ignore')
import datetime

# Import our secret.py file
import secret
# Import our supertrend.py file
import supertrend as indicators

ASSET_NAME = 'BTC-PERP'
TIMEFRAME = '5m'
FETCHING_LIMIT = 1500
TRADE_SIZE = 0.0004 # ~ 10$ worth of Bitcoin right now

# Initiate our ccxt connection
exchange = ccxt.ftx({
    "apiKey": secret.PUBLIC_KEY,
    "secret": secret.SECRET_KEY
})

def in_position():
    for position in exchange.fetchPositions():
        if float(position['info']['size']) > 0:
            return True
    return False

def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr

def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()

    return atr

def supertrend(df, period=10, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
        
    return df

def add_indicators(df):
    # Bollinger Bands
    period_bb = 20
    df['midband'] = df['close'].rolling(window=period_bb).mean()
    df['stddev'] = df['close'].rolling(window=period_bb).std()
    df['upperband_bb'] = df['midband'] + 2 * df['stddev']
    df['lowerband_bb'] = df['midband'] - 2 * df['stddev']

    # Exponential Weighted Moving Average (EWMA)
    span_ewma = 12
    df['ewma'] = df['close'].ewm(span=span_ewma, adjust=False).mean()

    # Exponential Moving Average (EMA)
    ema_period = 10
    df['ema'] = df['close'].ewm(span=ema_period, adjust=False).mean()

    return df

def execute(df):
    in_uptrend = df['in_uptrend'][len(df['in_uptrend']) - 1]
    curr_datetime = str(df['timestamp'][len(df['timestamp']) - 1])
    curr_close = df['close'][len(df['close']) - 1]

    # Bollinger Bands Strategy
    if not in_position() and df['close'].iloc[-1] < df['lowerband_bb'].iloc[-1]:
        exchange.createOrder(ASSET_NAME, 'market', 'buy', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' bought at price ' + str(curr_close) + ' (Bollinger Bands Buy Signal)\n')
    elif in_position() and df['close'].iloc[-1] > df['upperband_bb'].iloc[-1]:
        exchange.createOrder(ASSET_NAME, 'market', 'sell', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' sold at price ' + str(curr_close) + ' (Bollinger Bands Sell Signal)\n')

    # EWMA Strategy
    if not in_position() and df['close'].iloc[-1] > df['ewma'].iloc[-1] and df['close'].iloc[-2] <= df['ewma'].iloc[-2]:
        exchange.createOrder(ASSET_NAME, 'market', 'buy', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' bought at price ' + str(curr_close) + ' (EWMA Buy Signal)\n')
    elif in_position() and df['close'].iloc[-1] < df['ewma'].iloc[-1] and df['close'].iloc[-2] >= df['ewma'].iloc[-2]:
        exchange.createOrder(ASSET_NAME, 'market', 'sell', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' sold at price ' + str(curr_close) + ' (EWMA Sell Signal)\n')

    # EMA Strategy
    if not in_position() and df['close'].iloc[-1] > df['ema'].iloc[-1] and df['close'].iloc[-2] <= df['ema'].iloc[-2]:
        exchange.createOrder(ASSET_NAME, 'market', 'buy', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' bought at price ' + str(curr_close) + ' (EMA Buy Signal)\n')
    elif in_position() and df['close'].iloc[-1] < df['ema'].iloc[-1] and df['close'].iloc[-2] >= df['ema'].iloc[-2]:
        exchange.createOrder(ASSET_NAME, 'market', 'sell', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' sold at price ' + str(curr_close) + ' (EMA Sell Signal)\n')

    # Supertrend Strategy
    if not in_position() and in_uptrend:
        exchange.createOrder(ASSET_NAME, 'market', 'buy', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' bought at price ' + str(curr_close) + ' (Supertrend Buy Signal)\n')
    elif in_position() and not in_uptrend:
        exchange.createOrder(ASSET_NAME, 'market', 'sell', TRADE_SIZE)
        print(curr_datetime + ', ' + ASSET_NAME + ' sold at price ' + str(curr_close) + ' (Supertrend Sell Signal)\n' + '\n')

def run():
    # Fetch our Bitcoin price data (Open, High, Low, Close, Volume)
    bars = exchange.fetch_ohlcv(ASSET_NAME, timeframe=TIMEFRAME, limit=FETCHING_LIMIT)
    
    # Create our pandas data frame
    df = pd.DataFrame(bars[:], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Add Supertrend indicator calculation to our data frame
    df = indicators.supertrend(df)

    # Add other indicators
    df = add_indicators(df)

    # Execute
    execute(df)

run()
