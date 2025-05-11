#!/usr/bin/env python3

import regex
from typing import Optional


def matches_any_regex(data: str, regex_filters: Optional[list[str]]=None) -> bool:
    """checks if any of the regex filters return a match for provided data

    Parameters
    ----------
    data:          str
                   data to check for matches
    regex_filters: list of str, optional
                   list of regex filters (str)
    Returns
    -------
    bool
        True if any match was found, False otherwise or if no filters provided
    """
    if regex_filters == None: return False

    compiled_filters = [regex.compile(f) for f in regex_filters]
    return any(f.search(data) for f in compiled_filters)
