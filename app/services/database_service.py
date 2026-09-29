import os
import sqlite3


class DatabaseService:
    """SQLite database service for SportIQ users and watchlists."""

    def __init__(self, database_path="data/sportiq.db"):
        self.database_path = database_path

        folder = os.path.dirname(self.database_path)

        if folder:
            os.makedirs(folder, exist_ok=True)

        self._initialize_database()

    def _connect(self):
        """Create a database connection."""

        return sqlite3.connect(self.database_path)

    def _initialize_database(self):
        """Create the database tables if they do not exist."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist_teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    team_name TEXT NOT NULL,
                    league_id INTEGER,
                    league_name TEXT,
                    country TEXT,
                    FOREIGN KEY (user_id)
                        REFERENCES users(id),
                    UNIQUE(user_id, team_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    player_name TEXT NOT NULL,
                    team_id INTEGER,
                    team_name TEXT,
                    country TEXT,
                    FOREIGN KEY (user_id)
                        REFERENCES users(id),
                    UNIQUE(user_id, player_id)
                )
                """
            )

            connection.commit()

    def get_or_create_user(self, username):
        """Return an existing user or create a new one."""

        username = username.strip()

        if not username:
            raise ValueError("Username cannot be empty.")

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT id, username
                FROM users
                WHERE username = ?
                """,
                (username,),
            )

            user = cursor.fetchone()

            if user:
                return {
                    "id": user[0],
                    "username": user[1],
                }

            cursor.execute(
                """
                INSERT INTO users (username)
                VALUES (?)
                """,
                (username,),
            )

            user_id = cursor.lastrowid

            connection.commit()

            return {
                "id": user_id,
                "username": username,
            }

    def add_team(self, user_id, team):
        """Add a team to a user's watchlist."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO watchlist_teams (
                    user_id,
                    team_id,
                    team_name,
                    league_id,
                    league_name,
                    country
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    team.get("id"),
                    team.get("name"),
                    team.get("league_id"),
                    team.get("league_name"),
                    team.get("country"),
                ),
            )

            connection.commit()

            return cursor.rowcount > 0

    def remove_team(self, user_id, team_id):
        """Remove a team from a user's watchlist."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                DELETE FROM watchlist_teams
                WHERE user_id = ?
                AND team_id = ?
                """,
                (user_id, team_id),
            )

            connection.commit()

            return cursor.rowcount > 0

    def get_teams(self, user_id):
        """Return all teams belonging to a user."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    team_id,
                    team_name,
                    league_id,
                    league_name,
                    country
                FROM watchlist_teams
                WHERE user_id = ?
                ORDER BY team_name
                """,
                (user_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "league_id": row[2],
                "league_name": row[3],
                "country": row[4],
            }
            for row in rows
        ]

    def add_player(self, user_id, player):
        """Add a player to a user's watchlist."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO watchlist_players (
                    user_id,
                    player_id,
                    player_name,
                    team_id,
                    team_name,
                    country
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    player.get("id"),
                    player.get("name"),
                    player.get("team_id"),
                    player.get("team_name"),
                    player.get("country"),
                ),
            )

            connection.commit()

            return cursor.rowcount > 0

    def remove_player(self, user_id, player_id):
        """Remove a player from a user's watchlist."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                DELETE FROM watchlist_players
                WHERE user_id = ?
                AND player_id = ?
                """,
                (user_id, player_id),
            )

            connection.commit()

            return cursor.rowcount > 0

    def get_players(self, user_id):
        """Return all players belonging to a user."""

        with self._connect() as connection:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    player_id,
                    player_name,
                    team_id,
                    team_name,
                    country
                FROM watchlist_players
                WHERE user_id = ?
                ORDER BY player_name
                """,
                (user_id,),
            )

            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "team_id": row[2],
                "team_name": row[3],
                "country": row[4],
            }
            for row in rows
        ]