from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select

from database import session_scope
from models import Character, GameMessage, MemorySummary


def get_recent_game_messages(character_id: int, limit: int = 12) -> list[GameMessage]:
    with session_scope() as db_session:
        rows = db_session.scalars(
            select(GameMessage)
            .where(GameMessage.character_id == character_id)
            .order_by(GameMessage.created_at.desc(), GameMessage.id.desc())
            .limit(limit)
        ).all()
    return list(reversed(rows))


def get_latest_memory_summary(character_id: int) -> MemorySummary | None:
    with session_scope() as db_session:
        return db_session.scalar(
            select(MemorySummary)
            .where(MemorySummary.character_id == character_id)
            .order_by(MemorySummary.version.desc(), MemorySummary.id.desc())
        )


def store_game_messages(character_id: int, scene: str, player_message: str, gm_message: str) -> None:
    with session_scope() as db_session:
        db_session.add(
            GameMessage(
                character_id=character_id,
                role="player",
                content=player_message,
                scene=scene,
            )
        )
        db_session.add(
            GameMessage(
                character_id=character_id,
                role="gm",
                content=gm_message,
                scene=scene,
            )
        )


def store_gm_message(character_id: int, scene: str, gm_message: str) -> None:
    with session_scope() as db_session:
        db_session.add(
            GameMessage(
                character_id=character_id,
                role="gm",
                content=gm_message,
                scene=scene,
            )
        )


def store_player_message(character_id: int, scene: str, player_message: str) -> None:
    with session_scope() as db_session:
        db_session.add(
            GameMessage(
                character_id=character_id,
                role="player",
                content=player_message,
                scene=scene,
            )
        )


def message_count_for_character(character_id: int) -> int:
    with session_scope() as db_session:
        rows = db_session.scalars(select(GameMessage.id).where(GameMessage.character_id == character_id)).all()
    return len(rows)


def summarize_memory_if_needed(
    character: Character,
    *,
    call_llm: Callable[[list[dict]], str],
) -> None:
    recent_messages = get_recent_game_messages(character.id, limit=6)
    player_turns = [message for message in recent_messages if message.role == "player"]
    if len(player_turns) < 4:
        return

    latest_summary = get_latest_memory_summary(character.id)
    message_count = message_count_for_character(character.id)
    if latest_summary and message_count < latest_summary.version * 8:
        return
    if not latest_summary and message_count < 8:
        return

    existing_summary = latest_summary.summary_text if latest_summary else "Nenhum resumo anterior."
    summary_messages = [
        {
            "role": "system",
            "content": (
                "Resuma a memória de um jogador de RPG em português. "
                "Guarde apenas fatos duradouros: estilo do jogador, decisões, interesses, "
                "alianças, desconfianças, itens narrativos, pistas e tom emocional. "
                "Seja conciso, 6 a 10 linhas."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Resumo anterior:\n{existing_summary}\n\n"
                "Mensagens recentes:\n"
                + "\n".join(f"[{msg.role}] {msg.content}" for msg in recent_messages)
            ),
        },
    ]

    try:
        summary_text = call_llm(summary_messages)
    except RuntimeError:
        return

    next_version = (latest_summary.version + 1) if latest_summary else 1
    with session_scope() as db_session:
        db_session.add(
            MemorySummary(
                character_id=character.id,
                summary_text=summary_text,
                version=next_version,
            )
        )
