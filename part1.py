### terminal steps to setup database ubuntu
# sudo apt install postgresql postgresql-contrib
# sudo systemctl start postgresql.service
# sudo -i -u postgres
# ALTER USER postgres WITH PASSWORD 'passum';

import pandas as pd
import numpy as np
import sqlalchemy.types as st
from sqlalchemy import create_engine
import yfinance as yf


engine = create_engine("postgresql://postgres:passum@localhost",
                       isolation_level='AUTOCOMMIT')

conn = engine.connect()

conn.execute("create database interest_account_transactions")

iat = pd.read_csv('interest_account_transactions_30_days .csv')

iat['confirmed_at'] =  pd.to_datetime(iat['confirmed_at'], infer_datetime_format=True)

iat['date'] = iat['confirmed_at'].dt.date


def prc_avg(df):
    return (df.Open + df.Close)/2

def get_prc(sym):
    ticker = yf.Ticker(sym + '-USD')
    data = ticker.history(start="2020-05-15", end="2020-06-15", interval="1d")
    data = data.reset_index()
    data['date'] = data['Date'].dt.date
    data['mean_price'] = data.apply(prc_avg, axis=1)
    data['cryptocurrency'] = sym.lower()
    data = data[['date', 'mean_price', 'cryptocurrency']]
    return data

currency_lst = ['BTC', 'ETH', 'LTC', 'GUSD', 'USDC', 'USDP']

price_df = pd.DataFrame()

for i in currency_lst:
    crypto_df = get_prc(i)
    price_df = price_df.append(crypto_df)


iat = iat[['cryptocurrency','transaction_type','confirmed_at','customer_id','amount','date']]

datatypes = {"cryptocurrency": st.String(length=8),
     "transaction_type": st.String(length=20),
     "confirmed_at": st.DateTime(),
     "date" : st.Date,
     "customer_id": st.String(length=10),
     "amount": st.Float}

iat.to_sql('interest_account_transactions', engine,
           if_exists='replace', dtype=datatypes)

prc_datatypes = {"date": st.Date(),
                 "mean_price":st.Float}

price_df.to_sql('crypto_prices', engine,
           if_exists='replace', dtype=prc_datatypes)

tstq = pd.read_sql('SELECT * FROM interest_account_transactions', conn)
tstq1 = pd.read_sql('SELECT * FROM crypto_prices', conn)

#%%
hrb = pd.read_sql(
    '''SELECT c.customer_id, c.date, c.cryptocurrency, c.fixed_balance balance, c.mean_price, 
     c.mean_price*c.fixed_balance notional_balance 
    FROM
    (SELECT a.customer_id, a.balance, a.date, a.cryptocurrency,
    MAX(a.balance) OVER (PARTITION BY a.group_balance, a.customer_id, a.cryptocurrency order by a.date) AS fixed_balance,
    b.mean_price
 FROM (SELECT d.date, i.customer_id, i.cryptocurrency, acct.balance,
    sum(case when acct.balance is not null then 1 end) over (partition by i.customer_id, i.cryptocurrency order by d.date) as group_balance
    FROM 
     ( SELECT generate_series(min(date), max(date), interval '1 day') AS date
       FROM interest_account_transactions
     ) AS d
 CROSS JOIN
     ( SELECT DISTINCT customer_id, cryptocurrency
         FROM interest_account_transactions
     ) AS i
    LEFT JOIN 
    (SELECT SUM(amount) over (partition by customer_id,cryptocurrency order by date) balance
    ,date
    ,customer_id
    ,cryptocurrency FROM interest_account_transactions) acct
    USING (customer_id, date, cryptocurrency)) a
    LEFT JOIN crypto_prices b
    USING (date, cryptocurrency)
    order by a.customer_id, a.cryptocurrency, a.date) c''', conn)

#%%

hrb_datatypes = {
    "customer_id": st.String(length=10),
    "date": st.DateTime(),
     "cryptocurrency": st.String(length=8),
     "balance": st.Float,
     "mean_price": st.Float,
     "notional_balance": st.Float}

hrb.to_sql('historical_running_balance', engine,
           if_exists='replace', dtype=hrb_datatypes)

#%%

dau = pd.read_sql(
    ''' SELECT COUNT(DISTINCT(customer_id)) dau, date
    FROM historical_running_balance
    WHERE notional_balance>0
    GROUP BY date
''', conn)

#%%

dau_datatypes = {
     "dau": st.Float,
    "date": st.DateTime()}

dau.to_sql('daily_active_users', engine,
           if_exists='replace', dtype=dau_datatypes)

#%%

wow_dau = pd.read_sql(
    ''' SELECT date, dau, diff, wk_moving_avg, wk_min, wk_max, diff/dau pct_diff
    FROM
    (SELECT date 
    ,dau - lag(dau, 7) OVER (order by date) diff
    ,AVG(dau) OVER (ORDER BY date rows between 6 preceding and current row) wk_moving_avg
    ,MIN(dau) OVER (ORDER BY date rows between 6 preceding and current row) wk_min
    ,MAX(dau) OVER (ORDER BY date rows between 6 preceding and current row) wk_max
    ,dau
     FROM daily_active_users) tbl ''', conn)

#%%

wow_dau_datatypes = {
    "date": st.DateTime(),
     "dau": st.Float,
     "diff": st.Float,
     "wk_moving_avg": st.Float,
     "wk_min": st.Float,
     "wk_max": st.Float,
     "pct_diff": st.Float
}

wow_dau.to_sql('wow_daily_active_users', engine,
           if_exists='replace', dtype=wow_dau_datatypes)

### END OF PART 1 OF CASE STUDY

### BONUS

# deposits
#%%
trans = pd.read_sql(
    '''
    SELECT a.date
     ,a.cryptocurrency
     ,a.transaction_type
     ,sum(a.amount * b.mean_price) dollar_sum
     ,COUNT(DISTINCT(a.customer_id)) quantity
    FROM interest_account_transactions a
    LEFT JOIN crypto_prices b
    USING(date, cryptocurrency)
    GROUP BY a.date, a.cryptocurrency, a.transaction_type
    ''', conn)

#%%

day_trans_datatypes = {
    "date": st.Date,
    "cryptocurrency": st.String(length=8),
    "transaction_type": st.String(length=20),
    "dollar_sum": st.Float,
    "quantity":st.INTEGER}

#%%

trans.to_sql('daily_transaction_summary', engine,
           if_exists='replace', dtype=day_trans_datatypes)
#%%
cust_trans = pd.read_sql(
    '''
    SELECT date
    ,cryptocurrency
    ,transaction_type
    ,COUNT(DISTINCT(customer_id)) customers_transacted
    ,AVG(dollar_sum) dollar_mean
    ,MIN(dollar_sum) dollar_min
    ,MAX(dollar_sum) dollar_max
    ,PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY dollar_sum) dollar_25th_percentile
    ,PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY dollar_sum) dollar_median
    ,PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY dollar_sum) dollar_75th_percentile
    ,AVG(quantity) quantity_mean
    ,MIN(quantity) quantity_min
    ,MAX(quantity) quantity_max
    ,PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY quantity) quantity_25th_percentile
    ,PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY quantity) quantity_median
    ,PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY quantity) quantity_75th_percentile
    FROM
    (SELECT a.date
     ,a.cryptocurrency
     ,a.customer_id
     ,a.transaction_type
     ,sum(a.amount * b.mean_price) dollar_sum
     ,count(a.*) quantity
    FROM interest_account_transactions a
    LEFT JOIN crypto_prices b
    USING(date, cryptocurrency)
    GROUP BY a.date, a.cryptocurrency, a.customer_id, a.transaction_type) tbl
    GROUP BY date, cryptocurrency, transaction_type
    ''', conn)

#%%

cust_day_trans_datatypes = {
    "date": st.Date,
    "cryptocurrency": st.String(length=8),
    "transaction_type": st.String(length=20),
    "customers_transacted":st.INTEGER,
    "dollar_mean": st.Float,
    "dollar_min": st.Float,
    "dollar_max": st.Float,
    "dollar_25th_percentile": st.Float,
    "dollar_median": st.Float,
    "dollar_75th_percentile": st.Float,
    "quantity_mean":st.Float,
    "quantity_min": st.INTEGER,
    "quantity_max":st.INTEGER,
    "quantity_25th_percentile":st.Float,
    "quantity_median":st.Float,
    "quantity_75th_percentile":st.Float}

#%%

cust_trans.to_sql('daily_customer_transaction_summary', engine,
           if_exists='replace', dtype=cust_day_trans_datatypes)
