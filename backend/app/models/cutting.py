"""Cutting models — drafts (mutable) and results/sheets/placements (immutable).

Spec: docs/ref/entities/cutting.md.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey
from app.models.enums import CuttingResultStatus


class CuttingDraft(UUIDPrimaryKey, Base):
    """The client's editable workspace for one set of parts. Private; no expiry."""

    __tablename__ = "cutting_draft"

    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("client.id"), index=True)
    # list of parts: part_ref, material_id, material_source, length_mm, width_mm,
    # quantity, edge_{top,bottom,left,right}_mm
    parts_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    chosen_result_id: Mapped[uuid.UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CuttingResult(UUIDPrimaryKey, Base):
    """The output of one algorithm on a draft's parts. Immutable after creation."""

    __tablename__ = "cutting_result"

    draft_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cutting_draft.id"), index=True)
    algorithm_name: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(String(16))
    status: Mapped[CuttingResultStatus] = mapped_column(
        Enum(CuttingResultStatus, native_enum=False, length=16),
        default=CuttingResultStatus.CANDIDATE,
    )
    kerf_mm: Mapped[int] = mapped_column(Integer)
    edge_trim_mm: Mapped[int] = mapped_column(Integer)
    # {"<material_id>": sheet_count}
    sheets_used_by_material: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    waste_percentage: Mapped[float] = mapped_column(Numeric(6, 4))
    total_cut_length_mm: Mapped[int] = mapped_column(Integer, default=0)
    total_edge_length_mm: Mapped[int] = mapped_column(Integer, default=0)
    # {"0.4": metres_in_mm, "2.0": ...}
    edge_length_by_thickness: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    order_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CuttingSheet(UUIDPrimaryKey, Base):
    """One physical sheet within a result — its material, index, and waste."""

    __tablename__ = "cutting_sheet"

    cutting_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cutting_result.id"), index=True
    )
    material_id: Mapped[uuid.UUID] = mapped_column()
    sheet_index: Mapped[int] = mapped_column(Integer)  # 1..N within the material
    waste_area_mm2: Mapped[int] = mapped_column(BigInteger, default=0)


class CuttingPlacement(UUIDPrimaryKey, Base):
    """One placed part-instance on one sheet."""

    __tablename__ = "cutting_placement"

    cutting_sheet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cutting_sheet.id"), index=True)
    part_ref: Mapped[str] = mapped_column(String(64))
    part_quantity_index: Mapped[int] = mapped_column(Integer, default=1)
    x_mm: Mapped[int] = mapped_column(Integer)
    y_mm: Mapped[int] = mapped_column(Integer)
    length_mm: Mapped[int] = mapped_column(Integer)
    width_mm: Mapped[int] = mapped_column(Integer)
    rotated: Mapped[bool] = mapped_column(Boolean, default=False)
