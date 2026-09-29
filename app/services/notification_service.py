import time
import threading


class NotificationService:

    def match_reminder(
        self,
        team_name,
        opponent,
        match_date,
        competition,
        reminder_type
    ):
        return (
            "🔔 SPORTS ALERT\n\n"
            f"⏰ {reminder_type.upper()} REMINDER\n\n"
            f"⚽ {team_name} vs {opponent}\n\n"
            f"📅 {match_date}\n"
            f"🏆 {competition}"
        )

    def live_match(
        self,
        team_name,
        opponent,
        home_score,
        away_score,
        minute
    ):
        return (
            "🔴 LIVE MATCH\n\n"
            f"{team_name} vs {opponent}\n\n"
            f"⚽ {home_score} - {away_score}\n"
            f"⏱️ {minute}'"
        )

    def goal_alert(
        self,
        team_name,
        opponent,
        home_score,
        away_score,
        scorer
    ):
        return (
            "⚽ GOAL!\n\n"
            f"{team_name} vs {opponent}\n\n"
            f"Score: {home_score} - {away_score}\n"
            f"🥅 Scorer: {scorer}"
        )

    def full_time(
        self,
        team_name,
        opponent,
        home_score,
        away_score
    ):
        return (
            "🏁 FULL TIME\n\n"
            f"{team_name} vs {opponent}\n\n"
            f"Final Score: {home_score} - {away_score}"
        )

    def transfer_alert(
        self,
        player_name,
        from_team,
        to_team,
        transfer_fee
    ):
        return (
            "🔄 TRANSFER ALERT\n\n"
            f"{player_name}\n\n"
            f"From: {from_team}\n"
            f"To: {to_team}\n"
            f"💰 Fee: {transfer_fee}"
        )

    def news_alert(
        self,
        team_name,
        headline,
        source
    ):
        return (
            "📰 SPORTS NEWS\n\n"
            f"{team_name}\n\n"
            f"{headline}\n"
            f"Source: {source}"
        )

    def schedule_reminder(
        self,
        delay,
        message
    ):
        def send():
            time.sleep(max(0, delay))

            print(
                "\n" + "=" * 70
            )

            print(message)

            print(
                "=" * 70
            )

        thread = threading.Thread(
            target=send,
            daemon=True
        )

        thread.start()