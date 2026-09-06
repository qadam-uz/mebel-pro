"""Dev/test seed helpers for foundation fixtures."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.core.security import hash_password
from app.models.enums import DecorType, MaterialStatus, ProductionMode
from app.modules.access.contracts import PlatformUser, WorkshopUser
from app.modules.catalog.contracts import BranchMaterial, Decor, DecorFormat, Manufacturer

# The one formula for `decors.search_key`. Tests insert decors straight
# through the ORM (no service call), so they must fill the key the same way
# `create_decor` does or every search assertion silently matches nothing.
from app.modules.catalog.service import _recompute_decor_search_key, _search_key
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
    production_mode: ProductionMode = ProductionMode.FULL,
) -> tuple[Workshop, Branch, WorkshopUser]:
    """Seed a workshop with its owner. Logins are globally unique — pass a distinct
    `login` when a test seeds more than one workshop.

    The branch is seeded in **full** mode purely as a test convenience: the
    per-step choreography is what most of this suite exercises, and defaulting to
    it keeps those tests from opting in one by one. It deliberately does NOT
    mirror production, where every branch — provisioned or new — is `simple`
    (the migration has no backfill). A simple-mode test asks for it explicitly.
    """
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
        production_mode=production_mode,
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


def make_search_key(
    *,
    name: str,
    code: str | None,
    manufacturer_name: str,
    type_words: Sequence[str] = (),
) -> str:
    """`decors.search_key` for a hand-built Decor row.

    Exposed so tests that construct a `Decor` directly (rather than through
    `seed_decor`) still fill the key with the service's formula.
    """
    return _search_key(
        name=name,
        code=code,
        manufacturer_name=manufacturer_name,
        type_words=type_words,
    )


@dataclass(frozen=True)
class MaterialFixture:
    """A seeded material as the reshaped model defines it: four rows.

    The platform owns the pattern (`manufacturer` + `decor`) and the product
    (`decor_format`); the branch owns only the decision to carry it
    (`branch_material`). `.id` is the branch material's — that is the id stock,
    cutting panels and order items all point at, and the one a request payload
    means when it says `material_id`.
    """

    manufacturer: Manufacturer
    decor: Decor
    decor_format: DecorFormat
    branch_material: BranchMaterial

    @property
    def id(self) -> uuid.UUID:
        return self.branch_material.id

    @property
    def decor_id(self) -> uuid.UUID:
        return self.decor.id

    @property
    def decor_format_id(self) -> uuid.UUID:
        return self.decor_format.id

    @property
    def type(self) -> DecorType:
        return self.decor_format.type


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


async def seed_decor(
    db: AsyncSession,
    *,
    manufacturer: Manufacturer,
    code: str | None = None,
    name: str = "Sonoma eman",
    has_grain: bool = False,
    status: MaterialStatus = MaterialStatus.ACTIVE,
    image_file_id: uuid.UUID | None = None,
) -> Decor:
    """A decor pattern. No substrate — that belongs to its formats."""
    row = Decor(
        manufacturer_id=manufacturer.id,
        code=code,
        name=name,
        has_grain=has_grain,
        status=status,
        image_file_id=image_file_id,
        search_key=_search_key(name=name, code=code, manufacturer_name=manufacturer.name),
    )
    db.add(row)
    await db.flush()
    return row


async def seed_decor_format(
    db: AsyncSession,
    *,
    decor: Decor,
    type: DecorType = DecorType.LDSP,
    thickness_mm: Decimal = Decimal("18"),
    length_mm: int | None = 2750,
    width_mm: int | None = 1830,
    tape_width_mm: int | None = None,
    finished_sides: int | None = None,
    status: MaterialStatus = MaterialStatus.ACTIVE,
) -> DecorFormat:
    """One concrete product of a decor.

    `finished_sides` defaults to the two-sided norm for the board types and to
    NULL for everything else, so a caller that does not care about it still
    produces a row the shape CHECK accepts.
    """
    if finished_sides is None and type in (DecorType.LDSP, DecorType.DSP, DecorType.MDF):
        finished_sides = 2
    row = DecorFormat(
        decor_id=decor.id,
        type=type,
        thickness_mm=thickness_mm,
        length_mm=length_mm,
        width_mm=width_mm,
        tape_width_mm=tape_width_mm,
        finished_sides=finished_sides,
        status=status,
    )
    db.add(row)
    await db.flush()
    # The decor's key carries the substrate words of its active formats, and the
    # service rebuilds it on every format write — a fixture that skipped this
    # would make «ldsp sonoma» findable in production and not in the tests.
    manufacturer = await db.get(Manufacturer, decor.manufacturer_id)
    if manufacturer is not None:
        await _recompute_decor_search_key(db, decor, manufacturer.name)
    return row


async def seed_branch_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    decor_format: DecorFormat,
    price_tiyin: int = 0,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
) -> BranchMaterial:
    """The branch's decision to carry one platform format, at its own price."""
    row = BranchMaterial(
        branch_id=branch_id,
        decor_format_id=decor_format.id,
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
    decor: Decor | None = None,
    type: DecorType = DecorType.LDSP,
    code: str | None = "H1334",
    name: str = "Sonoma eman",
    has_grain: bool = False,
    thickness_mm: Decimal = Decimal("18"),
    length_mm: int = 2750,
    width_mm: int = 1830,
    finished_sides: int | None = None,
    price_tiyin: int = 250000,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
    decor_status: MaterialStatus = MaterialStatus.ACTIVE,
    format_status: MaterialStatus = MaterialStatus.ACTIVE,
) -> MaterialFixture:
    """A panel-shaped format the branch carries.

    Pass `decor` to hang a second format off an existing pattern — a board and
    its matching kromka are two formats of ONE decor now, which is the case
    worth exercising.
    """
    maker = manufacturer or (
        await seed_manufacturer(db) if decor is None else await _manufacturer_of(db, decor)
    )
    pattern = decor or await seed_decor(
        db, manufacturer=maker, code=code, name=name, has_grain=has_grain, status=decor_status
    )
    decor_format = await seed_decor_format(
        db,
        decor=pattern,
        type=type,
        thickness_mm=thickness_mm,
        length_mm=length_mm,
        width_mm=width_mm,
        finished_sides=finished_sides,
        status=format_status,
    )
    branch_material = await seed_branch_material(
        db,
        branch_id=branch_id,
        decor_format=decor_format,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=status,
    )
    return MaterialFixture(
        manufacturer=maker,
        decor=pattern,
        decor_format=decor_format,
        branch_material=branch_material,
    )


async def seed_kromka_material(
    db: AsyncSession,
    *,
    branch_id: uuid.UUID,
    manufacturer: Manufacturer | None = None,
    decor: Decor | None = None,
    code: str | None = "H1334",
    name: str = "Sonoma eman",
    thickness_mm: Decimal = Decimal("0.4"),
    tape_width_mm: int = 19,
    price_tiyin: int = 1000,
    min_stock: int = 0,
    status: MaterialStatus = MaterialStatus.ACTIVE,
    decor_status: MaterialStatus = MaterialStatus.ACTIVE,
    format_status: MaterialStatus = MaterialStatus.ACTIVE,
) -> MaterialFixture:
    """A tape-shaped format the branch carries."""
    maker = manufacturer or (
        await seed_manufacturer(db) if decor is None else await _manufacturer_of(db, decor)
    )
    pattern = decor or await seed_decor(
        db, manufacturer=maker, code=code, name=name, status=decor_status
    )
    decor_format = await seed_decor_format(
        db,
        decor=pattern,
        type=DecorType.KROMKA,
        thickness_mm=thickness_mm,
        length_mm=None,
        width_mm=None,
        tape_width_mm=tape_width_mm,
        status=format_status,
    )
    branch_material = await seed_branch_material(
        db,
        branch_id=branch_id,
        decor_format=decor_format,
        price_tiyin=price_tiyin,
        min_stock=min_stock,
        status=status,
    )
    return MaterialFixture(
        manufacturer=maker,
        decor=pattern,
        decor_format=decor_format,
        branch_material=branch_material,
    )


async def _manufacturer_of(db: AsyncSession, decor: Decor) -> Manufacturer:
    row = await db.get(Manufacturer, decor.manufacturer_id)
    assert row is not None
    return row
