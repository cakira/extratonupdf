# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# SPDX-License-Identifier: MPL-2.0
# SPDX-FileCopyrightText: 2025 Cleber Akira Nakandakare <cleber.akira@gmail.com>

import datetime
import re

import pymupdf

_GET_YEAR_PATTERN = r'vencimento.*(\d{4})$'
_GET_ENTRY_PATTERN = r'^(\d\d) ([A-Z]{3})\n(.*)\n(.?)R\$ ([0-9.]+,\d\d)$'
# group 1 -> day
# group 2 -> month, in 3 characters Portuguese
# group 3 -> title
# group 4 -> if present, value is negative
# group 5 -> value (check group 4 for its signal)
_MONTHS = {
    'JAN': 1,
    'FEV': 2,
    'MAR': 3,
    'ABR': 4,
    'MAI': 5,
    'JUN': 6,
    'JUL': 7,
    'AGO': 8,
    'SET': 9,
    'OUT': 10,
    'NOV': 11,
    'DEZ': 12
}


def pdf_to_table(filename) -> list[tuple]:
    text: str = _get_text_from_pdf(filename)
    year = _discover_year(text)
    table = _get_entries(text, year)
    return table


def _get_text_from_pdf(filename) -> str:
    text: str = ''
    doc = pymupdf.open(filename)
    for page in doc:
        text = text + page.get_text()
    return text


def _discover_year(extrato_text: str) -> int:
    match = re.search(_GET_YEAR_PATTERN, extrato_text,
                      re.UNICODE | re.MULTILINE)
    return int(match[1])


def _get_entries(extrato_text: str, year: int) -> list[tuple]:
    entry_pattern = re.compile(_GET_ENTRY_PATTERN, re.UNICODE | re.MULTILINE)
    entries: list[list[str]] = entry_pattern.findall(extrato_text)
    table = []
    for entry in entries:
        day = int(entry[0])
        month = _MONTHS[entry[1]]
        entry_year = year if (month != 12) else (year - 1)
        date = datetime.date(entry_year, month, day)
        title = entry[2]
        value = float(entry[4].replace('.', '').replace(',', '.'))
        if entry[3]:
            value = -value
        table += [(date, title, value)]
    return table
