"""catalog material identity

Revision ID: 0a1b2c3d4e5f
Revises: a5b6c7d8e9f0
Create Date: 2026-07-12 00:00:00.000000
"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPE_LABELS = {
    "dsp": "LDSP",
    "mdf": "MDF",
    "plywood": "Fanera",
    "natural_wood": "Yog'och",
    "other": "Panel",
}
_DIMENSION_SEPARATOR = "\N{MULTIPLICATION SIGN}"


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("materials", sa.Column("edge_width_mm", sa.Integer(), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE materials SET edge_width_mm = 19 WHERE kind = 'edge' AND edge_width_mm IS NULL"
        )
    )
    _regenerate_names(bind)
    op.drop_constraint("ck_materials_kind_shape", "materials", type_="check")
    op.create_check_constraint(
        "ck_materials_kind_shape",
        "materials",
        "(kind = 'panel' AND type IS NOT NULL "
        "AND panel_length_mm IS NOT NULL AND panel_width_mm IS NOT NULL "
        "AND panel_length_mm >= panel_width_mm AND grain_direction IS NOT NULL "
        "AND edge_width_mm IS NULL) "
        "OR (kind = 'edge' AND type IS NULL "
        "AND panel_length_mm IS NULL AND panel_width_mm IS NULL "
        "AND grain_direction IS NULL AND edge_width_mm IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_materials_edge_width_positive",
        "materials",
        "edge_width_mm IS NULL OR edge_width_mm > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_materials_edge_width_positive", "materials", type_="check")
    op.drop_constraint("ck_materials_kind_shape", "materials", type_="check")
    op.create_check_constraint(
        "ck_materials_kind_shape",
        "materials",
        "(kind = 'panel' AND type IS NOT NULL "
        "AND panel_length_mm IS NOT NULL AND panel_width_mm IS NOT NULL "
        "AND panel_length_mm >= panel_width_mm AND grain_direction IS NOT NULL) "
        "OR (kind = 'edge' AND type IS NULL "
        "AND panel_length_mm IS NULL AND panel_width_mm IS NULL "
        "AND grain_direction IS NULL)",
    )
    op.drop_column("materials", "edge_width_mm")


def _regenerate_names(bind: sa.Connection) -> None:
    materials = sa.table(
        "materials",
        sa.column("id"),
        sa.column("kind"),
        sa.column("manufacturer_id"),
        sa.column("type"),
        sa.column("name"),
        sa.column("thickness_mm"),
        sa.column("color"),
        sa.column("decor_code"),
        sa.column("panel_length_mm"),
        sa.column("panel_width_mm"),
        sa.column("edge_width_mm"),
    )
    manufacturers = sa.table("manufacturers", sa.column("id"), sa.column("name"))
    rows = bind.execute(
        sa.select(materials, manufacturers.c.name.label("manufacturer_name")).select_from(
            materials.join(manufacturers, materials.c.manufacturer_id == manufacturers.c.id)
        )
    ).mappings()
    for row in rows:
        bind.execute(
            materials.update()
            .where(materials.c.id == row["id"])
            .values(name=_compose_material_name(row))
        )


def _compose_material_name(row: sa.RowMapping) -> str:
    decor_code = _optional_text(row["decor_code"])
    color = " ".join(str(row["color"]).strip().split())
    manufacturer = row["manufacturer_name"]
    thickness = _fmt_mm(row["thickness_mm"])
    if row["kind"] == "panel":
        first_parts = [_TYPE_LABELS.get(row["type"], "Panel"), manufacturer]
        if decor_code:
            first_parts.append(decor_code)
        dimensions = (
            f"{row['panel_length_mm']}{_DIMENSION_SEPARATOR}"
            f"{row['panel_width_mm']}{_DIMENSION_SEPARATOR}{thickness} mm"
        )
    else:
        first_parts = ["Kromka", manufacturer]
        if decor_code:
            first_parts.append(decor_code)
        dimensions = f"{thickness}{_DIMENSION_SEPARATOR}{row['edge_width_mm']} mm"
    return f"{' '.join(first_parts)} · {color} · {dimensions}"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).strip().split())
    return normalized or None


def _fmt_mm(value: object) -> str:
    return format(Decimal(str(value)).normalize(), "f")
