"""Bank statement upload: /upload"""

from __future__ import annotations

from nicegui import events, run, ui

from app.auth.session import current_user, login_redirect
from app.components.app_shell import app_shell, notify_error
from app.components.dashboard_cards import page_header, panel
from app.config import settings
from app.services import statement_service
from app.services.statement_service import SAMPLE_CSV, ParsedStatement

PREVIEW_COLUMNS = [
    {"name": "date", "label": "Date", "field": "date", "align": "left", "sortable": True},
    {"name": "description", "label": "Description", "field": "description", "align": "left"},
    {"name": "transaction_type", "label": "Type", "field": "transaction_type", "align": "left", "sortable": True},
    {"name": "category", "label": "Category", "field": "category", "align": "left", "sortable": True},
    {"name": "amount", "label": "Amount", "field": "amount", "align": "right", "sortable": True},
    {"name": "duplicate", "label": "Status", "field": "duplicate", "align": "left", "sortable": True},
]


@ui.page("/upload", title="Statements · FinTwin AI")
def upload_page():
    user = current_user()
    if user is None:
        return login_redirect("/upload")
    state: dict[str, ParsedStatement | None] = {"parsed": None}

    with app_shell(user, "upload"):
        page_header("Bank statements",
                    "Upload a CSV or PDF statement. Transactions are extracted, categorised and checked for duplicates "
                    "before anything is saved.",
                    lambda: ui.button("Download sample CSV", icon="download",
                                      on_click=lambda: ui.download.content(SAMPLE_CSV.encode(), "sample_statement.csv",
                                                                           "text/csv")).classes("ft-btn-ghost").props("color=none text-color=none"))

        @ui.refreshable
        def preview() -> None:
            parsed = state["parsed"]
            if parsed is None:
                return
            new_rows = parsed.new_rows
            with panel(f"Review {parsed.file_name}", f"{parsed.file_type} statement · nothing is saved until you import"):
                with ui.row().classes("w-full gap-2 wrap"):
                    ui.label(f"{len(parsed.rows)} transactions found").classes("ft-chip")
                    ui.label(f"{len(new_rows)} new").classes("ft-chip ft-chip-mint")
                    if parsed.duplicate_count:
                        ui.label(f"{parsed.duplicate_count} duplicates skipped").classes("ft-chip ft-chip-amber")
                    if parsed.skipped:
                        ui.label(f"{parsed.skipped} rows unreadable").classes("ft-chip ft-chip-coral")
                    low_conf = sum(1 for r in parsed.rows if r.confidence < 0.5)
                    if low_conf:
                        ui.label(f"{low_conf} categorised as Other (edit later)").classes("ft-chip ft-chip-iris")
                table = ui.table(columns=PREVIEW_COLUMNS, rows=[{**r.to_dict(), "idx": i} for i, r in enumerate(parsed.rows)], row_key="idx",
                                 pagination={"rowsPerPage": 10}).props("flat dark dense wrap-cells").classes("w-full")
                table.add_slot("body-cell-duplicate", """
                    <q-td :props="props"><span class="ft-chip" :class="props.value ? 'ft-chip-amber' : 'ft-chip-mint'">
                    {{ props.value ? 'Duplicate' : 'New' }}</span></q-td>""")
                table.add_slot("body-cell-amount", """
                    <q-td :props="props" class="ft-num" style="font-weight:600">
                    ₹{{ Number(props.value).toLocaleString('en-IN', {maximumFractionDigits: 2}) }}</q-td>""")
                table.add_slot("body-cell-category", """
                    <q-td :props="props">{{ props.value }}
                    <span v-if="props.row.confidence < 50" style="color:#5E6A86;font-size:11px"> (guess)</span></q-td>""")

                async def do_import() -> None:
                    try:
                        count = await run.io_bound(statement_service.import_rows, user.id, parsed.rows)
                    except Exception as exc:
                        notify_error(exc)
                        return
                    ui.notify(f"Imported {count} transactions", type="positive")
                    state["parsed"] = None
                    preview.refresh()
                    with result_area:
                        result_area.clear()
                        with ui.row().classes("ft-tile p-4 w-full items-center gap-3 no-wrap"):
                            ui.icon("check_circle", size="24px").classes("ft-mint")
                            ui.label(f"{count} transactions imported. Your dashboard and AI twin are updated.").classes(
                                "text-sm flex-grow")
                            ui.button("Open dashboard", on_click=lambda: ui.navigate.to("/dashboard")).classes(
                                "ft-btn-primary").props("color=none text-color=none")

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Discard", on_click=lambda: (state.update(parsed=None), preview.refresh())).classes(
                        "ft-btn-ghost").props("color=none text-color=none")
                    import_button = ui.button(f"Import {len(new_rows)} transactions", icon="download_done",
                                              on_click=do_import).classes("ft-btn-primary").props("color=none text-color=none")
                    if not new_rows:
                        import_button.disable()

        async def handle_upload(e: events.UploadEventArguments) -> None:
            try:
                data = await e.file.read()
                parsed = await run.io_bound(statement_service.process_statement, user.id, e.file.name, data)
            except Exception as exc:
                notify_error(exc, "The statement could not be processed.")
                uploader.reset()
                return
            state["parsed"] = parsed
            uploader.reset()
            result_area.clear()
            preview.refresh()
            ui.notify(f"Found {len(parsed.rows)} transactions in {parsed.file_name}", type="info")

        with ui.element("div").classes("grid gap-4 lg:grid-cols-[1.4fr_1fr] w-full"):
            with panel("Upload a statement", f"CSV or PDF · up to {settings.max_upload_mb} MB"):
                with ui.column().classes("w-full items-center gap-3 p-6 rounded-2xl border-2 border-dashed text-center").style(
                        "border-color:var(--line-strong); background:rgba(255,255,255,.02)"):
                    ui.icon("cloud_upload", size="40px").classes("ft-iris")
                    ui.label("Choose a file or drop it here").classes("font-semibold")
                    uploader = ui.upload(
                        on_upload=handle_upload, auto_upload=True, max_file_size=settings.max_upload_bytes,
                        on_rejected=lambda: ui.notify(
                            f"Only CSV or PDF files up to {settings.max_upload_mb} MB are accepted.", type="negative"),
                    ).props('accept=".csv,.pdf" flat bordered color=secondary label="Select statement"').classes("max-w-sm")
                    ui.label("Files are read as data only and stored privately in app/uploads.").classes(
                        "text-xs ft-faint")
            with panel("What works best"):
                for icon, text in [
                    ("table_view", "CSV exports from net banking work best. We look for a header row with a date, a "
                                   "description and either an amount or debit/credit columns."),
                    ("picture_as_pdf", "Text-based PDF statements are supported. Scanned images and password-protected "
                                       "PDFs can't be read."),
                    ("category", "Merchants like Swiggy, Uber, Amazon, Netflix and salary credits are categorised "
                                 "automatically. You can edit any category later."),
                    ("content_copy", "Rows already in your account (same date, amount and description) are skipped."),
                ]:
                    with ui.row().classes("gap-3 no-wrap items-start"):
                        ui.icon(icon, size="20px").classes("ft-iris mt-0.5")
                        ui.label(text).classes("text-sm ft-muted")

        result_area = ui.column().classes("w-full")
        preview()
    return None
