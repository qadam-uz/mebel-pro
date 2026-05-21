"""Dev seed — a realistic dataset so the three apps have content to show.

    uv run python -m app.seed

Idempotent-ish: skips if the platform user 'admin' already exists. Creates a
platform operator, a workshop with an owner + one all-grants staffer, two
branches with pricing, a handful of platform materials, each branch's
selection + stock, and one client. Login passwords are simple on purpose
(dev only); ``force_password_change`` is off so you can sign straight in.
"""

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.catalog import BranchMaterial, BranchPricing, Material
from app.models.enums import (
    CatalogStatus,
    CuttingModel,
    MaterialKind,
    MaterialType,
    Permission,
    UserStatus,
)
from app.models.identity import Client, PermissionGrant, PlatformUser, WorkshopUser
from app.models.inventory import StockItem
from app.models.workshop import Branch, Workshop

HOURS = {
    d: {"open": "09:00", "close": "18:00"} for d in ("mon", "tue", "wed", "thu", "fri", "sat")
} | {"sun": {"closed": True}}


async def seed() -> None:
    async with SessionLocal() as db:
        exists = (
            await db.execute(select(PlatformUser).where(PlatformUser.login == "admin"))
        ).scalar_one_or_none()
        if exists is not None:
            print("Seed already present (platform user 'admin' exists) — skipping.")
            return

        # --- platform operator ---
        db.add(
            PlatformUser(
                login="admin",
                password_hash=hash_password("Admin123"),
                full_name="Platforma operatori",
                phone="+998901112233",
                status=UserStatus.ACTIVE,
                force_password_change=False,
            )
        )

        # --- workshop + owner ---
        ws = Workshop(name="Mebel Stil", phone="+998712001020", address="Toshkent sh.")
        db.add(ws)
        await db.flush()
        owner = WorkshopUser(
            workshop_id=ws.id,
            login="owner",
            password_hash=hash_password("Owner123"),
            full_name="Akmal Karimov",
            phone="+998901002030",
            is_owner=True,
            status=UserStatus.ACTIVE,
            force_password_change=False,
        )
        db.add(owner)
        await db.flush()
        ws.owner_user_id = owner.id

        # --- branches + pricing ---
        b1 = Branch(
            workshop_id=ws.id,
            name="Yunusobod filiali",
            address="Yunusobod, Toshkent",
            phone="+998712001021",
            latitude=41.36,
            longitude=69.29,
            working_hours=HOURS,
        )
        b2 = Branch(
            workshop_id=ws.id,
            name="Chilonzor filiali",
            address="Chilonzor, Toshkent",
            phone="+998712001022",
            latitude=41.28,
            longitude=69.20,
            working_hours=HOURS,
        )
        db.add_all([b1, b2])
        await db.flush()
        for b in (b1, b2):
            db.add(
                BranchPricing(
                    branch_id=b.id,
                    cutting_model=CuttingModel.PER_CUT,
                    cutting_rate_tiyin=150_000,  # 1 500 so'm per cut
                    edge_banding_rates={"0.4": 300_000, "2.0": 500_000},
                    updated_by_user_id=owner.id,
                )
            )

        # --- one all-grants staffer on branch 1 ---
        staff = WorkshopUser(
            workshop_id=ws.id,
            login="anvar",
            password_hash=hash_password("Anvar123"),
            full_name="Anvar To'xtayev",
            phone="+998901002031",
            is_owner=False,
            home_branch_id=b1.id,
            status=UserStatus.ACTIVE,
            force_password_change=False,
        )
        db.add(staff)
        await db.flush()
        for perm in Permission:
            db.add(
                PermissionGrant(
                    workshop_user_id=staff.id,
                    permission=perm,
                    branch_id=b1.id,
                    granted_by_user_id=owner.id,
                )
            )

        # --- platform materials ---
        dsp = Material(
            kind=MaterialKind.SHEET,
            type=MaterialType.DSP,
            name="Kronospan DSP Belyj 18mm",
            thickness_mm=18,
            color="Belyj",
            decor_code="0101 PE",
            sheet_length_mm=2800,
            sheet_width_mm=2070,
            grain_direction=True,
            status=CatalogStatus.ACTIVE,
        )
        mdf = Material(
            kind=MaterialKind.SHEET,
            type=MaterialType.MDF,
            name="MDF Krem 16mm",
            thickness_mm=16,
            color="Krem",
            sheet_length_mm=2800,
            sheet_width_mm=2070,
            grain_direction=False,
            status=CatalogStatus.ACTIVE,
        )
        edge04 = Material(
            kind=MaterialKind.EDGE,
            name="PVC kromka Belyj 0.4mm",
            thickness_mm=0.4,
            color="Belyj",
            status=CatalogStatus.ACTIVE,
        )
        edge20 = Material(
            kind=MaterialKind.EDGE,
            name="PVC kromka Belyj 2.0mm",
            thickness_mm=2.0,
            color="Belyj",
            status=CatalogStatus.ACTIVE,
        )
        db.add_all([dsp, mdf, edge04, edge20])
        await db.flush()

        # --- branch 1 carries all four; stock seeded ---
        selections = [
            (dsp, 30_000_000, 5, 24),
            (mdf, 25_000_000, 5, 14),
            (edge04, 200_000, 50, 320),
            (edge20, 250_000, 50, 180),
        ]
        for mat, price, min_stock, on_hand in selections:
            db.add(
                BranchMaterial(
                    branch_id=b1.id,
                    material_id=mat.id,
                    price_tiyin=price,
                    min_stock=min_stock,
                    status=CatalogStatus.ACTIVE,
                )
            )
            db.add(
                StockItem(branch_id=b1.id, material_id=mat.id, on_hand=on_hand, min_stock=min_stock)
            )

        # --- a client ---
        db.add(
            Client(
                telegram_id=100200300,
                phone="+998901234567",
                first_name="Dilshod",
                last_name="Rahimov",
                status=UserStatus.ACTIVE,
            )
        )

        await db.commit()
        print("Seed complete.")
        print("  Platform operator : admin / Admin123  (admin app)")
        print("  Workshop owner    : owner / Owner123  (workshop app)")
        print("  Workshop staff    : anvar / Anvar123  (workshop app, all grants on Yunusobod)")
        print("  Client            : telegram_id 100200300 (client app — dev login skips HMAC)")


if __name__ == "__main__":
    asyncio.run(seed())
