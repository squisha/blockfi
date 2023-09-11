#%%

import numpy as np
import pandas as pd
import os
import glob
import sqlalchemy.types as st


path = os.getcwd()+"/case_study_data "
csvs = glob.glob(os.path.join(path, "*.xlsx"))


loans = pd.DataFrame()
for f in csvs:
    data = pd.read_excel(f, 'Sheet1')
    loans = loans.append(data)


### The approach taken here is to identify date values that are a string and just make them NAN
### Then Convert the columns to Date datatype. For the NAN Dates we non missing date add or subtract the non missing date
### to get the missing date. This works because there are no cases where both dates or term is missing.
### Because there weren't many different Term values, just used loans['Term'].value_counts() to identify the
## one value that needed to be fixed in order to make the Term column usable i.e. integer datatype

loans['Funding Date'] = np.where(loans['Funding Date'].str.len().notnull(),  np.NAN, loans['Funding Date'])
loans['Funding Date'] = pd.to_datetime(pd.to_numeric(loans['Funding Date']), unit='d', origin='1899-12-30').dt.date
loans['Maturity Date'] = np.where(loans['Maturity Date'].str.len().notnull(),  np.NAN, loans['Maturity Date'])
loans['Maturity Date'] = pd.to_datetime(pd.to_numeric(loans['Maturity Date']), unit='d', origin='1899-12-30').dt.date
loans['Term']=np.where(loans['Term']=='Twelve',12,loans['Term']).astype(int)
loans['Funding Date'] = np.where(loans['Funding Date'].isnull(), loans['Maturity Date'] - loans['Term'].astype('timedelta64[M]'),loans['Funding Date'])
loans['Maturity Date'] = np.where(loans['Maturity Date'].isnull(), loans['Funding Date'] + loans['Term'].astype('timedelta64[M]'),loans['Maturity Date'])

  ## find that only one string is Twenty Two Thousand
loans['LA_has_string']=loans['Loan Amount'].str.isalpha()
## find that only string values are '!#Ref','#!REF' just force all to nan
loans['AF_has_string']=loans['Amount Funded'].str.isalpha()
loans['IR_has_string']=loans['Interest Rate'].str.isalpha()
loans['OF_has_string']=loans['Origination Fee'].str.isalpha()

 ## fix all values
loans['Loan Amount']=np.where(loans['Loan Amount']=='Twenty Two Thousand', 22000.0, loans['Loan Amount']).astype('float')
loans['Amount Funded'] = pd.to_numeric(loans['Amount Funded'], errors='coerce')
loans['Interest Rate'] = pd.to_numeric(loans['Interest Rate'], errors='coerce')
loans['Origination Fee'] = pd.to_numeric(loans['Origination Fee'], errors='coerce')

loans = loans.drop(columns=['LA_has_string', 'AF_has_string','IR_has_string','OF_has_string']).rename(
    columns={"Term": "term",
             "Interest Rate": "interest_rate",
             "Origination Fee":"origination_fee",
             "Funding Date":"funding_date",
             "Maturity Date":"maturity_date",
             "Loan Amount": "loan_amount",
             "Amount Funded": "amount_funded",
             "Principal Balance": "principal_balance",
             "Payoff Amount": "payoff_amount",
             "Collateral Posted":"collateral_posted"})

loans_datatypes = {
    "term":st.INTEGER,
    "interest_rate":st.Float,
    "origination_fee":st.Float,
    "funding_date":st.DateTime,
    "maturity_date":st.DateTime,
    "loan_amount":st.Float,
    "amount_funded":st.Float,
    "principal_balance":st.Float,
    "payoff_amount":st.Float,
    "collateral_posted":st.Float
}

loans.to_sql('loans', engine,
           if_exists='replace', dtype=loans_datatypes)

loans_test = pd.read_sql(
    ''' SELECT * from loans
''', conn)