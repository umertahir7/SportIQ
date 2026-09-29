from app.services.database_service import DatabaseService
from app.services.user_context import get_current_user_id


class WatchlistService:
    """Manage the current user's teams and players."""

    def __init__(self, user_id=None, database=None):
        self.user_id = user_id
        self.database = database or DatabaseService()

    def _get_user_id(self):
        """Return the explicitly supplied or current context user ID."""

        user_id = self.user_id

        if user_id is None:
            user_id = get_current_user_id()

        if user_id is None:
            raise RuntimeError(
                "No active user is set for the watchlist."
            )

        return user_id

    def add_team(self, team):
        """Add a team to the current user's watchlist."""

        return self.database.add_team(
            user_id=self._get_user_id(),
            team=team,
        )

    def remove_team(self, team_id):
        """Remove a team from the current user's watchlist."""

        return self.database.remove_team(
            user_id=self._get_user_id(),
            team_id=team_id,
        )

    def get_teams(self):
        """Return all teams in the current user's watchlist."""

        return self.database.get_teams(
            user_id=self._get_user_id(),
        )

    def get_team(self, team_id):
        """Find a specific team in the current user's watchlist."""

        teams = self.get_teams()

        for team in teams:
            if team.get("id") == team_id:
                return team

        return None

    def add_player(self, player):
        """Add a player to the current user's watchlist."""

        return self.database.add_player(
            user_id=self._get_user_id(),
            player=player,
        )

    def remove_player(self, player_id):
        """Remove a player from the current user's watchlist."""

        return self.database.remove_player(
            user_id=self._get_user_id(),
            player_id=player_id,
        )

    def get_players(self):
        """Return all players in the current user's watchlist."""

        return self.database.get_players(
            user_id=self._get_user_id(),
        )

    def get_player(self, player_id):
        """Find a specific player in the current user's watchlist."""

        players = self.get_players()

        for player in players:
            if player.get("id") == player_id:
                return player

        return None

    def clear_teams(self):
        """Remove all teams from the current user's watchlist."""

        for team in self.get_teams():
            self.remove_team(team.get("id"))

    def clear_players(self):
        """Remove all players from the current user's watchlist."""

        for player in self.get_players():
            self.remove_player(player.get("id"))

    def count_teams(self):
        """Return the number of watched teams."""

        return len(self.get_teams())

    def count_players(self):
        """Return the number of watched players."""

        return len(self.get_players())