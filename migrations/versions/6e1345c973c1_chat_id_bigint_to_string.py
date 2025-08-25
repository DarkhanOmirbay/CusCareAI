from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6e1345c973c1'
down_revision: str = '6cfdf63981a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Удаляем FK
    op.drop_constraint('messages_chat_id_fkey', 'messages', type_='foreignkey')

    # 2. Меняем типы
    op.alter_column('chats', 'chat_id',
                    existing_type=sa.BIGINT(),
                    type_=sa.String(),
                    existing_nullable=False)

    op.alter_column('messages', 'chat_id',
                    existing_type=sa.BIGINT(),
                    type_=sa.String(),
                    existing_nullable=True)

    # 3. Создаём FK обратно
    op.create_foreign_key(
        'messages_chat_id_fkey',
        source_table='messages',
        referent_table='chats',
        local_cols=['chat_id'],
        remote_cols=['chat_id'],
    )


def downgrade() -> None:
    # 1. Удаляем FK
    op.drop_constraint('messages_chat_id_fkey', 'messages', type_='foreignkey')

    # 2. Возвращаем BIGINT
    op.alter_column('messages', 'chat_id',
                    existing_type=sa.String(),
                    type_=sa.BIGINT(),
                    existing_nullable=True)

    op.alter_column('chats', 'chat_id',
                    existing_type=sa.String(),
                    type_=sa.BIGINT(),
                    existing_nullable=False)

    # 3. Создаём FK обратно
    op.create_foreign_key(
        'messages_chat_id_fkey',
        source_table='messages',
        referent_table='chats',
        local_cols=['chat_id'],
        remote_cols=['chat_id'],
    )
