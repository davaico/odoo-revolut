"""Resource limits for the cart evidence shared by charge and return flows."""

import json
import re
from decimal import Decimal

from odoo import _
from odoo.exceptions import UserError


MAX_LINES = 1000
MAX_TAXES = 100
MAX_SNAPSHOT_BYTES = 256 * 1024
MAX_NUMERIC_TEXT = 64
MAX_PRECISION = 28
MAX_EXPONENT = 324
MAX_FIXED_TEXT = 354
MAX_IDENTIFIER = 2147483647
NUMBER = re.compile(r"([+-]?)([0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]+))?")


class FinancialSnapshotError(UserError):
    """Invalid cart input; never evidence that a financial attempt is absent."""


def _invalid(detail):
    return FinancialSnapshotError(_(
        "Revolut cart %(detail)s Correct the cart before starting payment. "
        "If an attempt already exists, check its status or ask a manager to reconcile it.",
        detail=detail,
    ))


def check_line_count(lines):
    # Check len before obtaining an iterator, including at settlement discovery.
    if not isinstance(lines, list):
        raise _invalid("must provide a list of order lines.")
    check_line_count_size(len(lines))


def check_line_count_size(size):
    if size > MAX_LINES:
        raise _invalid("must contain at most 1,000 lines.")


def snapshot_id(value):
    if isinstance(value, str):
        if len(value) > 10 or not re.fullmatch(r"[0-9]+", value):
            raise _invalid("has an invalid identifier (maximum 2,147,483,647).")
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_IDENTIFIER:
        raise _invalid("has an invalid identifier (maximum 2,147,483,647).")
    return value


def decimal_text(value, name, maximum):
    # Bound integers before str() and strings before Decimal's coefficient parse.
    if type(value) is int and abs(value) > maximum:
        raise _invalid(f"{name} must be between -{maximum:,} and {maximum:,}.")
    if type(value) not in (str, int, float):
        raise _invalid(f"{name} must be a finite decimal number.")
    raw = str(value)
    if len(raw) > MAX_NUMERIC_TEXT:
        raise _invalid(f"{name} must use at most 64 numeric characters.")
    match = NUMBER.fullmatch(raw)
    if not match:
        raise _invalid(f"{name} must be a finite decimal number.")
    coefficient = match[2].replace(".", "").lstrip("0").rstrip("0")
    if len(coefficient) > MAX_PRECISION or abs(int(match[3] or 0)) > MAX_EXPONENT:
        raise _invalid(f"{name} must use at most 28 significant digits and an exponent from -324 to 324.")
    number = Decimal(raw)
    if abs(number) > maximum:
        raise _invalid(f"{name} must be between -{maximum:,} and {maximum:,}.")
    # normalize() is exact within the existing 28-digit Decimal context. Predict
    # its fixed-point length from the tuple before format() can expand anything.
    sign, digits, exponent = number.as_tuple()
    if number.is_zero():
        width = sign + 1
    else:
        trailing = len(digits) - len(coefficient)
        # Decimal.as_tuple() already omits leading zeros.
        exponent += trailing
        digit_count = len(digits) - trailing
        width = sign + (digit_count + exponent if exponent >= 0
                        else max(digit_count + 1, 2 - exponent))
    if width > MAX_FIXED_TEXT:
        raise _invalid(f"{name} expands beyond 354 decimal characters.")
    return format(number.normalize(), "f")


def normalize_snapshot(data):
    if not isinstance(data, dict):
        raise _invalid("contents are unavailable.")
    check_line_count(data.get("lines"))
    if not data["lines"]:
        raise _invalid("must contain at least one line.")
    # These fields are consumed outside canonical comparison. Validate them
    # here too, before the Restaurant and original-return callers convert them.
    if "amount_total" in data:
        decimal_text(data["amount_total"], "total", 10**12)
    restaurant = data.get("restaurant")
    if restaurant:
        if not isinstance(restaurant, dict):
            raise _invalid("has invalid restaurant context.")
        for name in ("preset_id", "table_id"):
            snapshot_id(restaurant.get(name) or 0)
    result = {
        "pricelist_id": snapshot_id(data.get("pricelist_id") or 0),
        "fiscal_position_id": snapshot_id(data.get("fiscal_position_id") or 0),
        "lines": [],
    }
    # Count the exact default JSON representation (ASCII, including separators).
    # Every line is individually bounded before its small temporary encoding;
    # refuse before appending once the retained aggregate would exceed budget.
    budget = MAX_SNAPSHOT_BYTES - len(json.dumps(result))
    seen = set()
    for raw in data["lines"]:
        if isinstance(raw, (list, tuple)):
            if len(raw) != 3 or raw[0] not in (0, 1):
                raise _invalid("has an invalid line command.")
            raw = raw[2]
        if not isinstance(raw, dict):
            raise _invalid("has an invalid line.")
        uuid = raw.get("uuid")
        if not isinstance(uuid, str) or not 1 <= len(uuid) <= 128 or uuid in seen:
            raise _invalid("requires unique line identifiers of at most 128 characters.")
        taxes = raw.get("tax_ids") or []
        if not isinstance(taxes, (list, tuple)) or len(taxes) > MAX_TAXES:
            raise _invalid("must contain at most 100 taxes per line.")
        if taxes and isinstance(taxes[0], (list, tuple)):
            command = taxes[0]
            if len(taxes) != 1 or len(command) != 3 or command[0] != 6:
                raise _invalid("has an invalid tax command.")
            taxes = command[2]
        if not isinstance(taxes, (list, tuple)) or len(taxes) > MAX_TAXES:
            raise _invalid("must contain at most 100 taxes per line.")
        try:
            line = {
                "uuid": uuid, "product_id": snapshot_id(raw["product_id"]),
                "qty": decimal_text(raw["qty"], "quantity", 10**9),
                "price_unit": decimal_text(raw["price_unit"], "unit price", 10**9),
                "discount": decimal_text(raw.get("discount", 0), "discount", 10**6),
                "tax_ids": sorted(snapshot_id(tax) for tax in taxes),
            }
        except KeyError:
            raise _invalid("is missing a product, quantity or unit price.") from None
        if not line["product_id"]:
            raise _invalid("is missing a product.")
        if raw.get("refunded_orderline_id"):
            line["refunded_orderline_id"] = snapshot_id(raw["refunded_orderline_id"])
        cost = len(json.dumps(line)) + (2 if result["lines"] else 0)
        if cost > budget:
            raise _invalid("contents exceed 256 KiB; reduce lines or taxes before payment.")
        budget -= cost
        result["lines"].append(line)
        seen.add(uuid)
    result["lines"].sort(key=lambda line: line["uuid"])
    return result
