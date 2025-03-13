from entsoe import EntsoePandasClient
import pandas as pd

client = EntsoePandasClient(api_key="539dfdf2-c0f1-47d8-97eb-24b9472cc70f")

start = pd.Timestamp('20230101', tz='Europe/Amsterdam')
end = pd.Timestamp('20230102', tz='Europe/Amsterdam')
country_code = 'NL'
process_type = 'A51'

client.query_day_ahead_prices(country_code, start=start, end=end)
ts = client.query_day_ahead_prices(country_code, start=start, end=end)
ts.to_csv('data/day_ahead.csv')

# client.query_imbalance_prices(country_code, start=start, end=end, psr_type=None)