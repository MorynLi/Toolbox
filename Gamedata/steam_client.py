import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.steampowered.com"


class SteamClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("STEAM_API_KEY")
        self.steam_id = os.getenv("STEAM_ID64")
        if not self.api_key or not self.steam_id:
            raise RuntimeError("Missing STEAM_API_KEY or STEAM_ID64 in environment/.env")
        self.session = requests.Session()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {"key": self.api_key, "steamid": self.steam_id, **params}
        response = self.session.get(f"{BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_owned_games(self) -> list[dict[str, Any]]:
        data = self._get(
            "/IPlayerService/GetOwnedGames/v1/",
            {
                "include_appinfo": 1,
                "include_played_free_games": 1,
                "format": "json",
            },
        )
        return data.get("response", {}).get("games", [])

    def get_recent_games(self, count: int = 20) -> list[dict[str, Any]]:
        data = self._get(
            "/IPlayerService/GetRecentlyPlayedGames/v1/",
            {"count": count, "format": "json"},
        )
        return data.get("response", {}).get("games", [])

    def get_achievements(
        self, appid: int, language: str = "schinese"
    ) -> Optional[list[dict[str, Any]]]:
        data = self._get(
            "/ISteamUserStats/GetPlayerAchievements/v1/",
            {"appid": appid, "l": language},
        )
        stats = data.get("playerstats", {})
        if not stats.get("success"):
            return None
        return stats.get("achievements", [])
