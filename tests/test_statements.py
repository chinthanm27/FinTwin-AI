import pytest

from app.services import statement_service, transaction_service
from app.services.statement_service import SAMPLE_CSV, parse_amount, parse_date, validate_upload
from app.utils.errors import UploadError


def test_sample_csv_parses_with_types(user):
    parsed = statement_service.process_statement(user.id, "statement.csv", SAMPLE_CSV.encode())
    assert len(parsed.rows) == 10
    by_desc = {r.description: r for r in parsed.rows}
    assert by_desc["SALARY CREDIT - NIMBUS TECH PVT LTD"].transaction_type == "Income"
    assert by_desc["SALARY CREDIT - NIMBUS TECH PVT LTD"].category == "Salary"
    assert by_desc["Swiggy order 8841"].category == "Food"
    assert by_desc["SIP - Groww Nifty 50 index fund"].transaction_type == "Investment"
    assert by_desc["Refund - Flipkart order"].transaction_type == "Income"


def test_import_then_duplicates_detected(user):
    first = statement_service.process_statement(user.id, "s.csv", SAMPLE_CSV.encode())
    assert statement_service.import_rows(user.id, first.rows) == 10
    second = statement_service.process_statement(user.id, "s.csv", SAMPLE_CSV.encode())
    assert second.duplicate_count == 10 and not second.new_rows
    assert len(transaction_service.list_transactions(user.id)) == 10


def test_signed_amount_column(user):
    csv = "Txn Date,Description,Amount\n2026-05-01,Salary credit,85000\n2026-05-02,Zomato,-450\n"
    parsed = statement_service.process_statement(user.id, "s.csv", csv.encode())
    types = [r.transaction_type for r in parsed.rows]
    assert types == ["Income", "Expense"]


def test_header_row_not_first(user):
    csv = "Bank of Example\nAccount: XXXX1234\n\nDate,Particulars,Debit,Credit\n05/05/2026,Uber trip,250.00,\n"
    parsed = statement_service.process_statement(user.id, "s.csv", csv.encode())
    assert parsed.rows[0].category == "Transport"


@pytest.mark.parametrize("name,data,message", [
    ("evil.exe", b"MZ...", "Only CSV and PDF"),
    ("s.pdf", b"not a pdf", "valid PDF"),
    ("s.csv", b"", "empty"),
    ("s.csv", b"PK\x03\x04zip", "text CSV"),
])
def test_upload_validation(name, data, message):
    with pytest.raises(UploadError, match=message):
        validate_upload(name, data)


def test_csv_without_columns_rejected(user):
    with pytest.raises(UploadError, match="No transactions found"):
        statement_service.process_statement(user.id, "s.csv", b"foo,bar\n1,2\n")


def test_parse_helpers():
    assert parse_date("05/03/2026").month == 3
    assert parse_date("12-Jan-2026").day == 12
    assert parse_date("garbage") is None
    assert parse_amount("₹1,234.50 Cr") == (1234.5, "Cr")
    assert parse_amount("(500.00)") == (-500.0, None)
