from decimal import Decimal

import pytest
from app.models.enums import AuthenticatedPrincipalType, MaterialKind, PanelMaterialType
from app.modules.access.api import create_session
from app.modules.catalog.contracts import Manufacturer, Material
from app.modules.catalog.service import compose_material_name
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import seed_platform_user

SEP = "\N{MULTIPLICATION SIGN}"


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _platform_access(db_session: AsyncSession) -> str:
    platform = await seed_platform_user(db_session, password_reset_required=False)
    tokens = await create_session(
        db_session,
        principal_type=AuthenticatedPrincipalType.PLATFORM_USER,
        principal_id=platform.id,
    )
    return tokens.access_token


async def _manufacturer(client: AsyncClient, access: str, name: str = "Egger") -> str:
    response = await client.post(
        "/api/v1/platform/catalog/manufacturers",
        headers=_auth(access),
        json={"name": name, "country": "AT"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_compose_material_name_examples() -> None:
    assert (
        compose_material_name(
            kind=MaterialKind.PANEL,
            manufacturer_name="Egger",
            type_value=PanelMaterialType.DSP,
            color="Sonoma eman",
            decor_code="H1334 ST9",
            thickness_mm=Decimal("18.0"),
            panel_length_mm=2750,
            panel_width_mm=1830,
            edge_width_mm=None,
        )
        == f"LDSP Egger H1334 ST9 · Sonoma eman · 2750{SEP}1830{SEP}18 mm"
    )
    assert (
        compose_material_name(
            kind=MaterialKind.PANEL,
            manufacturer_name="Kronospan",
            type_value=PanelMaterialType.MDF,
            color="Oq",
            decor_code=None,
            thickness_mm=Decimal("0.4"),
            panel_length_mm=2800,
            panel_width_mm=2070,
            edge_width_mm=None,
        )
        == f"MDF Kronospan · Oq · 2800{SEP}2070{SEP}0.4 mm"
    )
    assert (
        compose_material_name(
            kind=MaterialKind.EDGE,
            manufacturer_name="Egger",
            type_value=None,
            color="Sonoma eman",
            decor_code="H1145",
            thickness_mm=Decimal("2.0"),
            panel_length_mm=None,
            panel_width_mm=None,
            edge_width_mm=19,
        )
        == f"Kromka Egger H1145 · Sonoma eman · 2{SEP}19 mm"
    )


async def test_material_create_generates_name_and_validates_edge_width(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _platform_access(db_session)
    manufacturer_id = await _manufacturer(client, access)

    created = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "edge",
            "manufacturer_id": manufacturer_id,
            "name": "ignored operator input",
            "thickness_mm": "2.0",
            "color": "Sonoma eman",
            "decor_code": "H1145",
            "edge_width_mm": 19,
        },
    )
    missing_width = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "edge",
            "manufacturer_id": manufacturer_id,
            "thickness_mm": "2",
            "color": "Sonoma eman",
        },
    )
    panel_with_width = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "panel",
            "manufacturer_id": manufacturer_id,
            "type": "dsp",
            "thickness_mm": "18",
            "color": "Sonoma eman",
            "panel_length_mm": 2750,
            "panel_width_mm": 1830,
            "grain_direction": True,
            "edge_width_mm": 19,
        },
    )

    assert created.status_code == 201
    assert created.json()["name"] == f"Kromka Egger H1145 · Sonoma eman · 2{SEP}19 mm"
    assert created.json()["edge_width_mm"] == 19
    assert missing_width.status_code == 400
    assert missing_width.json()["code"] == "invalid_edge_width"
    assert panel_with_width.status_code == 400
    assert panel_with_width.json()["code"] == "invalid_panel_material"


async def test_material_patch_regenerates_name(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _platform_access(db_session)
    egger_id = await _manufacturer(client, access, "Egger Patch")
    kronospan_id = await _manufacturer(client, access, "Kronospan Patch")
    created = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "edge",
            "manufacturer_id": egger_id,
            "thickness_mm": "0.4",
            "color": "Oak",
            "decor_code": "H1334",
            "edge_width_mm": 19,
        },
    )
    assert created.status_code == 201

    patched = await client.patch(
        f"/api/v1/platform/catalog/materials/{created.json()['id']}",
        headers=_auth(access),
        json={
            "manufacturer_id": kronospan_id,
            "thickness_mm": "2",
            "color": "White",
            "edge_width_mm": 42,
        },
    )
    panel_width_patch = await client.post(
        "/api/v1/platform/catalog/materials",
        headers=_auth(access),
        json={
            "kind": "panel",
            "manufacturer_id": egger_id,
            "type": "dsp",
            "thickness_mm": "18",
            "color": "Oak",
            "panel_length_mm": 2750,
            "panel_width_mm": 1830,
            "grain_direction": True,
        },
    )
    invalid_panel_patch = await client.patch(
        f"/api/v1/platform/catalog/materials/{panel_width_patch.json()['id']}",
        headers=_auth(access),
        json={"edge_width_mm": 19},
    )

    assert patched.status_code == 200
    assert patched.json()["name"] == f"Kromka Kronospan Patch H1334 · White · 2{SEP}42 mm"
    assert invalid_panel_patch.status_code == 400
    assert invalid_panel_patch.json()["code"] == "invalid_panel_material"


async def test_material_shape_constraints_include_edge_width(db_session: AsyncSession) -> None:
    manufacturer = Manufacturer(name="Constraint Maker")
    manufacturer = Manufacturer(name="Constraint Maker 2")
    db_session.add(manufacturer)
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(Material).values(
                kind=MaterialKind.EDGE,
                manufacturer_id=manufacturer.id,
                name="Bad edge",
                thickness_mm=Decimal("2"),
                color="White",
            )
        )
        await db_session.flush()
    await db_session.rollback()

    db_session.add(manufacturer)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            insert(Material).values(
                kind=MaterialKind.PANEL,
                manufacturer_id=manufacturer.id,
                type=PanelMaterialType.DSP,
                name="Bad panel",
                thickness_mm=Decimal("18"),
                color="White",
                panel_length_mm=2800,
                panel_width_mm=2070,
                grain_direction=True,
                edge_width_mm=19,
            )
        )
        await db_session.flush()
