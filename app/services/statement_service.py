"""
Bank statement upload pipeline.

Upload -> Validation -> Parsing (CSV/PDF) -> Transaction extraction ->
Normalization -> Categorization -> Duplicate detection -> MongoDB.

Security:
- Only .csv and .pdf are accepted, checked by extension AND content.
- Size is capped by MAX_UPLOAD_MB.
- Files are saved under app/uploads/<user_id>/ with a generated name
  (the original filename is never used as a path).
- Files are only read as data; nothing uploaded is ever executed.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.ai.categorizer import categorize
from app.config import settings
from app.database import transaction_repository
from app.models.transaction import Transaction
from app.utils.dates import utcnow
from app.utils.errors import UploadError
from app.utils.logger import get_logger
from app.utils.validators import clean_text

log = get_logger("statements")

ALLOWED_EXTENSIONS = {".csv", ".pdf"}
MAX_ROWS = 5000
MAX_PDF_PAGES = 60

# Example statement format (also written to datasets/sample_bank_statement.csv)
SAMPLE_CSV = """Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance
01/10/2026,SALARY CREDIT - NIMBUS TECH PVT LTD,,91800.00,142300.00
02/10/2026,NEFT - Monthly house rent,22000.00,,120300.00
03/10/2026,Swiggy order 8841,412.00,,119888.00
04/10/2026,Uber trip,236.00,,119652.00
05/10/2026,SIP - Groww Nifty 50 index fund,10000.00,,109652.00
06/10/2026,BESCOM electricity bill,1840.00,,107812.00
07/10/2026,Amazon.in order,2399.00,,105413.00
08/10/2026,Netflix subscription,649.00,,104764.00
09/10/2026,Apollo Pharmacy,560.00,,104204.00
10/10/2026,Refund - Flipkart order,,899.00,105103.00
"""

DATE_HEADERS = ("date", "txn date", "transaction date", "value date", "posting date", "tran date", "value dt")
DESC_HEADERS = ("description", "narration", "particulars", "details", "remarks", "transaction details",
                "transaction remarks", "merchant")
AMOUNT_HEADERS = ("amount", "transaction amount", "amount (inr)", "amt", "txn amount")
DEBIT_HEADERS = ("debit", "withdrawal", "withdrawals", "withdrawal amt", "withdrawal amount", "debit amount", "dr", "paid out")
CREDIT_HEADERS = ("credit", "deposit", "deposits", "deposit amt", "deposit amount", "credit amount", "cr", "paid in")
TYPE_HEADERS = ("type", "dr/cr", "cr/dr", "debit/credit", "txn type", "transaction type")

DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d-%b-%Y", "%d %b %Y", "%d-%b-%y",
                "%d %b %y", "%Y-%m-%d", "%d.%m.%Y", "%d %B %Y", "%b %d, %Y")
PDF_LINE_RE = re.compile(
    r"^(?P<date>\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{1,2}[ \-][A-Za-z]{3}[ \-]\d{2,4}|\d{4}-\d{2}-\d{2})\s+"
    r"(?P<desc>.+?)\s+(?P<amount>-?[\d,]+\.\d{2})(?:\s*(?P<drcr>Cr|Dr|CR|DR)\.?)?(?:\s+-?[\d,]+\.\d{2}(?:\s*(?:Cr|Dr|CR|DR))?)?\s*$"
)


@dataclass
class ParsedRow:
    date: datetime
    description: str
    amount: float
    transaction_type: str
    category: str
    confidence: float
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.strftime("%Y-%m-%d"), "description": self.description, "amount": self.amount,
            "transaction_type": self.transaction_type, "category": self.category,
            "confidence": round(self.confidence * 100), "duplicate": self.duplicate,
        }


@dataclass
class ParsedStatement:
    file_name: str
    file_type: str
    rows: list[ParsedRow] = field(default_factory=list)
    skipped: int = 0
    stored_path: str = ""

    @property
    def new_rows(self) -> list[ParsedRow]:
        return [r for r in self.rows if not r.duplicate]

    @property
    def duplicate_count(self) -> int:
        return sum(1 for r in self.rows if r.duplicate)


# ------------------------------------------------------------------ validation
def validate_upload(file_name: str, data: bytes) -> str:
    """Return the normalized extension or raise UploadError."""
    ext = Path(file_name or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError("Only CSV and PDF bank statements are supported.")
    if not data:
        raise UploadError("The file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise UploadError(f"The file is larger than {settings.max_upload_mb} MB.")
    if ext == ".pdf" and not data[:1024].lstrip().startswith(b"%PDF-"):
        raise UploadError("This file does not look like a valid PDF.")
    if ext == ".csv":
        if b"\x00" in data[:4096]:
            raise UploadError("This file does not look like a text CSV.")
        if data[:2] in (b"PK", b"MZ") or data[:4] == b"\x7fELF":
            raise UploadError("This file does not look like a text CSV.")
    return ext


def store_upload(user_id: str, ext: str, data: bytes) -> Path:
    folder = settings.uploads_dir / re.sub(r"[^a-f0-9]", "", user_id.lower())[:24]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}{ext}"
    path.write_bytes(data)
    return path


# ------------------------------------------------------------------ normalization
def parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    text = re.sub(r"\s+", " ", text)
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return datetime(parsed.year, parsed.month, parsed.day)
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="raise")
        return datetime(parsed.year, parsed.month, parsed.day)
    except (ValueError, TypeError, OverflowError):
        return None


def parse_amount(value: Any) -> tuple[float | None, str | None]:
    """Return (signed amount, 'Cr'/'Dr' marker if present)."""
    if value is None:
        return None, None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return None, None
    marker = None
    m = re.search(r"\b(cr|dr)\.?$", text, re.IGNORECASE)
    if m:
        marker = m.group(1).capitalize()
        text = text[: m.start()].strip()
    negative = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[₹,\s()]|INR|Rs\.?", "", text, flags=re.IGNORECASE)
    if not text:
        return None, marker
    try:
        amount = float(text)
    except ValueError:
        return None, marker
    return (-amount if negative else amount), marker


def _match_header(header: str, options: tuple[str, ...]) -> bool:
    h = re.sub(r"[^a-z/() ]", "", header.lower()).strip()
    h = re.sub(r"\s+", " ", h)
    return h in options or any(h.startswith(opt + " ") or h == opt for opt in options)


def _find_columns(headers: list[str]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for idx, header in enumerate(headers):
        header = str(header or "")
        if "date" not in cols and _match_header(header, DATE_HEADERS):
            cols["date"] = idx
        elif "desc" not in cols and _match_header(header, DESC_HEADERS):
            cols["desc"] = idx
        elif "debit" not in cols and _match_header(header, DEBIT_HEADERS):
            cols["debit"] = idx
        elif "credit" not in cols and _match_header(header, CREDIT_HEADERS):
            cols["credit"] = idx
        elif "amount" not in cols and _match_header(header, AMOUNT_HEADERS):
            cols["amount"] = idx
        elif "type" not in cols and _match_header(header, TYPE_HEADERS):
            cols["type"] = idx
    return cols


def rows_from_table(table: list[list[Any]]) -> tuple[list[dict[str, Any]], int]:
    """Locate the header row in a 2-D table and extract raw transactions."""
    header_idx, cols = None, {}
    for i, row in enumerate(table[:40]):
        candidate = _find_columns([str(c or "") for c in row])
        if "date" in candidate and "desc" in candidate and ({"amount"} & candidate.keys() or {"debit", "credit"} & candidate.keys()):
            header_idx, cols = i, candidate
            break
    if header_idx is None:
        return [], 0
    extracted, skipped = [], 0
    for row in table[header_idx + 1:]:
        cells = list(row) + [None] * 10

        def cell(key: str) -> Any:
            return cells[cols[key]] if key in cols else None

        date = parse_date(cell("date"))
        description = clean_text(str(cell("desc") or ""), 200)
        if date is None or not description:
            skipped += 1 if any(c not in (None, "") for c in row) else 0
            continue
        hint = None
        amount = None
        signed = None
        if "debit" in cols or "credit" in cols:
            debit, _ = parse_amount(cell("debit"))
            credit, _ = parse_amount(cell("credit"))
            if credit and abs(credit) > 0:
                amount, hint = abs(credit), "Income"
            elif debit and abs(debit) > 0:
                amount, hint = abs(debit), "Expense"
        if amount is None and "amount" in cols:
            value, marker = parse_amount(cell("amount"))
            if value is not None and value != 0:
                type_text = str(cell("type") or "").strip().lower()
                if marker == "Cr" or type_text in {"cr", "credit", "c"}:
                    hint = "Income"
                elif marker == "Dr" or type_text in {"dr", "debit", "d"}:
                    hint = "Expense"
                elif value < 0:
                    hint = "Expense"
                signed = value
                amount = abs(value)
        if amount is None or amount <= 0:
            skipped += 1
            continue
        extracted.append({"date": date, "description": description, "amount": round(amount, 2), "hint": hint,
                          "signed": signed})
    # A single signed amount column: if the file uses negatives for debits, positives are credits.
    if any((r["signed"] or 0) < 0 for r in extracted):
        for r in extracted:
            if r["hint"] is None and (r["signed"] or 0) > 0:
                r["hint"] = "Income"
    return extracted, skipped


def parse_csv(data: bytes) -> tuple[list[dict[str, Any]], int]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise UploadError("Could not read the CSV text encoding.")
    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    table = list(csv.reader(io.StringIO(text), delimiter=delimiter))[: MAX_ROWS + 50]
    rows, skipped = rows_from_table(table)
    if not rows:
        raise UploadError(
            "No transactions found. The CSV needs a header row with a date column, a description column, "
            "and either an amount column or debit/credit columns."
        )
    return rows, skipped


def parse_pdf(data: bytes) -> tuple[list[dict[str, Any]], int]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise UploadError("PDF support needs the pdfplumber package (pip install pdfplumber).") from exc
    rows: list[dict[str, Any]] = []
    skipped = 0
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise UploadError(f"PDFs are limited to {MAX_PDF_PAGES} pages.")
            text_lines: list[str] = []
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    found, sk = rows_from_table(table)
                    rows.extend(found)
                    skipped += sk
                text_lines.extend((page.extract_text() or "").splitlines())
    except UploadError:
        raise
    except Exception as exc:  # malformed / encrypted PDFs
        log.warning("PDF parsing failed: %s", type(exc).__name__)
        raise UploadError("This PDF could not be read. It may be scanned, encrypted or damaged.") from None
    if not rows:
        for line in text_lines:
            m = PDF_LINE_RE.match(line.strip())
            if not m:
                continue
            date = parse_date(m.group("date"))
            amount, _ = parse_amount(m.group("amount"))
            if date is None or amount is None or amount == 0:
                skipped += 1
                continue
            drcr = (m.group("drcr") or "").capitalize()
            hint = "Income" if drcr == "Cr" else "Expense" if drcr == "Dr" or amount < 0 else None
            rows.append({"date": date, "description": clean_text(m.group("desc"), 200),
                         "amount": round(abs(amount), 2), "hint": hint})
    if not rows:
        raise UploadError("No transactions could be found in this PDF. Try the CSV export from your bank instead.")
    return rows, skipped


# ------------------------------------------------------------------ pipeline
def process_statement(user_id: str, file_name: str, data: bytes) -> ParsedStatement:
    ext = validate_upload(file_name, data)
    path = store_upload(user_id, ext, data)
    raw_rows, skipped = parse_csv(data) if ext == ".csv" else parse_pdf(data)
    raw_rows = raw_rows[:MAX_ROWS]

    statement = ParsedStatement(file_name=clean_text(file_name, 120), file_type=ext[1:].upper(),
                                skipped=skipped, stored_path=str(path.name))
    start = min(r["date"] for r in raw_rows)
    end = max(r["date"] for r in raw_rows)
    existing = transaction_repository.find_existing_keys(user_id, start, end)
    seen: set[tuple[str, float, str]] = set()
    for raw in raw_rows:
        prediction = categorize(raw["description"], raw.get("hint"))
        ttype = raw.get("hint") or prediction.transaction_type
        if raw.get("hint") == "Expense" and prediction.transaction_type == "Investment":
            ttype = "Investment"
        category = prediction.category
        if ttype == "Income" and category not in {"Salary", "Investment", "Other"}:
            category = "Other"
        key = transaction_repository.duplicate_key(raw["date"], raw["amount"], raw["description"])
        statement.rows.append(ParsedRow(
            date=raw["date"], description=raw["description"], amount=raw["amount"], transaction_type=ttype,
            category=category, confidence=prediction.confidence, duplicate=key in existing or key in seen,
        ))
        seen.add(key)
    log.info("Parsed %s: %d rows (%d duplicates, %d skipped)", ext, len(statement.rows),
             statement.duplicate_count, skipped)
    return statement


def import_rows(user_id: str, rows: list[ParsedRow]) -> int:
    txs = []
    for r in rows:
        if r.duplicate:
            continue
        txs.append(Transaction.create(user_id, r.date, r.category, r.transaction_type, r.amount, r.description, "statement"))
    return transaction_repository.insert_many(txs)


def delete_user_uploads(user_id: str) -> int:
    folder = settings.uploads_dir / re.sub(r"[^a-f0-9]", "", user_id.lower())[:24]
    if not folder.exists():
        return 0
    count = 0
    for file in folder.iterdir():
        if file.is_file():
            file.unlink()
            count += 1
    return count
