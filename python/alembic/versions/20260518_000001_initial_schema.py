"""Initial schema

Revision ID: 20260518_000001
Revises:
Create Date: 2026-05-18 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260518_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauthuser",
        sa.Column("at_hash", sa.String(), nullable=False),
        sa.Column("aud", sa.String(), nullable=False),
        sa.Column("azp", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("exp", sa.DateTime(), nullable=False),
        sa.Column("family_name", sa.String(), nullable=False),
        sa.Column("given_name", sa.String(), nullable=False),
        sa.Column("iat", sa.DateTime(), nullable=False),
        sa.Column("iss", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("picture", sa.String(), nullable=False),
        sa.Column("sub", sa.String(), nullable=False),
        sa.Column("logged_in", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("sub"),
    )
    op.create_table(
        "game",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "ACTIVE",
                "ENDED",
                "CANCELLED",
                name="gamestatus",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner"], ["oauthuser.sub"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "refreshtoken",
        sa.Column("sub", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["sub"], ["oauthuser.sub"]),
        sa.PrimaryKeyConstraint("sub"),
    )
    op.create_table(
        "player",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["game.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id"], ["oauthuser.sub"]),
        sa.PrimaryKeyConstraint("id", "game_id"),
    )
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("team_number", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["game.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner"], ["oauthuser.sub"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "id"),
        sa.UniqueConstraint("game_id", "team_number"),
    )
    op.create_table(
        "teammember",
        sa.Column("game_id", sa.String(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["game_id", "player_id"],
            ["player.game_id", "player.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["game_id", "team_id"],
            ["team.game_id", "team.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("game_id", "team_id", "player_id"),
        sa.UniqueConstraint("game_id", "player_id"),
    )


def downgrade() -> None:
    op.drop_table("teammember")
    op.drop_table("team")
    op.drop_table("player")
    op.drop_table("refreshtoken")
    op.drop_table("game")
    op.drop_table("oauthuser")
    sa.Enum(
        "CREATED",
        "ACTIVE",
        "ENDED",
        "CANCELLED",
        name="gamestatus",
    ).drop(op.get_bind(), checkfirst=True)
