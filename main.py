import requests
from lxml import etree
import datetime
import pytz
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import print
from collections import defaultdict
from functools import lru_cache
import sys

#############################################
# user configs
#############################################

USER_IDS = ["roeniss"]

# use ethiopia timezone because we consider 06:00(+09:00) as start of the next day
TIMEZONE = pytz.timezone("Africa/Addis_Ababa")

START_DATE_FROM_TODAY = 7  # not including today, for our purpose.s


#############################################
# constants
#############################################

# reference: https://solvedac.github.io/unofficial-documentation/#/operations/getProblemsCountGroupByLevel
LEVEL_REFERENCE = {
    0: Text().append("NR", style="turquoise4"),  # not rated
    1: Text().append("B5", style="orange4"),
    2: Text().append("B4", style="orange4"),
    3: Text().append("B3", style="orange4"),
    4: Text().append("B2", style="orange4"),
    5: Text().append("B1", style="orange4"),
    6: Text().append("S5", style="light_steel_blue1"),
    7: Text().append("S4", style="light_steel_blue1"),
    8: Text().append("S3", style="light_steel_blue1"),
    9: Text().append("S2", style="light_steel_blue1"),
    10: Text().append("S1", style="light_steel_blue1"),
    11: Text().append("G5", style="gold1"),
    12: Text().append("G4", style="gold1"),
    13: Text().append("G3", style="gold1"),
    14: Text().append("G2", style="gold1"),
    15: Text().append("G1", style="gold1"),
    16: Text().append("P5", style="cyan1"),
    17: Text().append("P4", style="cyan1"),
    18: Text().append("P3", style="cyan1"),
    19: Text().append("P2", style="cyan1"),
    20: Text().append("P1", style="cyan1"),
    21: Text().append("D5", style="red1"),
    22: Text().append("D4", style="red1"),
    23: Text().append("D3", style="red1"),
    24: Text().append("D2", style="red1"),
    25: Text().append("D1", style="red1"),
    26: Text().append("R5", style="magenta1"),
    27: Text().append("R4", style="magenta1"),
    28: Text().append("R3", style="magenta1"),
    29: Text().append("R2", style="magenta1"),
    30: Text().append("R1", style="magenta1"),
}

#############################################
# get user's submission data
#############################################


@lru_cache(maxsize=None)
def _get_session():
    return requests.Session()


def _get_page(user_id, top):
    """
    return: str
    """
    url = f"https://www.acmicpc.net/status?user_id={user_id}&result_id=4"
    if top:
        url += f"&top={top}"

    headers = {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        + "AppleWebKit/537.36 (KHTML, like Gecko)"
        + "Chrome/128.0.0.0 Safari/537.36"
    }

    response = _get_session().get(url, headers=headers)

    return response.text


def _parse_time_to_problem_id(html):
    """
    return: last_submit_time to problem_id and last_submit_id
            [dict]{[int]last_submit_time: [int]problem_id, ...}, [int]last_submit_id
    """
    time_to_problem_id = defaultdict(lambda: 0)

    html = etree.HTML(html)
    trs = html.cssselect("table.table tr")[1:]

    for tr in trs:
        tds = tr.cssselect("td")

        try:
            last_submit_id = int(tds[0].text)
            problem_id = int(tds[2].cssselect("a")[0].text)
            submit_time = int(tds[8].cssselect("a")[0].attrib["data-timestamp"])
        except IndexError:
            # some row is blank (redacted?)
            continue

        time_to_problem_id[submit_time] = max(
            time_to_problem_id[submit_time], int(problem_id)
        )

    return time_to_problem_id, last_submit_id


def _merge_dicts(dict1, dict2):
    """
    in-place merge
    XXX: expects single value
    """
    for key, value in dict2.items():
        if key in dict1:
            dict1[key] = max(dict1[key], value)
        else:
            dict1[key] = value


def get_time_to_problem_id(user_id):
    """
    return: last_submit_time to problem_id
            [dict]{[int]last_submit_time: [int]problem_id, ...}x
    """
    time_to_problem_id = {}
    max_fetch = 5
    max_size = 200
    last_submit_id = ""

    # with above config, it roughly fetches 80 problems
    while max_fetch > 0 and len(time_to_problem_id) < max_size:
        max_fetch -= 1
        html = _get_page(user_id, last_submit_id)
        data, last_submit_id = _parse_time_to_problem_id(html)
        _merge_dicts(time_to_problem_id, data)

    return time_to_problem_id


#############################################
# visualize the data
#############################################


@lru_cache(maxsize=None)
def _get_problem_level_dict():
    problem_level_dict = {}

    with open("./problem_level_mapping.csv", "r") as f:
        lines = f.readlines()
        for line in lines:
            if "," not in line:
                continue

            _problem_id, level = line.split(",")

            problem_level_dict[int(_problem_id)] = int(level)

    return problem_level_dict


def _get_problem_levels(problem_ids):
    """
    param problem_ids: [set]{[int]problem_id1, problem_id2, ...}
    return: rich.Text list
            [list][text1, text2, ...]
    """
    if not problem_ids:
        return []

    problem_level_dict = _get_problem_level_dict()
    levels = [problem_level_dict.get(i) for i in problem_ids]
    levels = reversed(sorted(levels))

    return [LEVEL_REFERENCE[i] for i in levels]


def _parse_date(date_str):
    return datetime.datetime.fromtimestamp(date_str, tz=TIMEZONE).date()


def _get_today():
    return datetime.datetime.now(tz=TIMEZONE).date()


def _group_problem_ids_per_day(time_to_problem_id):
    date_to_problem_ids = defaultdict(set)

    for submit_time, problem_id in time_to_problem_id.items():
        date = _parse_date(submit_time)
        date_to_problem_ids[date].add(problem_id)

    return date_to_problem_ids


def view_table(user_statistics_list):
    today = _get_today()
    days = [
        today - datetime.timedelta(days=i) for i in range(1, START_DATE_FROM_TODAY + 1)
    ]

    table = Table(title="이번 주의 숙제 검사", show_lines=True)
    table.add_column("user_id", justify="right", style="cyan", no_wrap=True)
    for day in days:
        table.add_column(f'{day.strftime("%m-%d (%a)")}')

    for user, time_to_problem_id in user_statistics_list.items():
        columns = [user]
        date_to_problem_ids = _group_problem_ids_per_day(time_to_problem_id)

        for day in days:
            problem_ids = date_to_problem_ids.get(day)
            if not problem_ids:
                columns.append("-")
                continue

            levels = _get_problem_levels(problem_ids)

            columns.append(levels[0])
            for level in levels[1:]:
                columns[-1] += ", "
                columns[-1] += level
        table.add_row(*columns)

    Console().print(table)


#############################################
# main
#############################################


def _get_user_ids():
    if len(sys.argv) > 1:
        return sys.argv[1:]
    return USER_IDS


if __name__ == "__main__":
    user_ids = _get_user_ids()

    stats = {user_id: get_time_to_problem_id(user_id) for user_id in user_ids}

    view_table(stats)
