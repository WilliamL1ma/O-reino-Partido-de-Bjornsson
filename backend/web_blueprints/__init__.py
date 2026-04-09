from .auth import create_auth_blueprint
from .game import create_game_blueprint
from .player import create_player_blueprint

__all__ = [
    "create_auth_blueprint",
    "create_game_blueprint",
    "create_player_blueprint",
]
