"""Vendored JCAMP-DX DIFDUP/SQZ/DUP/PAC line decoder.

Vendored from nmrglue.fileio.jcampdx (0.12-dev), lines 208-453.

This module is a byte-identical copy of the dependency closure of nmrglue's
``_parse_data`` function (the pseudo-digit / DIFDUP/SQZ/DUP/PAC decoder used
by JCAMP-DX ``##DATA TABLE=`` blocks). It is vendored -- not imported -- so
that lucy-ng's JCAMP-DX reader does not depend on nmrglue's private API
(JC-04). The only changes from the upstream source are: the module docstring
below, the license block, this provenance note, and renaming the public
entry point from ``_parse_data`` to ``parse_data``. The internal logic is
otherwise unmodified.

Copyright Notice and Statement for the nmrglue Project

Copyright (c) 2010-2015 Jonathan J. Helmus
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

a. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

b. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

c. Neither the name of the author nor the names of contributors may
   be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Return contract (Pitfall 2, RESEARCH.md): ``parse_data`` returns RAW decoded
integers as ``(np.ndarray[float64], "R"|"I")``. Y-FACTOR scaling is applied
later by the reader (``lucy_ng.readers.jcamp``), NOT here.
"""

import re
from typing import Any
from warnings import warn

import numpy as np
from numpy.typing import NDArray

###############################################################################
# digit dictionaries for pseudodigit parsing
_DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."]
_SQZ_DIGITS = {"@": "0",
               "A": "1", "B": "2", "C": "3", "D": "4", "E": "5",
               "F": "6", "G": "7", "H": "8", "I": "9",
               "a": "-1", "b": "-2", "c": "-3", "d": "-4", "e": "-5",
               "f": "-6", "g": "-7", "h": "-8", "i": "-9"}
_DIF_DIGITS = {"%": "0",
               "J": "1", "K": "2", "L": "3", "M": "4", "N": "5",
               "O": "6", "P": "7", "Q": "8", "R": "9",
               "j": "-1", "k": "-2", "l": "-3", "m": "-4", "n": "-5",
               "o": "-6", "p": "-7", "q": "-8", "r": "-9"}
_DUP_DIGITS = {"S": "1", "T": "2", "U": "3", "V": "4", "W": "5",
               "X": "6", "Y": "7", "Z": "8", "s": "9"}
###############################################################################


def _detect_format(dataline: str) -> int:
    '''
    Detects and returns digit format:
    0  Normal
    1  Pseudodigits
    -1 Error
    '''

    # regexp to find & skip the first value of line, that never begins
    # with a pseudodigit in any format
    firstvalue_re = re.compile(
        r"(\s)*([+-]?\d+\.?\d*|[+-]?\.\d+)([eE][+-]?\d+)?(\s)*")

    match = firstvalue_re.match(dataline)
    if match is None:
        return -1
    index = match.end()
    if index is None:
        return -1
    try:
        firstchar = dataline[index:index+1]
    except IndexError:
        return -1
    # detect the format from the first character of the second value in line
    if firstchar in _SQZ_DIGITS:
        return 1
    if firstchar in _DIF_DIGITS:
        return 1
    if firstchar in _DUP_DIGITS:
        return 1
    return 0


def _parse_affn_pac(datalines: list[str]) -> list[float] | None:
    ''' Parses datalines that do NOT contain any pseudodigits  '''

    # regexp explained:
    # -values may be delimited with whitespace, comma, or sign (+/-)
    # -may contain leading + or -
    # -base number may have decimal separator (.) or not
    # -if decimal separator is present, number can be given without leading
    #  zero (.1234) or decimals (123.)
    # -exponent (E/e) may be present
    value_re = re.compile(r"(\s|,)*([+-]?\d+\.?\d*|[+-]?\.\d+)([eE][+-]?\d+)?")

    data: list[float] = []
    for dataline in datalines:
        linedata: list[float] = []
        for match in value_re.finditer(dataline):
            base = match.group(2)
            exp = match.group(3)
            try:
                value = float(base + (exp if exp is not None else ""))
            except ValueError:
                warn(f"Data parsing failed at line: {dataline}", stacklevel=2)
                return None
            linedata.append(value)
        if len(linedata) > 1:
            data.extend(linedata[1:])  # ignore first column (X value)
    return data


def _append_value(data: list[float], value_to_append: float, isdif: bool) -> None:
    '''
    Helper function for _finish_value: actual data push happens
    here based on isdif flag (direct value or difference from prev)
    '''
    if isdif:
        data.append(data[-1] + value_to_append)
    else:
        data.append(value_to_append)


def _finish_value(
    valuestr: str,
    currentmode: int,
    prev_value_to_append: tuple[float, bool] | None,
    data: list[float],
) -> tuple[tuple[float, bool] | None, bool]:
    '''
    Helper for _parse_pseudo:
    -Processes value in prev_value_to_append based on currentmode
    -Parses and returns next value_to_append for next round
    '''

    try:
        # squeeze format: number is added to data array as such
        if currentmode == 1:
            if prev_value_to_append is not None:
                _append_value(data, *prev_value_to_append)
            new_value_to_append = (float(valuestr), False)  # isdif=False
            return new_value_to_append, True
        # diff format: number is diff from previous entry
        elif currentmode == 2:
            if prev_value_to_append is not None:
                _append_value(data, *prev_value_to_append)
            new_value_to_append = (float(valuestr), True)  # isdif=True
            return new_value_to_append, True
        # duplicate format: push previous number (or diff) n times
        elif currentmode == 3:
            if prev_value_to_append is None:
                warn("Parse error: DUP entry without preceding value", stacklevel=2)
                return None, False
            dupcount = int(valuestr)
            for _i in range(dupcount):
                _append_value(data, *prev_value_to_append)
            new_value_to_append = None
            return new_value_to_append, True
        else:  # first value
            return None, True
    except ValueError:
        return None, False


def _parse_pseudo(datalines: list[str]) -> list[float] | None:
    ''' Parses datalines packed with pseudodigits  '''

    # regexp to find the first value of line, that never begins
    # with a pseudodigit (exponents are not allowed here)
    firstvalue_re = re.compile(r"(\s)*([+-]?\d+\.?\d*|[+-]?\.\d+)")

    data: list[float] = []
    currentmode = 0
    # valuestr alternates between a list of pending digit characters and the
    # joined string of the just-finished number (vendored logic, unchanged);
    # typed as Any to reflect that intentional dual use without altering it.
    valuestr: Any = []
    skip_checkpoint = False

    # since the DUP mode entries may duplicate previous number n times,
    # we can't directly append newly read values to data. Instead, store
    # them here until next value is read:
    value_to_append: tuple[float, bool] | None = None

    for dataline in datalines:
        if not dataline:
            continue

        # ignore first value of line (X value)
        firstmatch = firstvalue_re.match(dataline)
        assert firstmatch is not None  # noqa: S101 -- vendored logic guarantees a match here
        y_valuestring = dataline[firstmatch.end():]

        first_of_line = True

        # parse rest one char at a time
        for char in y_valuestring.strip():

            # char is digit = continues the current number
            if char in _DIGITS:
                valuestr.append(char)
                continue

            # char is pseudodigit = begin new number
            try:
                valuechar = _SQZ_DIGITS[char]
                newmode = 1
            except KeyError:
                try:
                    valuechar = _DIF_DIGITS[char]
                    newmode = 2
                except KeyError:
                    try:
                        valuechar = _DUP_DIGITS[char]
                        newmode = 3
                    except KeyError:
                        warn(f"Unknown pseudo-digit: {char} at line: {dataline}", stacklevel=2)
                        return None

            # finish previous number
            valuestr = "".join(valuestr)

            # before updating value_to_append, store the mode of last value
            # actually appended to data.
            # this is needed for the DIF checkpoint removal below
            previous_is_dif = False
            if currentmode == 2:
                previous_is_dif = True
            elif currentmode == 3 and value_to_append[1]:  # type: ignore[index]
                previous_is_dif = True

            if not skip_checkpoint:
                # append number in value_to_append to data array if exists,
                # and update value_to_append
                value_to_append, success = _finish_value(valuestr,
                                                         currentmode,
                                                         value_to_append,
                                                         data)
                if not success:
                    warn(f"Data parsing failed at line: {dataline}", stacklevel=2)
                    return None

            # in DIF mode last of line is same than the first of next line
            # (= checkpoint). In such case raise a flag that this number
            # is to be skipped in _finish_value
            skip_checkpoint = first_of_line and previous_is_dif

            # init new number
            currentmode = newmode
            valuestr = [valuechar]
            first_of_line = False

    # read ended. finish last number:
    if not skip_checkpoint:
        valuestr = "".join(valuestr)
        value_to_append, success = _finish_value(valuestr,
                                                 currentmode,
                                                 value_to_append,
                                                 data)
        if not success:
            warn("Data parsing failed at last dataline", stacklevel=2)
            return None

    # append last number now in value_to_append:
    if value_to_append is not None:
        _append_value(data, *value_to_append)

    return data


def parse_data(datastring: str) -> tuple[NDArray[np.float64], str] | None:
    '''
    Creates numpy array from datalines

    Vendored from nmrglue.fileio.jcampdx._parse_data (0.12-dev), renamed
    to a public entry point since lucy-ng's reader and its own hand-oracle
    test both need a non-underscore-private import target (JC-04).
    '''
    datalines = datastring.split("\n")
    headerline = datalines[0]

    datatype = "R"
    if "I..I" in headerline:
        datatype = "I"

    datalines = datalines[1:]  # get rid of the header line (e.g. (X++(Y..Y)))
    mode = _detect_format(datalines[0])
    if mode == 1:
        data = _parse_pseudo(datalines)
    elif mode == 0:
        data = _parse_affn_pac(datalines)
    else:
        return None
    if data is None:
        return None
    return np.asarray(data, dtype="float64"), datatype
