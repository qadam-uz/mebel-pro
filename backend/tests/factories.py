"""Dev/test seed helpers for foundation fixtures."""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import DekorType, MaterialStatus
from app.modules.access.contracts import PlatformUser, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Dekor, Manufacturer

# The one formula for `dekorlar.search_key`. Tests insert dekorlar straight
# through the ORM (no service call), so they must fill the key the same way
# `create_dekor` does or every search assertion silently matches nothing.
from app.modules.catalog.service import _search_key
from app.modules.workshop.api import next_branch_no
from app.modules.workshop.contracts import Branch, Workshop
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_platform_user(
    db: AsyncSession,
    *,
    login: str = "admin",
    password: str = "Admin123",
    password_reset_required: bool = True,
) -> PlatformUser:
    user = PlatformUser(
        login=login,
        password_hash=hash_password(password),
        full_name="Platform Admin",
        phone="+998901234567",
        password_reset_required=password_reset_required,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_workshop_with_owner(
    db: AsyncSession,
    *,
    login: str = "owner",
) -> tuple[Workshop, Branch, WorkshopUser]:
    """Seed a workshop with its owner. Logins are globally unique — pass a distinct
    `login` when a test seeds more than one workshop."""
    workshop_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    workshop = Workshop(
        id=workshop_id,
        owner_user_id=owner_id,
        name="Demo Workshop",
    )
    db.add(workshop)
    await db.flush()
    branch = Branch(
        workshop_id=workshop.id,
        branch_no=await next_branch_no(db),
        name="Yunusobod",
        address="Tashkent, Yunusobod",
        phone="+998902222222",
        latitude=Decimal("41.365"),
        longitude=Decimal("69.285"),
    )
    db.add(branch)
    await db.flush()
    owner = WorkshopUser(
        id=owner_id,
        workshop_id=workshop.id,
        login=login,
        password_hash=hash_password("Owner123"),
        full_name="Workshop Owner",
        phone="+998903333333",
        is_owner=True,
        home_branch_id=branch.id,
    )
    db.add(owner)
    await db.flush()
    return workshop, branch, owner


def make_search_key(*, nomi: str, kod: str | None, manufacturer_name: str) -> str:
    """`dekorlar.search_key` for a hand-built Dekor row.

    Exposed so tests that construct a `Dekor` directly (rather than through
    `seed_dekor`) still fill the key with the service's formula.
    """
    return _search_key(nomi=nomi, kod=kod, manufacturer_name=manufacturer_name)


@dataclass(frozen=True)
class MaterialFixture:
    """A seeded material as the reshaped model defines it: three rows.

    Identity is platform-owned (`manufacturer` + `dekor`), format is
    branch-owned (`branch_material`). `.id` is the branch material's — that is
    the id stock, cutting panels and order items all point at, and the one a
    request payload means when it says `material_id`.
    """

    manufacturer: Manufacturer
    dekor: Dekor
    branch_material: BranchMaterial

    @property
    def id(self) -> uuid.UUID:
        return self.branch_material.id

    @property
    def dekor_id(self) -> uuid.UUID:
        return self.dekor.id

    @property
    def tur(self) -> DekorType:
        return self.dekor.tur


async def seed_manufacturer(
    db: AsyncSession,
    *,
    name: str | None = None,
    country: str = "AT",
) -> Manufacturer:
    """A manufacturer with a collision-proof name (the name is uniquely indexed)."""
    row = Manufacturer(name=name or f"Egger {uuid.uuid4().hex[:8]}", country=country)
    db.add(row)
    await db.flush()
    return row


async def seed_dekor(
    db: AsyncSession,
    *,
    manufacturer: Manufacturer,
    tur: DekorType = DekorType.LDSP,
    kod: str | None = None,
    nomi: str = "Sonoma eman",
    tolali: bool = False,
    holat: MaterialStatus = MaterialStatus.ACTIVE,
    image_file_id: uuid.UUID | None = None,
) -> Dekor:
    row = Dekor(
        manufacturer_id=manufacturer.id,
        tur=tur,
        kod=kod,
        nomi=nomi,
        tolali=tolali,
        holat=holat,
        image_file_id=image_file_id,
        search_key=_search_key(nomi=nomi, kod=kod, manufacturer_name=manufacturer.name),
    )
    db.add(row)
    await db.flush()
    return row


async def seed_branch_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    dekor: Dekor,
    qalinlik_mm: Decimal = Decimal("18"),
    uzunlik_mm: int | None = None,
    eni_mm: int | None = None,
    kromka_eni_mm: int | None = None,
    price_tiyin: int = 0,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
) -> BranchMaterial:
    row = BranchMaterial(
        branch_id=branch_id,
        dekor_id=dekor.id,
        qalinlik_mm=qalinlik_mm,
        uzunlik_mm=uzunlik_mm,
        eni_mm=eni_mm,
        kromka_eni_mm=kromka_eni_mm,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=status,
    )
    db.add(row)
    await db.flush()
    return row


async def seed_panel_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    manufacturer: Manufacturer | None = None,
    tur: DekorType = DekorType.LDSP,
    kod: str | None = "H1334",
    nomi: str = "Sonoma eman",
    tolali: bool = False,
    qalinlik_mm: Decimal = Decimal("18"),
    uzunlik_mm: int = 2750,
    eni_mm: int = 1830,
    price_tiyin: int = 250000,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
    holat: MaterialStatus = MaterialStatus.ACTIVE,
) -> MaterialFixture:
    """A panel-shaped dekor the branch carries in one format."""
    maker = manufacturer or await seed_manufacturer(db)
    dekor = await seed_dekor(
        db, manufacturer=maker, tur=tur, kod=kod, nomi=nomi, tolali=tolali, holat=holat
    )
    branch_material = await seed_branch_material(
        db,
        branch_id=branch_id,
        dekor=dekor,
        qalinlik_mm=qalinlik_mm,
        uzunlik_mm=uzunlik_mm,
        eni_mm=eni_mm,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=status,
    )
    return MaterialFixture(manufacturer=maker, dekor=dekor, branch_material=branch_material)


async def seed_kromka_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    manufacturer: Manufacturer | None = None,
    kod: str | None = "H1334",
    nomi: str = "Sonoma eman",
    qalinlik_mm: Decimal = Decimal("0.4"),
    kromka_eni_mm: int = 19,
    price_tiyin: int = 1000,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
    holat: MaterialStatus = MaterialStatus.ACTIVE,
) -> MaterialFixture:
    """A tape-shaped dekor the branch carries in one format."""
    maker = manufacturer or await seed_manufacturer(db)
    dekor = await seed_dekor(
        db, manufacturer=maker, tur=DekorType.KROMKA, kod=kod, nomi=nomi, holat=holat
    )
    branch_material = await seed_branch_material(
        db,
        branch_id=branch_id,
        dekor=dekor,
        qalinlik_mm=qalinlik_mm,
        kromka_eni_mm=kromka_eni_mm,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=status,
    )
    return MaterialFixture(manufacturer=maker, dekor=dekor, branch_material=branch_material)
