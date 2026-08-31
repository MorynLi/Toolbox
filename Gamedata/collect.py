import json
from datetime import datetime, timezone
from pathlib import Path

from steam_client import SteamClient

OUTPUT = Path(__file__).parent / "data" / "steam_library.json"


def classify_playtime(hours: float) -> str:
    if hours < 0.2:
        return "unplayed"
    if hours < 2:
        return "barely_played"
    if hours < 10:
        return "sampled"
    if hours < 40:
        return "played"
    return "deeply_played"


def main() -> None:
    client = SteamClient()
    games = client.get_owned_games()

    library = []
    for game in games:
        hours = round(game.get("playtime_forever", 0) / 60, 1)
        recent_hours = round(game.get("playtime_2weeks", 0) / 60, 1)
        last_played = game.get("rtime_last_played")

        library.append(
            {
                "appid": game["appid"],
                "name": game.get("name", ""),
                "playtime_hours": hours,
                "recent_hours": recent_hours,
                "last_played": last_played,
                "status": classify_playtime(hours),
            }
        )

    library.sort(key=lambda item: item["playtime_hours"], reverse=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "game_count": len(library),
        "games": library,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Collected {len(library)} games -> {OUTPUT}")


if __name__ == "__main__":
    main()
