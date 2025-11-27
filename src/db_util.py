#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from datetime import datetime

from tabulate import tabulate

import util
from db import Db


db = Db()
# trades = Trades(db)

# select = "SELECT count(id) FROM trades"
# rows = db.query(select=select)
# print("All Trades")
# for row in rows:
#     print(row)

# select = 'SELECT count(operation) FROM trades WHERE operation="STO"'
# print("STO Trades")
# rows = db.query(select=select)
# for row in rows:
#     print(row)

# select = 'SELECT count(operation) FROM trades WHERE operation="BTC"'
# print("BTC Trades")
# rows = db.query(select=select)
# for row in rows:
#     print(row)

# select = 'SELECT operation, count(operation) FROM trades GROUP BY operation'
# print("Group by operation and count")
# rows = db.query(select=select)
# for row in rows:
#     print(row)

# select = 'SELECT symbol, count(symbol) FROM trades GROUP BY symbol'
# print("Group by symbol and count")
# rows = db.query(select=select)
# for row in rows:
#     print(row)


select = "SELECT min(date), max(date) FROM trades"
print("Min/Max date")
rows = db.query(select=select)

start_date = rows[0][0]
start_date =datetime.strptime(start_date, "%Y-%m-%d")

end_date = rows[0][1]
end_date =datetime.strptime(end_date, "%Y-%m-%d")

print(f"start_date: {start_date}")
print(f"end_date: {end_date}")


for month_str in util.month_iterator(start_date, end_date):
    month = datetime.strptime(month_str, "%Y-%m-%d")
    sdt, edt = util.month_start_end(month)
    filter = f'datetime(date) >= datetime("{sdt}") and datetime(date) <= datetime("{edt}")'
    my = sdt.strftime("%m/%Y")
    print(my)
    # Stats on operation
    select = "SELECT operation, count(operation), sum(contracts), sum(total) FROM trades"
    rows = db.query(select=select,condition=filter, groupby="operation")
    table_str = tabulate(rows, headers=["Action", "Trades", "Contracts", "Total Premium"], stralign="right", floatfmt=".2f")
    print(table_str)
    print("\n")

    # Stats on symbol
    select = "SELECT symbol, count(symbol), sum(contracts), sum(total) FROM trades"
    rows = db.query(select=select,condition=filter, groupby="symbol")
    table_str = tabulate(rows, headers=["Symbol", "Trades", "Contracts", "Total Premium"], stralign="right", floatfmt=".2f")
    print(table_str)
    print("---------------------------------------------")
