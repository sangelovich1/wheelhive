#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import os
from datetime import datetime, timedelta

import dataframe_image as dfi
import pandas as pd
import requests


# Get a logger instance
logger = logging.getLogger(__name__)

class TTracker:
    URL = "https://media-cdn.factba.se/rss/json/trump/calendar-full.json"

    def __init__(self):
        logger.info("init")
        self.data = []
        self.IMAGE_DIR = "images"
        if not os.path.exists(self.IMAGE_DIR):
            os.mkdir(self.IMAGE_DIR)


    def download(self) -> int:

        response = requests.get(self.URL)
        logger.info(f"Status Code: {response.status_code}")

        if response.ok:
            self.data = response.json()

        return response.status_code

    def query(self, date: datetime) -> list:
        day = date.strftime("%Y-%m-%d")
        schedule = [d for d in self.data if d["date"] in day]
        return schedule

    def parse_date(self, sdate: str) -> datetime | None:
        date_format = "%Y-%m-%d"

        try:
            x = datetime.strptime(sdate, date_format)
        except ValueError as e:
            logger.error(f"Error parsing date: {e}")
            return None

        return x

    def df(self, dt, schedule) -> pd.DataFrame :

        data = list()
        for item in schedule:
            str_event = f'{item["details"]}'
            str_location = f'<b>Location:</b> {item["location"]}'
            str_coverage = f'<b>Coverage:</b> {item["coverage"]}'
            str = f"{str_event}<br>{str_location}<br>{str_coverage}"
            data.append([item["time_formatted"], str])

        df = pd.DataFrame(data, columns=["Time", "Event"])
        df_styled = df.style.hide(axis="index")
        df_styled = df_styled.hide(axis="columns")

        str_date = dt.strftime("%A<br> %B %d %Y")

        df_styled = df_styled.set_caption(f"<b>{str_date}</b>")
        # df_styled = df_styled.set_table_styles([{'selector': 'caption', 'props': [('text-align', 'left')]}])


        df_styled = df_styled.set_properties(
            **{
                "inline-size": "80ch",
                "overflow-wrap": "break-word",
                "text-align": "left",
            },
            subset="Event"
        )

        return df_styled


    def image(self, sdate: str, cacheOnly = True) -> tuple[bool, str]:

        dt = self.parse_date(sdate)
        if dt is None:
            return False, f"Error parsing date {str}. Date must be in the following format 2025-01-31"

        ts = dt.strftime("%Y-%m-%d")
        fname = f"{self.IMAGE_DIR}/{ts}.png"
        if os.path.exists(fname):
            return True, fname

        if cacheOnly:
            logger.debug("Exiting via cacheOnly flag")
            return False, f"Schedule for {ts} not found in cache"


        sc = self.download()
        if sc != 200:
            return False, f"Downloading schedule failed with status code: {sc}"

        schedule = self.query(dt)
        if len(schedule) == 0:
            return False, f"No information found for {dt}."

        df_styled = self.df(dt, schedule)

        dfi.export(df_styled, fname)

        return True, fname


def main():

    tt = TTracker()

    sdate = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Forcing reconstruction of schedule for {sdate}")
    if os.path.exists(f"{tt.IMAGE_DIR}/{sdate}.png"):
        os.remove(f"{tt.IMAGE_DIR}/{sdate}.png")

    start_date = tt.parse_date("2025-01-01")
    if start_date is None:
        logger.error("Failed to parse start date")
        return
    end_date = datetime.now()
    delta = timedelta(days=1)

    # iterate over range of dates
    while (start_date <= end_date):
        #print(f'Processing date: {start_date}')
        status, fpath = tt.image(start_date.strftime("%Y-%m-%d"), cacheOnly=False)
        start_date += delta





if __name__ == "__main__":
    main()

