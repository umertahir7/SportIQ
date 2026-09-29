class TeamResolver:
    PRIORITY_LEAGUES = {
        "Premier League",
        "La Liga",
        "Saudi Pro League",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
        "UEFA Champions League",
    }

    NEGATIVE_KEYWORDS = {
        "u18",
        "u19",
        "u21",
        "u23",
        "reserve",
        "res",
        "ii",
        "iii",
        "women",
        "feminino",
        "femenino",
    }

    COMMON_ALIASES = {
        "man united": "Manchester United",
        "man utd": "Manchester United",
        "man city": "Manchester City",
        "spurs": "Tottenham",
        "psg": "Paris Saint Germain",
        "inter": "Inter",
        "inter milan": "Inter",
        "atleti": "Atletico Madrid",
        "al nassr": "Al-Nassr",
        "al nassr fc": "Al-Nassr",
    }

    MAJOR_CLUBS = {
        "real madrid",
        "barcelona",
        "atletico madrid",
        "arsenal",
        "chelsea",
        "liverpool",
        "manchester united",
        "manchester city",
        "tottenham hotspur",
        "bayern munich",
        "borussia dortmund",
        "paris saint germain",
        "juventus",
        "inter",
        "ac milan",
        "al nassr",
    }

    PRIORITY_COUNTRIES = {
        "england",
        "spain",
        "saudi-arabia",
        "italy",
        "germany",
        "france",
    }

    def __init__(self, football_service):
        self.football = football_service
        self.league_cache = {}

    def normalize(self, text):
        if not text:
            return ""

        return (
            str(text)
            .lower()
            .strip()
            .replace("-", " ")
            .replace(".", "")
        )

    def resolve_alias(self, team_name):
        normalized = self.normalize(team_name)

        return self.COMMON_ALIASES.get(
            normalized,
            team_name
        )

    def build_team_identity(self, team):
        """
        Build a reusable identity for any resolved team.

        This keeps team-specific information together so other
        services, especially the news service, do not need
        hardcoded team names or keywords.
        """

        if not team:
            return None

        team_name = team.get("name", "")
        short_name = team.get("shortName", "")
        country = team.get("countryName", "")
        team_id = team.get("id")

        canonical_name = team_name.strip()

        search_terms = []

        if canonical_name:
            search_terms.append(canonical_name)

        if short_name:
            short_name = str(short_name).strip()

            if (
                short_name
                and self.normalize(short_name)
                != self.normalize(canonical_name)
            ):
                search_terms.append(short_name)

        normalized_name = self.normalize(canonical_name)

        for alias, canonical in self.COMMON_ALIASES.items():
            if self.normalize(canonical) == normalized_name:
                search_terms.append(alias)

        unique_terms = []

        for term in search_terms:
            cleaned = term.strip()

            if cleaned and cleaned not in unique_terms:
                unique_terms.append(cleaned)

        return {
            "id": team_id,
            "name": canonical_name,
            "short_name": short_name,
            "country": country,
            "search_terms": unique_terms,
        }

    def get_current_leagues(self, team_id):
        if team_id in self.league_cache:
            return self.league_cache[team_id]

        try:
            data = self.football.get_team_leagues(team_id)

            leagues = []

            for item in data.get("response", []):
                league = item.get("league", {})
                league_name = league.get("name")

                if league_name:
                    leagues.append(league_name)

            self.league_cache[team_id] = leagues

            return leagues

        except Exception:
            self.league_cache[team_id] = []

            return []

    def score_team(self, requested_name, team):
        score = 0

        requested = self.normalize(requested_name)

        team_name = team.get("name", "")
        normalized_team = self.normalize(team_name)

        country = self.normalize(
            team.get("countryName", "")
        )

        if normalized_team == requested:
            score += 50

        elif requested in normalized_team:
            score += 20

        for keyword in self.NEGATIVE_KEYWORDS:
            if keyword in normalized_team:
                score -= 40

        if (
            normalized_team.endswith(" w")
            or " women" in normalized_team
            or normalized_team.endswith("women")
        ):
            score -= 50

        if country in self.PRIORITY_COUNTRIES:
            score += 5

        if normalized_team in self.MAJOR_CLUBS:
            score += 15

        return score

    def rank_local(self, requested_name, teams):
        ranked = []

        for team in teams:
            score = self.score_team(
                requested_name,
                team
            )

            ranked.append(
                {
                    "team": team,
                    "score": score,
                    "leagues": [],
                }
            )

        ranked.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return ranked

    def select_league_candidates(
        self,
        requested_name,
        ranked
    ):
        selected = []

        requested = self.normalize(
            requested_name
        )

        for item in ranked[:3]:
            if item not in selected:
                selected.append(item)

        for item in ranked:
            team_name = self.normalize(
                item["team"].get("name", "")
            )

            if team_name == requested:
                if item not in selected:
                    selected.append(item)

        return selected

    def apply_league_bonus(self, candidates):
        for item in candidates:
            team = item["team"]

            team_id = team.get("id")

            if not team_id:
                continue

            leagues = self.get_current_leagues(
                team_id
            )

            item["leagues"] = leagues

            priority_found = any(
                league in self.PRIORITY_LEAGUES
                for league in leagues
            )

            if priority_found:
                item["score"] += 30

    def rank_teams(self, requested_name, teams):
        ranked = self.rank_local(
            requested_name,
            teams
        )

        candidates = self.select_league_candidates(
            requested_name,
            ranked
        )

        self.apply_league_bonus(
            candidates
        )

        ranked.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return ranked

    def get_best_match(self, requested_name, teams):
        if not teams:
            return None

        ranked = self.rank_teams(
            requested_name,
            teams
        )

        best = ranked[0]

        if best["score"] <= 0:
            return None

        return best

    def get_team_identity(
        self,
        requested_name,
        teams
    ):
        """
        Resolve a requested team and return its
        reusable identity.

        This is the foundation for dynamic team-specific
        news searches, notifications, and AI context.
        """

        result = self.get_best_match(
            requested_name,
            teams
        )

        if result is None:
            return None

        identity = self.build_team_identity(
            result["team"]
        )

        if identity is None:
            return None

        identity["score"] = result["score"]
        identity["leagues"] = result["leagues"]

        return identity