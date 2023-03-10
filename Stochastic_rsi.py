import pybithumb
import pyupbit
import pandas as pd 
import numpy as np
import pandas as pd
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import utils

def get_ohlcv(ticker,n): #코인의 정보를 불러옴, 500*n개의 정보
    dfs = [ ]
    df = pyupbit.get_ohlcv(ticker, interval="minute240")
    dfs.append(df)
    for i in range(n):
        df = pyupbit.get_ohlcv(ticker, interval="minute240", to = df.index[0]) #to: 출력할 max date time을 지정
        dfs.append(df)
        time.sleep(0.2) #한 번에 너무 많은 데이터를 요청하면 웹서버에서 차단할 수 있음

    df = pd.concat(dfs) #list안에 있는 데이터프레임을 하나로 합쳐줌
    df = df.sort_index()
    return df

def fnRSI(m_Df, m_N):
    
    U = np.where(m_Df.diff(1) > 0, m_Df.diff(1), 0)
    D = np.where(m_Df.diff(1) < 0, m_Df.diff(1) *(-1), 0)
    AU = pd.DataFrame(U).rolling( window=m_N, min_periods=m_N).mean()
    AD = pd.DataFrame(D).rolling( window=m_N, min_periods=m_N).mean()    
    RSI = pd.DataFrame(columns=['rsi','index'])
    RSI['rsi'] = AU.div(AD+AU) *100
    RSI['index'] = m_Df.index
    RSI.set_index('index', inplace=True)
    
    return RSI['rsi']


def get_stochastic(df,n_days,slowk_days, slowd_days):
    
    stocastic = pd.DataFrame(columns=['fast_k', 'slow_k', 'slow_d'])
    ndays_high = df.high.rolling(window=n_days, min_periods=1).max()
    ndays_low = df.low.rolling(window=n_days, min_periods=1).min()
    stocastic['fast_k'] = ((df.close - ndays_low) / (ndays_high - ndays_low))*100
    stocastic['slow_k'] = stocastic.fast_k.rolling(slowk_days).mean()
    stocastic['slow_d'] = stocastic.slow_k.rolling(slowd_days).mean()
    
    return stocastic

    
def stocastic_plus_rsi(df,rsi,sto): #stocatsic은 'fast_k', 'slow_k', 'slow_d' 중 하나만 
    
    ma10 = df['close'].rolling(10).mean().shift(1)
    ma20 = df['close'].rolling(20).mean().shift(1)
    ma50 = df['close'].rolling(50).mean().shift(1)
    ma200 = df['close'].rolling(200).mean().shift(1)
    
    cond_1 = (rsi >= 40)&(rsi<=50)
    cond_2 = sto <= 20
    cond_3 = (ma50 > ma200)&(ma10 > ma20) # &(ma20>ma50) 이동평균선이 정렬되어 있을 경우에만 매수 -> 하락장 회피
    buy_cond = cond_1 & cond_2 & cond_3#  & cond_4#참과 거짓이 저장된 series객체
    acc_ror = 1 #원금
    sell_date = None 
    ax_ror = [] #누적수익률은 매도 시점에 업데이트 -> 언제 업데이트
    ay_ror = [] #업데이트 결과

    win_rate = []
    
    for buy_date in df.index[buy_cond]:
        if sell_date != None and buy_date <= sell_date: # 매수 후 매도하지 못했는데 시그널이 오면 그냥 패스
            continue
        
        target = df.loc[buy_date: ]
        sell_cond_1 = rsi[buy_date:] >= 93 # 매도조건 rsi가 80 85 93 95에서 높을수록 성능이 좋게 나옴
        sell_cond_2 = df.close.loc[buy_date:] < df.close.loc[buy_date] * 0.97 #손절전략_매수가격보다 종가기준 3%이상 하락하면 손절
        sell_cond = sell_cond_1 | sell_cond_2
        
        sell_candidate = target.index[sell_cond] # 매도조건을 만족한 시간의 리스트
        buy_price = df.loc[buy_date, 'close']
    
        
        if len(sell_candidate) == 0: #만약 매도조건을 만족한 시간이 없으면 break // 마지막 날의 가격으로 판매한 것으로 가정
            sell_price = df.iloc[-1,3] #-1 -> 마지막 날의 가격 3-> 종가를 의미
            profit = (sell_price/buy_price) - 0.005
            acc_ror *= profit
            ax_ror.append(df.index[-1]) # 팔지못했을 때
            ay_ror.append(acc_ror) # 동일
            
            if profit >= 1:
                win_rate.append(1)
            else:
                win_rate.append(0)
            
            break
        else:
            sell_date = target.index[sell_cond][0]
            sell_price = df.loc[sell_date,'close']
            profit = (sell_price/buy_price) - 0.005
            acc_ror *= profit # 수수료 계산 수수료는 정확한 값 알아보기
            ax_ror.append(sell_candidate[0]) # 매도 날짜를 plot으로 그리기 위해 
            ay_ror.append(acc_ror) # ror을 plot으로
            
            if profit >= 1:
                win_rate.append(1)
            else:
                win_rate.append(0)

            # print("buy date: ", buy_date)
            # print("sell date: ", sell_date)
            # print("ror:", acc_ror)
            # print("")
    
    # candle = go.Candlestick( #비트코인을 캔들차트로 표현
    #     x = df.index,
    #     open = df['open'],
    #     high = df['high'],
    #     close = df['close'],
    #     low = df['low'],
    # )
    
    # ror_chart = go.Scatter( #ror을 그림으로 표현
    #     x = ax_ror,
    #     y = ay_ror
    # )

    # fig = make_subplots(specs = [[{"secondary_y": True}]]) # "secondary_y": True -> ror과 비트코인 가격의 간격이 크니까 (1.0x, 2천만) 유의미한 차트 x --> 축 하나 더 생성
    # fig.add_trace(candle) #trace 메서드를 이용하여 차트를 그림  
    # fig.add_trace(ror_chart, secondary_y = True)
    
    # for idx in df.index[buy_cond]: #annotation은 하나씩 추가해야해서 for문으로 
    #     fig.add_annotation( #구매한 날짜 표시
    #         x = idx,
    #         y = df.loc[idx,'open'] 
    #     )
    # fig.show()
    return acc_ror, ay_ror, win_rate

#df = pyupbit.get_ohlcv("KRW-BTC")
#df = get_ohlcv("KRW-BTC")
#df.to_excel(f"KRW-BTC_4hours.xlsx")
tickers = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'BNB/USDT', 'LTC/USDT', 'TRX/USDT', 'DASH/USDT']
for ticker in tickers:
    df = utils.get_ohlcv('binance', ticker, 4, timeframe='4h', target_time='2023-01-16 16:00:00')
    print(f"--------------------ticker : {ticker}")

    stocastic = get_stochastic(df,14,3,3)
    rsi = fnRSI(df['close'],14)
    fast_k = stocastic['fast_k']
    slow_d = stocastic['slow_d']
    slow_k = stocastic['slow_k']
    cum_ror, ror_list, win_rate = stocastic_plus_rsi(df,rsi,fast_k)
    mdd, dd = utils.mdd(ror_list)
    period = utils.tdelta2year(df.index)
    cagr = utils.cagr(ror_list, period)
    win_rate = utils.win_rate(ror_list)
    print(f"--------------------period : {period:.3f} year")
    print(f"--------------------MDD : {mdd:.3f}%")
    print(f"--------------------CAGR : {cagr:.3f}%")
    print(f"--------------------win_rate : {win_rate:.3f}%")
    print(f"--------------------Overall Trade : {len(ror_list)} 번\n")



# df = utils.get_ohlcv('binance', 'BTC/USDT', 4, timeframe='4h', target_time='2023-01-16 16:00:00')
# stocastic = get_stochastic(df,14,3,3)
# rsi = fnRSI(df['close'],14)
# fast_k = stocastic['fast_k']
# slow_d = stocastic['slow_d']
# slow_k = stocastic['slow_k']
# cum_ror, ror_list, win_rate = stocastic_plus_rsi(df,rsi,fast_k)
# mdd, dd = utils.mdd(ror_list)
# period = utils.tdelta2year(df.index)
# cagr = utils.cagr(ror_list, period)
# print(f"--------------------period : {period:.3f} year")
# print(f"--------------------MDD : {mdd:.3f}%")
# print(f"--------------------CAGR : {cagr:.3f}%")

# ahpr = utils.Ahpr(ror_list, period)
# print(f"--------------------Annualized HPR : {ahpr:.3f}%")