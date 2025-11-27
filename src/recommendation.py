#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging

from tabulate import tabulate

from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class Recommendation:
    db: Db

    def __init__(self, db: Db):
        self.db = db
        self.__create_table()

    def headers(self):
        return ("Topic", "Reference")

    def __create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS recommendation (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            topic TEXT NOT NULL,
            reference TEXT NOT NULL)
        """
        self.db.create_table(query)

    def add(self, username: str, topic: str, reference: str):
        self.insert((username, topic, reference))

    def insert(self, row):
        query = """
            INSERT INTO recommendation 
                (username, topic, reference ) 
                values(?, ?, ?)
            """
        self.db.insert(query, row)


    def query(self) -> list[tuple]:
            return self.db.query(select="SELECT topic, reference from recommendation")

    def del_all(self) -> list[tuple]:
        return self.db.query(select="DELETE FROM recommendation")

    def get(self) -> str:
        rows = self.query()
        header = self.headers()
        table_str = tabulate(rows, headers=header, stralign="right", floatfmt=".2f")
        table_size = len(table_str)
        return table_str

def main():
    db = Db()
    r = Recommendation(db)
    r.del_all()
    recommendations =  [
        ("brock.hamilton.88", "LEAPS Overview", "https://www.youtube.com/watch?v=QBiQzgujNhM"),
        ("ajvtinvests", "Anchored VWAP", "Anchored VWAP - Brian Shannon")
    ]
    for reference in recommendations:
        r.insert(reference)

    print(r.get())


if __name__ == "__main__":
    main()
