import time
from datetime import datetime, timezone


class MatchMonitorService:

    def __init__(
        self,
        football,
        notifications,
        timezone_service
    ):
        self.football = football
        self.notifications = notifications
        self.timezone = timezone_service

        self.previous_scores = {}
        self.finished_matches = set()

    # ==========================================================
    # HELPERS
    # ==========================================================

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

    def get_next_match(self, team_id, season):
        now = datetime.now(timezone.utc)

        try:
            data = self.football.get_fixtures(
                team_id,
                season
            )
        except Exception:
            return None

        upcoming = []

        for fixture in data.get("response", []):
            home = fixture.get("homeTeam", {})
            away = fixture.get("awayTeam", {})

            if team_id not in (
                home.get("id"),
                away.get("id")
            ):
                continue

            match_time = self.parse_date(
                fixture.get("date")
            )

            if match_time and match_time > now:
                upcoming.append(
                    (match_time, fixture)
                )

        if not upcoming:
            return None

        return min(
            upcoming,
            key=lambda item: item[0]
        )

    # ==========================================================
    # REMINDERS
    # ==========================================================

    def schedule_reminders(self, teams, season):
        now = datetime.now(timezone.utc)

        print("\n🔔 Setting up match reminders...")

        for team in teams:
            self.schedule_team_reminders(
                team,
                season,
                now
            )

    def schedule_team_reminders(
        self,
        team,
        season,
        now=None
    ):
        if now is None:
            now = datetime.now(timezone.utc)

        team_id = team.get("id")
        team_name = team.get(
            "name",
            "Unknown"
        )

        result = self.get_next_match(
            team_id,
            season
        )

        if not result:
            print(
                f"ℹ️ No upcoming match "
                f"found for {team_name}."
            )
            return

        match_time, fixture = result

        home = fixture.get(
            "homeTeam",
            {}
        )

        away = fixture.get(
            "awayTeam",
            {}
        )

        opponent = (
            away.get("name", "Unknown")
            if home.get("id") == team_id
            else home.get("name", "Unknown")
        )

        match_date = self.timezone.format_datetime(
            match_time
        )

        competition = fixture.get(
            "round",
            "Unknown competition"
        )

        print(
            f"\n{team_name}: "
            f"next match vs {opponent}"
        )

        print(
            f"📅 {match_date}"
        )

        reminders = {
            "24 hours": 24 * 60 * 60,
            "1 hour": 60 * 60,
            "15 minutes": 15 * 60
        }

        for reminder_type, seconds in reminders.items():

            delay = (
                match_time.timestamp()
                - seconds
                - now.timestamp()
            )

            if delay <= 0:
                continue

            message = self.notifications.match_reminder(
                team_name,
                opponent,
                match_date,
                competition,
                reminder_type
            )

            self.notifications.schedule_reminder(
                delay,
                message
            )

            print(
                f"   ✅ {reminder_type} "
                f"reminder scheduled."
            )

    # ==========================================================
    # LIVE MATCHES
    # ==========================================================

    def get_live_matches(self, teams):
        team_ids = {
            team.get("id")
            for team in teams
        }

        try:
            data = self.football.get_live_scores()
        except Exception as error:
            print(
                f"\n⚠️ Live score request failed: "
                f"{error}"
            )
            return []

        return [
            fixture
            for fixture in data.get("response", [])
            if (
                fixture.get(
                    "homeTeam",
                    {}
                ).get("id") in team_ids
                or
                fixture.get(
                    "awayTeam",
                    {}
                ).get("id") in team_ids
            )
        ]

    # ==========================================================
    # CHECK LIVE MATCHES
    # ==========================================================

    def check_live_matches(self, teams):
        matches = self.get_live_matches(teams)

        if not matches:
            print(
                "\nNo watched matches are live."
            )
            return

        for fixture in matches:
            self.process_match(fixture)

    # ==========================================================
    # PROCESS MATCH
    # ==========================================================

    def process_match(self, fixture):
        fixture_id = fixture.get("id")

        if not fixture_id:
            return

        home = fixture.get(
            "homeTeam",
            {}
        )

        away = fixture.get(
            "awayTeam",
            {}
        )

        home_name = home.get(
            "name",
            "Unknown"
        )

        away_name = away.get(
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

        minute = fixture.get(
            "elapsed"
        )

        status = fixture.get(
            "statusShort"
        )

        current_score = (
            home_score,
            away_score
        )

        # ------------------------------------------------------
        # FULL TIME
        # ------------------------------------------------------

        if status in (
            "FT",
            "AET",
            "PEN"
        ):
            if fixture_id not in self.finished_matches:

                self.send_full_time_alert(
                    home_name,
                    away_name,
                    home_score,
                    away_score
                )

                self.finished_matches.add(
                    fixture_id
                )

                self.previous_scores.pop(
                    fixture_id,
                    None
                )

            return

        # ------------------------------------------------------
        # FIRST LIVE CHECK
        # ------------------------------------------------------

        if fixture_id not in self.previous_scores:

            self.previous_scores[fixture_id] = (
                current_score
            )

            self.send_live_alert(
                home_name,
                away_name,
                home_score,
                away_score,
                minute
            )

            return

        # ------------------------------------------------------
        # GOAL DETECTION
        # ------------------------------------------------------

        previous_score = self.previous_scores[
            fixture_id
        ]

        if current_score != previous_score:

            scorer = self.get_scorer(
                fixture
            )

            self.send_goal_alert(
                home_name,
                away_name,
                home_score,
                away_score,
                scorer
            )

            self.previous_scores[fixture_id] = (
                current_score
            )

    # ==========================================================
    # ALERTS
    # ==========================================================

    def send_live_alert(
        self,
        home,
        away,
        home_score,
        away_score,
        minute
    ):
        print(
            "\n" + "=" * 70
        )

        print(
            self.notifications.live_match(
                home,
                away,
                home_score,
                away_score,
                minute
            )
        )

        print(
            "=" * 70
        )

    def send_goal_alert(
        self,
        home,
        away,
        home_score,
        away_score,
        scorer
    ):
        print(
            "\n" + "=" * 70
        )

        print(
            self.notifications.goal_alert(
                home,
                away,
                home_score,
                away_score,
                scorer
            )
        )

        print(
            "=" * 70
        )

    def send_full_time_alert(
        self,
        home,
        away,
        home_score,
        away_score
    ):
        print(
            "\n" + "=" * 70
        )

        print(
            self.notifications.full_time(
                home,
                away,
                home_score,
                away_score
            )
        )

        print(
            "=" * 70
        )

    # ==========================================================
    # SCORER
    # ==========================================================

    def get_scorer(self, fixture):
        events = fixture.get(
            "events",
            []
        )

        for event in reversed(events):
            if event.get("type") != "Goal":
                continue

            player = event.get(
                "player",
                {}
            )

            return player.get(
                "name",
                "Unknown"
            )

        return "Unknown"

    # ==========================================================
    # LIVE MONITOR
    # ==========================================================

    def monitor_live(
        self,
        teams,
        interval=300
    ):
        print(
            "\n🔴 LIVE MATCH MONITOR"
        )

        print(
            "Checking live matches every "
            "5 minutes."
        )

        print(
            "Press Ctrl+C to stop."
        )

        try:
            while True:

                print(
                    "\n🔎 Checking live matches..."
                )

                self.check_live_matches(
                    teams
                )

                print(
                    "\n⏳ Next check in "
                    f"{interval // 60} minutes."
                )

                time.sleep(interval)

        except KeyboardInterrupt:
            print(
                "\n\n🛑 Live monitor stopped."
            )