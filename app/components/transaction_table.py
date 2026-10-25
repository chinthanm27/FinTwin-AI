"""Transaction list and table components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from app.models.transaction import CATEGORY_ICONS, Transaction
from app.styles.theme import TYPE_COLORS
from app.utils.formatters import format_date, format_inr

COLUMNS = [
    {"name": "date", "label": "Date", "field": "date", "sortable": True, "align": "left"},
    {"name": "description", "label": "Description", "field": "description", "sortable": True, "align": "left",
     "classes": "ft-desc-cell"},
    {"name": "category", "label": "Category", "field": "category", "sortable": True, "align": "left"},
    {"name": "transaction_type", "label": "Type", "field": "transaction_type", "sortable": True, "align": "left"},
    {"name": "amount", "label": "Amount", "field": "amount", "sortable": True, "align": "right"},
    {"name": "actions", "label": "", "field": "id", "align": "right"},
]

TABLE_SLOTS = {
    "body-cell-transaction_type": """
        <q-td :props="props">
          <span class="ft-chip" :class="{'ft-chip-mint': props.value==='Income', 'ft-chip-coral': props.value==='Expense',
                'ft-chip-sky': props.value==='Investment'}">{{ props.value }}</span>
        </q-td>""",
    "body-cell-amount": """
        <q-td :props="props" class="ft-num" :style="{color: props.row.transaction_type==='Income' ? '#3EE6B0' :
              (props.row.transaction_type==='Investment' ? '#4CC2FF' : '#E7ECF6'), fontWeight: 600}">
          {{ props.row.transaction_type==='Income' ? '+' : '−' }}₹{{ Number(props.value).toLocaleString('en-IN', {maximumFractionDigits: 2}) }}
        </q-td>""",
    "body-cell-description": """
        <q-td :props="props" style="max-width:340px; white-space:normal">
          <div class="text-sm">{{ props.value || '—' }}</div>
          <div v-if="props.row.source && props.row.source !== 'manual'" class="text-[11px]" style="color:#5E6A86">
            {{ props.row.source === 'statement' ? 'Imported from statement' : (props.row.source === 'demo' ? 'Demo data' : props.row.source) }}
          </div>
        </q-td>""",
    "body-cell-actions": """
        <q-td :props="props" auto-width style="white-space:nowrap">
          <q-btn flat round dense size="sm" icon="edit" aria-label="Edit" @click="() => $parent.$emit('edit', props.row)" />
          <q-btn flat round dense size="sm" icon="delete_outline" color="negative" aria-label="Delete"
                 @click="() => $parent.$emit('delete', props.row)" />
        </q-td>""",
}


def transactions_table(rows: list[dict[str, Any]], on_edit: Callable[[dict[str, Any]], None],
                       on_delete: Callable[[dict[str, Any]], None]) -> ui.table:
    table = ui.table(
        columns=COLUMNS, rows=rows, row_key="id",
        pagination={"rowsPerPage": 15, "sortBy": None},
    ).props("flat dark dense wrap-cells binary-state-sort").classes("w-full")
    table.props('no-data-label="No transactions match these filters."')
    for name, template in TABLE_SLOTS.items():
        table.add_slot(name, template)
    table.on("edit", lambda e: on_edit(e.args))
    table.on("delete", lambda e: on_delete(e.args))
    return table


def recent_list(transactions: list[Transaction]) -> None:
    if not transactions:
        ui.label("No transactions yet.").classes("ft-muted text-sm")
        return
    with ui.column().classes("w-full gap-0"):
        for t in transactions:
            color = TYPE_COLORS.get(t.transaction_type, "#8C98B5")
            with ui.row().classes("w-full items-center gap-3 no-wrap py-2.5 border-b").style("border-color:var(--line)"):
                with ui.element("div").classes("rounded-xl p-2 shrink-0").style(f"background:{color}1A"):
                    ui.icon(CATEGORY_ICONS.get(t.category, "category"), size="18px").style(f"color:{color}")
                with ui.column().classes("gap-0 min-w-0 flex-grow"):
                    ui.label(t.description or t.category).classes("text-sm font-semibold truncate")
                    ui.label(f"{t.category} · {format_date(t.date)}").classes("text-xs ft-muted")
                sign = "+" if t.transaction_type == "Income" else "−"
                ui.label(f"{sign}{format_inr(t.amount)}").classes("text-sm font-semibold ft-num shrink-0").style(
                    f"color:{color if t.transaction_type != 'Expense' else 'var(--text)'}"
                )
