#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import random

from db import Db


# Get a logger instance
logger = logging.getLogger(__name__)

class Quote:
    db: Db

    def __init__(self, db: Db):
        self.db = db
        self.__create_table()

    def __create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            quote TEXT NOT NULL,
            author TEXT NOT NULL)
        """
        self.db.create_table(query)


    def insert(self, row):
        query = """
            INSERT INTO quotes 
                (username, quote, author ) 
                values(?, ?, ?)
            """
        self.db.insert(query, row)

    def query(self) -> list[tuple]:
            return self.db.query(select="SELECT * from quotes")

    def del_all(self) -> list[tuple]:
        return self.db.query(select="DELETE FROM quotes")

    def get(self) :
        rows = self.query()
        random_element = random.choice(rows)
        d = {"quote": random_element[2], "author": random_element[3]}
        return d



def main():
    db = Db()
    q = Quote(db)


    quotes = [
    ("sangelovich", "May the force be with you", "star wars"),
    ("sangelovich", "Do or do not. There is no try.", "Yoda"),
    ("sangelovich", "Skate to where the puck is going, not where it has been.", "Wayne Gretzky"),
    ("sangelovich", "Buy the rumor, sell the news.", "Anonymous"),
    ("sangelovich", "The market can stay irrational longer than you can stay solvent.", "Anyonymous"),
    ("sangelovich", "Never catch a falling knife.", "Anonymous"),
    ("sangelovich", "Sell in may, go away.", "Anonymous"),
    ("sangelovich", "Stocks take the stairs up and the elevator down.", "Anonymous")
    ]
    q.del_all()
    for quote in quotes:
        q.insert(quote)

    rows = q.query()
    for row in rows:
        print(row)

    print("random: " , q.get())

if __name__ == "__main__":
    main()
