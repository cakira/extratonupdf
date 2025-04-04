# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# SPDX-License-Identifier: MPL-2.0
# SPDX-FileCopyrightText: 2025 Cleber Akira Nakandakare <cleber.akira@gmail.com>

import datetime
import re
import zlib

import pymupdf

_GET_YEAR_PATTERN = r'vencimento.*(\d{4})$'

# Regex to extract transaction entries with the following capture groups:
# 1: day (dd)
# 2: month (three-letter Portuguese abbreviation)
# 3: transaction title
# 4: negative value indicator (present if value is negative). It's non-ASCII.
# 5: value amount (as formatted string with thousand separators)
_GET_ENTRY_PATTERN = r'^(\d\d) ([A-Z]{3})\n(.*)\n(.?)R\$ ([0-9.]+,\d\d)$'

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
    """Extract transactions with dates, descriptions, values and categories
    from PDF statement."""
    doc = pymupdf.open(filename)
    text: str = _get_text_from_pdf(doc)
    year = _discover_year(text)
    table = _get_entries(text, year)
    category_list = _get_categories(doc)
    # TODO: Raise error is len(category_list) != len()
    new_table = [
        (date, title, value, category)
        for (date, title,
             value), category in zip(table, category_list, strict=True)
    ]
    return new_table


def _get_text_from_pdf(pymupdf_document) -> str:
    text_parts: list[str] = []
    for page in pymupdf_document:
        text_parts.append(page.get_text())
    return ''.join(text_parts)


def _discover_year(extrato_text: str) -> int:
    match = re.search(_GET_YEAR_PATTERN, extrato_text,
                      re.UNICODE | re.MULTILINE)
    if not match:
        raise ValueError("Year not found in document")
    return int(match[1])


def _get_entries(extrato_text: str, year: int) -> list[tuple]:
    entry_pattern = re.compile(_GET_ENTRY_PATTERN, re.UNICODE | re.MULTILINE)
    entries: list[list[str]] = entry_pattern.findall(extrato_text)
    table = []
    for entry in entries:
        day = int(entry[0])
        month = _MONTHS[entry[1]]
        # Transition for December entries belong to previous year
        entry_year = year if (month != 12) else (year - 1)
        date = datetime.date(entry_year, month, day)
        title = entry[2]
        value = float(entry[4].replace('.', '').replace(',', '.'))
        if entry[3]:
            value = -value
        table += [(date, title, value)]
    return table


def _get_categories(pymupdf_document) -> list[str]:
    # Mapping of image checksums to category names for transaction
    # classification.
    # These hashes correspond to small embedded icons in the PDF statement:
    # - Generated using zlib.adler32() of the raw image bytes.
    #   See _lightweight_hash()
    # - Manually mapped through empirical analysis of the PDF format
    # - Specific to the current statement layout (may need updating if bank
    #   changes icons)
    # The empty string represents transactions without a category icon
    category_hashtable = {
        '7784104a': '',
        'fc279303': 'eletrônicos',
        '11d5189d': 'casa',
        '8b3caae0': 'lazer',
        'cfeed549': 'outros',
        '00fd45bb': 'restaurante',
        '29637e8d': 'saúde',
        'cc8dae95': 'serviços',
        'c6ed8a46': 'supermercado',
        '5c8d338d': 'transporte',
        '5a84907b': 'viagem',
    }

    xrefs = _get_categories_as_xrefs(pymupdf_document)
    xrefs_to_hashes_dict = _get_hashes_by_xref(xrefs, pymupdf_document)
    hashes = [xrefs_to_hashes_dict[xref] for xref in xrefs]
    categories = []
    for image_hash in hashes:
        category = category_hashtable.get(image_hash, '?')
        categories.append(category)
    return categories


def _get_categories_as_xrefs(pymupdf_document) -> list[int]:
    _TRANSACTIONS_START_PAGE = 4  # The page where transactions start appearing

    categories_xrefs = []
    for page_num in range(_TRANSACTIONS_START_PAGE, len(pymupdf_document)):
        page = pymupdf_document.load_page(page_num)
        images_info = page.get_image_info(xrefs=True)
        # The first image_info is not related to the categories
        for info in images_info[1:]:
            xref = info['xref']
            categories_xrefs.append(xref)
    return categories_xrefs


def _get_hashes_by_xref(xrefs, pymupdf_document) -> dict[int, str]:
    xrefs_to_hashes = dict()
    for xref in set(xrefs):
        image_bytes = pymupdf_document.extract_image(xref)['image']
        image_hash = _lightweight_hash(image_bytes)
        xrefs_to_hashes[xref] = image_hash
    return xrefs_to_hashes


def _lightweight_hash(bytes) -> str:
    '''The returned hash doesn't need to be tampering resistant or very
    collision proof, because they are not confidential and there will be only a
    dozen of categories'''
    return format(zlib.adler32(bytes), '08x')
