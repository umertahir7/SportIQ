import requests
from datetime import datetime, timezone

from app.config import SEASON
from app.services.kickoff_service import KickoffService
from app.services.news_service import NewsService
from app.services.team_resolver import TeamResolver
from app.services.watchlist_service import WatchlistService
from app.services.timezone_service import TimezoneService
from app.services.notification_service import NotificationService
from app.services.match_monitor_service import MatchMonitorService


class SportsAgent:

    def __init__(self):
        self.football = KickoffService()
        self.news = NewsService()
        self.resolver = TeamResolver(self.football)
        self.watchlist = WatchlistService()
        self.timezone = TimezoneService()
        self.notifications = NotificationService()

        self.monitor = MatchMonitorService(
            self.football,
            self.notifications,
            self.timezone
        )

    # ==========================================================
    # HELPERS
    # ==========================================================

    def section(self, title):
        print(
            f"\n{'=' * 70}\n"
            f"{title}\n"
            f"{'=' * 70}"
        )

    def teams(self):
        teams = self.watchlist.get_teams()

        if not teams:
            print("Your watchlist is empty.")

        return teams

    def parse_date(self, value):
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except (
            ValueError,
            TypeError,
            AttributeError
        ):
            return None

    def find_watchlist_team(self, team_name):
        """
        Find a watched team by exact or partial name.
        """
        teams = self.watchlist.get_teams()

        for team in teams:
            if team.get(
                "name",
                ""
            ).lower() == team_name.lower():
                return team

        for team in teams:
            stored_name = team.get(
                "name",
                ""
            ).lower()

            if (
                team_name.lower() in stored_name
                or stored_name in team_name.lower()
            ):
                return team

        return None

    # ==========================================================
    # ADD TEAM
    # ==========================================================

    def add_team(self):
        self.section("TEAM ONBOARDING")

        name = input(
            "What team do you want to follow? "
        ).strip()

        if not name:
            print("No team entered.")
            return

        search_name = self.resolver.resolve_alias(name)

        if search_name != name:
            print(
                f"\nAlias detected: "
                f"{name} -> {search_name}"
            )

        try:
            data = self.football.search_teams(
                search_name
            )
        except requests.RequestException as error:
            print(
                f"Could not search for teams: "
                f"{error}"
            )
            return

        teams = data.get("response", [])

        if not teams:
            print("No teams found.")
            return

        matches = self.resolver.rank_teams(
            search_name,
            teams
        )[:3]

        print(f"\nFound {len(teams)} teams.\n")
        print("BEST MATCHES")
        print("-" * 70)

        for i, item in enumerate(matches, 1):
            team = item["team"]

            print(
                f"{i}. "
                f"{team.get('name', 'Unknown')} | "
                f"ID: {team.get('id', 'Unknown')} | "
                f"Country: "
                f"{team.get('countryName', 'Unknown')} | "
                f"Score: {item['score']}"
            )

        while True:
            choice = input(
                "\nSelect a team number "
                "(Enter = #1): "
            ).strip()

            if not choice:
                index = 0
                break

            if (
                choice.isdigit()
                and 1 <= int(choice) <= len(matches)
            ):
                index = int(choice) - 1
                break

            print(
                "Please choose a valid team number."
            )

        selected = matches[index]["team"]

        team = {
            "id": selected.get("id"),
            "name": selected.get("name"),
            "countryName": selected.get(
                "countryName"
            ),
            "score": matches[index].get("score")
        }

        added = self.watchlist.add_team(team)

        print(
            f"\nTeam selected: "
            f"{team['name']}"
        )

        if added:
            print(
                "✅ Team added to watchlist."
            )

            self.monitor.schedule_team_reminders(
                team,
                SEASON
            )

        else:
            print(
                "ℹ️ Team is already in your "
                "watchlist."
            )

    # ==========================================================
    # WATCHLIST
    # ==========================================================

    def show_watchlist(self):
        self.section("MY WATCHLIST")

        teams = self.teams()

        if not teams:
            return

        for i, team in enumerate(teams, 1):
            print(
                f"{i}. "
                f"{team.get('name', 'Unknown')} | "
                f"ID: {team.get('id', 'Unknown')} | "
                f"Country: "
                f"{team.get('countryName', team.get('country', 'Unknown'))}"
            )

    # ==========================================================
    # UPCOMING FIXTURES
    # ==========================================================

    def show_upcoming(self):
        self.section("UPCOMING FIXTURES")

        teams = self.teams()

        if not teams:
            return

        now = datetime.now(timezone.utc)

        print(
            f"Your local timezone: "
            f"{self.timezone.get_timezone_name()}"
        )

        for team in teams:
            team_id = team.get("id")
            team_name = team.get(
                "name",
                "Unknown"
            )

            print(
                f"\n{team_name} "
                f"(ID: {team_id})"
            )

            print("-" * 50)

            try:
                data = self.football.get_fixtures(
                    team_id,
                    SEASON
                )
            except requests.RequestException as error:
                print(
                    f"Could not retrieve fixtures: "
                    f"{error}"
                )
                continue

            upcoming = []

            for fixture in data.get(
                "response",
                []
            ):
                home = fixture.get(
                    "homeTeam",
                    {}
                )

                away = fixture.get(
                    "awayTeam",
                    {}
                )

                if team_id not in (
                    home.get("id"),
                    away.get("id")
                ):
                    continue

                date = self.parse_date(
                    fixture.get("date")
                )

                if date and date > now:
                    upcoming.append(
                        fixture
                    )

            upcoming.sort(
                key=lambda x: x.get(
                    "timestamp",
                    0
                )
            )

            print(
                f"Upcoming fixtures: "
                f"{len(upcoming)}"
            )

            if not upcoming:
                print(
                    "No upcoming fixtures found."
                )
                continue

            for fixture in upcoming[:5]:
                home = fixture.get(
                    "homeTeam",
                    {}
                ).get(
                    "name",
                    "Unknown"
                )

                away = fixture.get(
                    "awayTeam",
                    {}
                ).get(
                    "name",
                    "Unknown"
                )

                date = self.parse_date(
                    fixture.get("date")
                )

                formatted = (
                    self.timezone.format_datetime(
                        date
                    )
                    if date
                    else fixture.get(
                        "date",
                        "Unknown"
                    )
                )

                print(
                    f"\n⚽ {home} vs {away}"
                )

                print(
                    f"📅 {formatted}"
                )

                print(
                    f"🏆 "
                    f"{fixture.get('round', 'Unknown')}"
                )

    # ==========================================================
    # COMPLETED RESULTS
    # ==========================================================

    def show_results(self):
        self.section("RECENT RESULTS")

        teams = self.teams()

        if not teams:
            return

        print(
            f"Your local timezone: "
            f"{self.timezone.get_timezone_name()}"
        )

        for team in teams:
            team_id = team.get("id")
            team_name = team.get(
                "name",
                "Unknown"
            )

            print(
                f"\n{team_name} "
                f"(ID: {team_id})"
            )

            print("-" * 70)

            league_id = team.get("league_id")

            try:
                season_id = None

                if league_id:
                    season = (
                        self.football.get_bsd_current_season(
                            league_id
                        )
                    )

                    season_id = season.get("id")

                data = self.football.get_bsd_results(
                    team_id=team_id,
                    season_id=season_id,
                    league_id=league_id,
                    limit=200
                )

            except (
                requests.RequestException,
                RuntimeError,
                ValueError
            ) as error:
                print(
                    f"Could not retrieve results: "
                    f"{error}"
                )
                continue

            results = data.get(
                "results",
                []
            )

            if not results:
                print(
                    "No completed results found."
                )
                continue

            print(
                f"Completed matches: "
                f"{len(results)}"
            )

            for match in results[:10]:
                home = match.get(
                    "home_team",
                    "Unknown"
                )

                away = match.get(
                    "away_team",
                    "Unknown"
                )

                home_score = match.get(
                    "home_score"
                )

                away_score = match.get(
                    "away_score"
                )

                date_value = match.get(
                    "date"
                )

                date = self.parse_date(
                    date_value
                )

                formatted = (
                    self.timezone.format_datetime(
                        date
                    )
                    if date
                    else date_value or "Unknown"
                )

                print(
                    f"\n⚽ {home} "
                    f"{home_score if home_score is not None else '-'}"
                    f" - "
                    f"{away_score if away_score is not None else '-'} "
                    f"{away}"
                )

                print(
                    f"📅 {formatted}"
                )

                competition = match.get(
                    "competition"
                )

                if isinstance(competition, dict):
                    competition_name = (
                        competition.get("name")
                        or competition.get("display_name")
                        or "Unknown competition"
                    )
                else:
                    competition_name = (
                        competition
                        or "Unknown competition"
                    )

                print(
                    f"🏆 {competition_name}"
                )

                if match.get("round"):
                    print(
                        f"🔄 {match.get('round')}"
                    )

    # ==========================================================
    # LEAGUE STANDINGS
    # ==========================================================

    def show_standings(self):
        self.section("LEAGUE STANDINGS")

        teams = self.teams()

        if not teams:
            return

        for team in teams:
            team_id = team.get("id")
            team_name = team.get(
                "name",
                "Unknown"
            )

            print(
                f"\n{team_name}"
            )

            print("-" * 70)

            league_id = team.get("league_id")

            if not league_id:
                print(
                    "No league information is stored "
                    "for this team."
                )
                continue

            try:
                data = self.football.get_bsd_standings(
                    league_id=league_id
                )

            except (
                requests.RequestException,
                RuntimeError,
                ValueError
            ) as error:
                print(
                    f"Could not retrieve standings: "
                    f"{error}"
                )
                continue

            standings = data.get(
                "standings",
                []
            )

            if not standings:
                print(
                    "No standings found."
                )
                continue

            team_row = None

            for row in standings:
                if row.get(
                    "team_id"
                ) == team_id:
                    team_row = row
                    break

            if team_row:
                print(
                    f"\n📊 {team_name}"
                )

                print(
                    f"Position: "
                    f"{team_row.get('position', 'N/A')}"
                )

                print(
                    f"Points: "
                    f"{team_row.get('points', 'N/A')}"
                )

                print(
                    f"Played: "
                    f"{team_row.get('played', 'N/A')}"
                )

                print(
                    f"Wins: "
                    f"{team_row.get('wins', 'N/A')}"
                )

                print(
                    f"Draws: "
                    f"{team_row.get('draws', 'N/A')}"
                )

                print(
                    f"Losses: "
                    f"{team_row.get('losses', 'N/A')}"
                )

                print(
                    f"Goals For: "
                    f"{team_row.get('goals_for', 'N/A')}"
                )

                print(
                    f"Goals Against: "
                    f"{team_row.get('goals_against', 'N/A')}"
                )

                print(
                    f"Goal Difference: "
                    f"{team_row.get('goal_difference', 'N/A')}"
                )

                if team_row.get("form"):
                    print(
                        f"Form: "
                        f"{team_row.get('form')}"
                    )

            else:
                print(
                    f"Could not find {team_name} "
                    f"in the current standings."
                )

            print(
                "\nFULL TABLE"
            )

            print(
                f"{'Pos':<5}"
                f"{'Team':<25}"
                f"{'P':<5}"
                f"{'W':<5}"
                f"{'D':<5}"
                f"{'L':<5}"
                f"{'GD':<7}"
                f"{'Pts':<6}"
            )

            print("-" * 70)

            for row in standings:
                position = row.get(
                    "position",
                    "-"
                )

                name = row.get(
                    "team_name",
                    "Unknown"
                )

                played = row.get(
                    "played",
                    "-"
                )

                wins = row.get(
                    "wins",
                    "-"
                )

                draws = row.get(
                    "draws",
                    "-"
                )

                losses = row.get(
                    "losses",
                    "-"
                )

                goal_difference = row.get(
                    "goal_difference",
                    "-"
                )

                points = row.get(
                    "points",
                    "-"
                )

                print(
                    f"{str(position):<5}"
                    f"{name[:24]:<25}"
                    f"{str(played):<5}"
                    f"{str(wins):<5}"
                    f"{str(draws):<5}"
                    f"{str(losses):<5}"
                    f"{str(goal_difference):<7}"
                    f"{str(points):<6}"
                )

    # ==========================================================
    # LIVE SCORES
    # ==========================================================

    def show_live(self):
        self.section("LIVE SCORES")

        teams = self.teams()

        if not teams:
            return

        ids = {
            team.get("id")
            for team in teams
        }

        try:
            data = self.football.get_live_scores()

        except requests.RequestException as error:
            print(
                f"Could not retrieve live scores: "
                f"{error}"
            )
            return

        matches = [
            fixture
            for fixture in data.get(
                "response",
                []
            )
            if (
                fixture.get(
                    "homeTeam",
                    {}
                ).get("id") in ids
                or
                fixture.get(
                    "awayTeam",
                    {}
                ).get("id") in ids
            )
        ]

        if not matches:
            print(
                "\nNo live matches for your "
                "watched teams right now. ⚽"
            )
            return

        print(
            f"\nLive matches found: "
            f"{len(matches)}"
        )

        print("-" * 70)

        for fixture in matches:
            home = fixture.get(
                "homeTeam",
                {}
            ).get(
                "name",
                "Unknown"
            )

            away = fixture.get(
                "awayTeam",
                {}
            ).get(
                "name",
                "Unknown"
            )

            home_score = (
                fixture.get("goalsHome")
                or 0
            )

            away_score = (
                fixture.get("goalsAway")
                or 0
            )

            status = fixture.get(
                "statusShort",
                "LIVE"
            )

            minute = fixture.get(
                "elapsed"
            )

            league = fixture.get(
                "league",
                {}
            ).get(
                "name",
                "Unknown competition"
            )

            print(
                f"\n⚽ {home} "
                f"{home_score} - "
                f"{away_score} {away}"
            )

            print(
                f"🔴 LIVE | Status: {status}"
            )

            if minute is not None:
                print(
                    f"⏱️ Minute: {minute}'"
                )

            print(
                f"🏆 {league}"
            )

    # ==========================================================
    # NEWS
    # ==========================================================

    def show_news(self):
        self.section("LATEST NEWS")

        teams = self.teams()

        if not teams:
            return

        for team in teams:
            name = team.get(
                "name",
                "Unknown"
            )

            print(
                f"\n📰 {name}"
            )

            print("-" * 70)

            try:
                data = self.news.search_news(
                    name,
                    page_size=20
                )

            except requests.RequestException as error:
                print(
                    f"Could not retrieve news: "
                    f"{error}"
                )
                continue

            articles = data.get(
                "articles",
                []
            )

            if not articles:
                print(
                    "No recent news found."
                )
                continue

            for article in articles:
                title = article.get(
                    "title",
                    "Untitled"
                )

                source = article.get(
                    "source",
                    {}
                ).get(
                    "name",
                    "Unknown source"
                )

                published = article.get(
                    "publishedAt"
                )

                date = self.parse_date(
                    published
                )

                if date:
                    published = (
                        self.timezone.format_datetime(
                            date
                        )
                    )

                print(
                    f"\n🔹 {title}"
                )

                print(
                    f"   Source: {source}"
                )

                if published:
                    print(
                        f"   📅 {published}"
                    )

                if article.get("url"):
                    print(
                        f"   🔗 "
                        f"{article['url']}"
                    )

    # ==========================================================
    # NOTIFICATIONS
    # ==========================================================

    def show_notifications(self):
        self.section("NOTIFICATIONS")

        print(
            "🔔 Notification Center"
        )

        print("-" * 70)

        print(
            "\nNext match reminders are "
            "scheduled automatically."
        )

        print(
            "\nReminders:"
        )

        print(
            "• 24 hours before"
        )

        print(
            "• 1 hour before"
        )

        print(
            "• 15 minutes before"
        )

        print(
            "\nLive monitoring:"
        )

        print(
            "• Checks every 5 minutes"
        )

        print(
            "• Live match alerts"
        )

        print(
            "• Goal alerts"
        )

        print(
            "• Full-time alerts"
        )

    # ==========================================================
    # START LIVE MONITOR
    # ==========================================================

    def start_live_monitor(self):
        teams = self.teams()

        if not teams:
            return

        self.monitor.monitor_live(
            teams,
            interval=300
        )

    # ==========================================================
    # MENU
    # ==========================================================

    def run(self):

        # Fetch fixtures once and schedule
        # the next-match reminders.
        self.monitor.schedule_reminders(
            self.watchlist.get_teams(),
            SEASON
        )

        actions = {
            "1": self.add_team,
            "2": self.show_watchlist,
            "3": self.show_upcoming,
            "4": self.show_results,
            "5": self.show_standings,
            "6": self.show_live,
            "7": self.show_news,
            "8": self.show_notifications,
            "9": self.start_live_monitor,
        }

        while True:
            self.section("AI SPORTS AGENT")

            print("1. Add a team")
            print("2. View watchlist")
            print("3. Upcoming fixtures")
            print("4. Recent results")
            print("5. League standings")
            print("6. Live scores")
            print("7. Latest news")
            print("8. Notifications")
            print("9. Start live match monitor")
            print("10. Exit")

            print("-" * 70)

            choice = input(
                "Choose an option: "
            ).strip()

            if choice == "10":
                print(
                    "\nGoodbye! 👋"
                )
                break

            action = actions.get(choice)

            if action:
                action()
            else:
                print(
                    "\nPlease choose a valid option "
                    "from 1 to 10."
                )


def main():
    SportsAgent().run()


if __name__ == "__main__":
    main()