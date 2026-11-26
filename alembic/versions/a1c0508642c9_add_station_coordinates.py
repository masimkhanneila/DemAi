"""add station coordinates

Revision ID: a1c0508642c9
Revises: 1c3f9324f32b
Create Date: 2026-11-26 18:12:20.952603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c0508642c9'
down_revision: Union[str, Sequence[str], None] = '1c3f9324f32b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable on purpose: existing stations have no coordinates, so a NOT NULL
    # column would make this migration fail on a database that already has data.
    op.add_column('stations', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('stations', sa.Column('longitude', sa.Float(), nullable=True))

    # Autogenerate does not detect CHECK constraints, so they are written by hand.
    # They allow NULL, so existing rows pass them.
    op.create_check_constraint(
        'ck_stations_latitude_range', 'stations',
        'latitude IS NULL OR (latitude >= -90 AND latitude <= 90)',
    )
    op.create_check_constraint(
        'ck_stations_longitude_range', 'stations',
        'longitude IS NULL OR (longitude >= -180 AND longitude <= 180)',
    )
    op.create_check_constraint(
        'ck_stations_coordinates_pair', 'stations',
        '(latitude IS NULL) = (longitude IS NULL)',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_stations_coordinates_pair', 'stations', type_='check')
    op.drop_constraint('ck_stations_longitude_range', 'stations', type_='check')
    op.drop_constraint('ck_stations_latitude_range', 'stations', type_='check')
    op.drop_column('stations', 'longitude')
    op.drop_column('stations', 'latitude')