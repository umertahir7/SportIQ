from typing import Any

from mcp.server import MCPServer
from app.tools.sports_tools import SportsTools

mcp = MCPServer("AI Sports Agent")
sports = SportsTools()


@mcp.tool()
def get_watchlist() -> list[dict[str, Any]]:
    return sports.get_watchlist()


@mcp.tool()
def search_teams(team_name: str) -> dict[str, Any]:
    return sports.search_teams(team_name=team_name)


@mcp.tool()
def add_team_to_watchlist(team_id: int) -> dict[str, Any]:
    return sports.add_team(team_id=team_id)


@mcp.tool()
def remove_team_from_watchlist(team_name: str) -> dict[str, Any]:
    return sports.remove_team(team_name=team_name)


@mcp.tool()
def get_upcoming_matches(
    team_name: str,
    league_id: int | None = None,
) -> dict[str, Any]:
    return sports.get_upcoming_matches(
        team_name=team_name,
        league_id=league_id,
    )


@mcp.tool()
def get_live_matches() -> dict[str, Any]:
    return sports.get_live_matches()


@mcp.tool()
def get_team_news(team_name: str) -> dict[str, Any]:
    return sports.get_team_news(team_name)


@mcp.tool()
def get_team_squad(team_name: str) -> dict[str, Any]:
    return sports.get_team_squad(team_name)


@mcp.tool()
def get_team_manager(team_name: str) -> dict[str, Any]:
    return sports.get_team_manager(team_name)


@mcp.tool()
def get_team_transfers(team_name: str) -> dict[str, Any]:
    return sports.get_team_transfers(team_name)


@mcp.tool()
def search_managers(manager_name: str) -> dict[str, Any]:
    return sports.search_managers(manager_name=manager_name)


@mcp.tool()
def search_players(player_name: str) -> dict[str, Any]:
    return sports.search_players(player_name=player_name)


@mcp.tool()
def get_player_stats(
    player_name: str,
    season_id: int | None = None,
    team_id: int | None = None,
    league_id: int | None = None,
) -> dict[str, Any]:
    return sports.get_player_stats(
        player_name=player_name,
        season_id=season_id,
        team_id=team_id,
        league_id=league_id,
    )


@mcp.tool()
def get_top_scorers(
    team_name: str,
    league_id: int | None = None,
) -> dict[str, Any]:
    return sports.get_top_scorers(
        team_name=team_name,
        league_id=league_id,
    )


@mcp.tool()
def get_team_results(
    team_name: str,
    league_id: int | None = None,
) -> dict[str, Any]:
    return sports.get_team_results(
        team_name=team_name,
        league_id=league_id,
    )


@mcp.tool()
def get_match_details(
    event_id: int,
    include_lineups: bool = False,
) -> dict[str, Any]:
    """
    Return detailed BSD match data, including incidents and optional
    lineups. Used for goal scorers, substitutions, and participation.
    """
    return sports.get_match_details(
        event_id=event_id,
        include_lineups=include_lineups,
    )


@mcp.tool()
def get_league_table(league_id: int, league_name: str | None = None) -> dict[str, Any]:
    return sports.get_league_table(
        league_id=league_id,
        league_name=league_name,
    )


@mcp.tool()
def get_league_standings(
    team_name: str,
    league_id: int | None = None,
) -> dict[str, Any]:
    return sports.get_league_standings(
        team_name=team_name,
        league_id=league_id,
    )


@mcp.tool()
def get_match_broadcasts(
    event_id: int,
    country_code: str | None = None,
) -> dict[str, Any]:
    return sports.get_match_broadcasts(
        event_id=event_id,
        country_code=country_code,
    )


@mcp.tool()
def get_match_social(
    event_id: int,
    limit: int = 10,
) -> dict[str, Any]:
    return sports.get_match_social(
        event_id=event_id,
        limit=limit,
    )


@mcp.tool()
def get_team_social(
    team_name: str,
    limit: int = 10,
) -> dict[str, Any]:
    return sports.get_team_social(
        team_name=team_name,
        limit=limit,
    )


@mcp.tool()
def get_match_h2h(event_id: int) -> dict[str, Any]:
    return sports.get_match_h2h(
        fixture_id=event_id
    )


@mcp.tool()
def monitor_match(
    home_team: str,
    away_team: str,
    match_date: str | None = None,
) -> dict[str, Any]:
    """
    Resolve and monitor one specific football match.

    Calling the tool again refreshes the match state, including score,
    status, incidents, stats, broadcasts, and social posts when available.
    """
    return sports.monitor_match(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
    )


if __name__ == "__main__":
    mcp.run()