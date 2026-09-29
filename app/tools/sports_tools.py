from datetime import datetime, timezone

from app.config import SEASON
from app.services.kickoff_service import KickoffService
from app.services.news_service import NewsService
from app.services.watchlist_service import WatchlistService
from app.services.timezone_service import TimezoneService


class SportsTools:
    """
    Tool layer exposed to the AI Sports Agent.

    These methods retrieve information from the application's
    services and return only the relevant fields needed by the LLM.
    """

    COMPETITION_DISPLAY_NAMES = {
        "League Cup": "Carabao Cup",
    }

    # BSD major men's domestic leagues.
    MAJOR_LEAGUE_IDS = {
        1: "Premier League",
        3: "La Liga",
        4: "Serie A",
        5: "Bundesliga",
        6: "Ligue 1",
        17: "Saudi Pro League",
    }

    # Reserve / youth / B-team keywords.
    NON_SENIOR_TEAM_KEYWORDS = (
        " u21",
        " u20",
        " u19",
        " u18",
        " u17",
        " u16",
        " u23",
        " b",
        " b ",
        " c",
        " c ",
        "castilla",
        "reserves",
        "reserve",
        "women",
        "femenino",
        "fem",
        "ladies",
    )

    def __init__(self):
        self.football = KickoffService()
        self.news = NewsService()
        self.watchlist = WatchlistService()
        self.timezone = TimezoneService()

        self.competition_cache = {}

    # ============================================================
    # GENERIC DATA HELPERS
    # ============================================================

    @staticmethod
    def _safe_int(value):
        """
        Safely convert a value to int.

        Returns None when conversion is not possible.
        """
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_team_name(team):
        """
        Extract a team name from either:
        - a string
        - a team dictionary
        - an object containing common BSD team fields
        """
        if isinstance(team, str):
            return team

        if not isinstance(team, dict):
            return None

        return (
            team.get("name")
            or team.get("team_name")
            or team.get("short_name")
        )

    @staticmethod
    def _extract_team_id(team):
        """
        Extract a team ID from either:
        - an integer
        - a numeric string
        - a team dictionary
        """
        if isinstance(team, dict):
            team = team.get("id") or team.get("team_id")

        return SportsTools._safe_int(team)

    @staticmethod
    def _extract_team_logo(team):
        """
        Extract a team logo from a normalized or raw team object.
        """
        if not isinstance(team, dict):
            return None

        return team.get("logo") or team.get("logo_url")

    @staticmethod
    def _extract_venue_name(item):
        """
        Extract a readable venue name from normalized BSD data
        or nested/raw venue structures.
        """
        if not isinstance(item, dict):
            return None

        venue_name = item.get("venue_name")

        if venue_name:
            return venue_name

        venue = item.get("venue")

        if isinstance(venue, dict):
            return (
                venue.get("name")
                or venue.get("venue_name")
                or venue.get("stadium")
            )

        if isinstance(venue, str):
            return venue

        return None

    @staticmethod
    def _extract_venue_city(item):
        """
        Extract venue city/location.
        """
        if not isinstance(item, dict):
            return None

        venue_city = item.get("venue_city")

        if venue_city:
            return venue_city

        venue = item.get("venue")

        if isinstance(venue, dict):
            return venue.get("city") or venue.get("location")

        return None

    @staticmethod
    def _extract_venue_country(item):
        """
        Extract venue country.
        """
        if not isinstance(item, dict):
            return None

        venue_country = item.get("venue_country")

        if venue_country:
            return venue_country

        venue = item.get("venue")

        if isinstance(venue, dict):
            return (
                venue.get("country")
                or venue.get("country_name")
            )

        return None

    @staticmethod
    def _extract_competition_name(item):
        """
        Extract a readable competition name from normalized BSD
        data or nested competition/league structures.
        """
        if not isinstance(item, dict):
            return None

        competition_name = (
            item.get("competition_display_name")
            or item.get("competition_name")
            or item.get("league_name")
        )

        if competition_name:
            return competition_name

        competition = (
            item.get("competition")
            or item.get("league")
        )

        if isinstance(competition, dict):
            return (
                competition.get("name")
                or competition.get("league_name")
                or competition.get("title")
            )

        return None

    @staticmethod
    def _extract_competition_id(item):
        """
        Extract competition/league ID.
        """
        if not isinstance(item, dict):
            return None

        competition_id = (
            item.get("competition_id")
            or item.get("league_id")
        )

        if competition_id is not None:
            return SportsTools._safe_int(competition_id)

        competition = (
            item.get("competition")
            or item.get("league")
        )

        if isinstance(competition, dict):
            return SportsTools._safe_int(
                competition.get("id")
                or competition.get("league_id")
            )

        return None

    @staticmethod
    def _team_matches(
        team,
        expected_team_id=None,
        expected_team_name=None,
    ):
        """
        Determine whether a team object/string matches the
        requested team.

        Team ID is preferred because it is more reliable than
        name matching.
        """
        actual_id = SportsTools._extract_team_id(team)
        expected_id = SportsTools._safe_int(expected_team_id)

        if (
            actual_id is not None
            and expected_id is not None
        ):
            return actual_id == expected_id

        actual_name = SportsTools._extract_team_name(team)

        if not actual_name or not expected_team_name:
            return False

        return (
            actual_name.lower().strip()
            == expected_team_name.lower().strip()
        )

    # ============================================================
    # TEAM NAME / SENIOR TEAM HELPERS
    # ============================================================

    @staticmethod
    def _normalize_team_name(name):
        """
        Normalize a team name for safe comparison.
        """
        if name is None:
            return ""

        return str(name).lower().strip()

    @classmethod
    def _is_non_senior_team(cls, team_name):
        """
        Identify obvious youth, reserve, B/C, or women's teams.

        This is intentionally conservative. It is only used to
        choose between BSD search candidates when a senior team
        exists.
        """
        normalized = cls._normalize_team_name(team_name)

        if not normalized:
            return False

        for keyword in cls.NON_SENIOR_TEAM_KEYWORDS:
            if keyword in normalized:
                return True

        return False

    @classmethod
    def _team_name_matches_exactly(
        cls,
        first_name,
        second_name,
    ):
        """
        Exact normalized team-name comparison.
        """
        first = cls._normalize_team_name(first_name)
        second = cls._normalize_team_name(second_name)

        return bool(
            first
            and second
            and first == second
        )

    @classmethod
    def _team_name_matches_safely(
        cls,
        requested_name,
        candidate_name,
    ):
        """
        Safe team-name comparison.

        Exact matches are preferred. Partial matching is retained
        for names such as Al Nassr / Al-Nassr.
        """
        requested = cls._normalize_team_name(requested_name)
        candidate = cls._normalize_team_name(candidate_name)

        if not requested or not candidate:
            return False

        if requested == candidate:
            return True

        requested_compact = requested.replace("-", " ")
        candidate_compact = candidate.replace("-", " ")

        requested_compact = " ".join(
            requested_compact.split()
        )

        candidate_compact = " ".join(
            candidate_compact.split()
        )

        if requested_compact == candidate_compact:
            return True

        return (
            requested_compact in candidate_compact
            or candidate_compact in requested_compact
        )

    def _search_mens_team_candidates(self, team_name):
        """
        Search BSD specifically for men's football teams.

        BSD supports the `is_women` parameter. Using
        is_women=False is important because a generic team-name
        search can otherwise return a women's team first.

        No hardcoded club IDs are used.
        """
        if team_name is None:
            return []

        team_name = str(team_name).strip()

        if not team_name:
            return []

        try:
            data = self.football._bsd_request(
                "teams/",
                params={
                    "name": team_name,
                    "is_women": False,
                    "limit": 20,
                },
            )
        except Exception:
            return []

        if not isinstance(data, dict):
            return []

        candidates = data.get(
            "results",
            data.get("data", []),
        )

        if not isinstance(candidates, list):
            candidates = []

        # National teams are also represented by BSD's /teams/ endpoint,
        # but a strict is_women=False search can omit some national-team
        # records. Retry without that filter only when the first search
        # returned nothing.
        if not candidates:
            try:
                data = self.football._bsd_request(
                    "teams/",
                    params={
                        "name": team_name,
                        "limit": 20,
                    },
                )
            except Exception:
                return []

            if not isinstance(data, dict):
                return []

            candidates = data.get(
                "results",
                data.get("data", []),
            )

            if not isinstance(candidates, list):
                return []

        cleaned = []

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            candidate_id = self._safe_int(
                candidate.get("id")
                or candidate.get("team_id")
            )

            candidate_name = (
                candidate.get("name")
                or candidate.get("team_name")
                or candidate.get("short_name")
            )

            if candidate_id is None or not candidate_name:
                continue

            if self._is_non_senior_team(candidate_name):
                continue

            candidate_copy = dict(candidate)
            candidate_copy["id"] = candidate_id

            cleaned.append(candidate_copy)

        return cleaned

    @staticmethod
    def _extract_manager_from_payload(payload):
        """Extract a manager/coach object or name from common BSD shapes."""
        if not isinstance(payload, dict):
            return None

        manager_keys = (
            "manager",
            "coach",
            "head_coach",
            "current_manager",
            "current_coach",
        )

        for key in manager_keys:
            value = payload.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, str) and value.strip():
                return {"name": value.strip()}

        # BSD responses may wrap the team under one of these keys.
        for key in ("team", "data", "result", "detail"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                found = SportsTools._extract_manager_from_payload(nested)
                if found is not None:
                    return found

        return None

    def get_team_manager(self, team_name):
        """
        Resolve and return the current manager/head coach from BSD.

        The team profile is preferred. If BSD does not embed the manager
        there, the dedicated managers endpoint is queried using both the
        team filter and exact team-name search as fallbacks.
        """
        resolved = self._resolve_team_for_analysis(team_name)

        if not isinstance(resolved, dict) or resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": (
                    resolved.get("message", "Could not resolve the team.")
                    if isinstance(resolved, dict)
                    else "Could not resolve the team."
                ),
                "error": (
                    resolved.get("error")
                    if isinstance(resolved, dict)
                    else None
                ),
            }

        team_id = self._safe_int(resolved.get("team_id"))
        resolved_name = resolved.get("team_name") or str(team_name).strip()

        if team_id is None:
            return {
                "status": "error",
                "team": resolved_name,
                "message": "BSD team resolution returned no valid team ID.",
            }

        # 1) Team profile. This is the cleanest source when the manager
        # is embedded in the response.
        try:
            profile = self.football._bsd_request(f"teams/{team_id}/")
        except Exception:
            profile = None

        manager = self._extract_manager_from_payload(profile)

        if isinstance(manager, dict):
            manager_name = (
                manager.get("name")
                or manager.get("manager_name")
                or manager.get("coach_name")
                or manager.get("short_name")
            )
            if manager_name:
                manager_id = self._safe_int(
                    manager.get("id") or manager.get("manager_id")
                )
                image = (
                    manager.get("image")
                    or manager.get("photo")
                    or manager.get("image_url")
                    or manager.get("photo_url")
                )
                if not image and manager_id is not None:
                    image = f"{self.football.BSD_IMAGE_PROXY}/manager/{manager_id}/"

                return {
                    "status": "success",
                    "team": resolved_name,
                    "team_id": team_id,
                    "manager": {
                        "id": manager_id,
                        "name": manager_name,
                        "image": image,
                        "photo": image,
                    },
                }

        # 2) Dedicated managers endpoint. BSD exposes manager search and
        # team filtering; try team_id first, then team, then exact search.
        lookup_params = [
            {"team_id": team_id, "limit": 20, "offset": 0},
            {"team": team_id, "limit": 20, "offset": 0},
            {"search": resolved_name, "limit": 20, "offset": 0},
        ]

        managers = []
        for params in lookup_params:
            try:
                data = self.football._bsd_request("managers/", params=params)
            except Exception:
                continue

            if isinstance(data, dict):
                values = data.get("results", data.get("data", []))
            else:
                values = data

            if isinstance(values, list):
                managers = values
                if managers:
                    break

        # Prefer a manager explicitly associated with this team/current role.
        selected = None
        for candidate in managers:
            if not isinstance(candidate, dict):
                continue

            candidate_team = candidate.get("current_team")
            candidate_team_id = self._safe_int(
                candidate.get("current_team_id")
                or candidate.get("team_id")
                or (
                    candidate_team.get("id")
                    if isinstance(candidate_team, dict)
                    else None
                )
            )

            is_current = (
                candidate.get("is_current") is True
                or candidate.get("current") is True
                or candidate.get("active") is True
            )

            if candidate_team_id == team_id or is_current:
                selected = candidate
                break

        if selected is None and managers:
            # For exact team-name search results, the first matching record
            # is preferable to returning no manager at all.
            selected = managers[0] if isinstance(managers[0], dict) else None

        if isinstance(selected, dict):
            manager_name = (
                selected.get("name")
                or selected.get("manager_name")
                or selected.get("coach_name")
                or selected.get("short_name")
            )
            if manager_name:
                manager_id = self._safe_int(
                    selected.get("id") or selected.get("manager_id")
                )
                image = (
                    selected.get("image")
                    or selected.get("photo")
                    or selected.get("image_url")
                    or selected.get("photo_url")
                )
                if not image and manager_id is not None:
                    image = f"{self.football.BSD_IMAGE_PROXY}/manager/{manager_id}/"

                return {
                    "status": "success",
                    "team": resolved_name,
                    "team_id": team_id,
                    "manager": {
                        "id": manager_id,
                        "name": manager_name,
                        "image": image,
                        "photo": image,
                    },
                }

        return {
            "status": "success",
            "team": resolved_name,
            "team_id": team_id,
            "manager": None,
            "message": "BSD returned no current manager for this team.",
        }

    def _resolve_mens_team(self, team_name):
        """
        Resolve a team name to the correct men's senior BSD team.

        Resolution order:
        1. BSD men's-only search.
        2. Exact senior-team name.
        3. Best non-youth candidate.
        4. Existing KickoffService resolver as a final fallback.
        """
        if team_name is None:
            return None

        requested_name = str(team_name).strip()

        if not requested_name:
            return None

        candidates = self._search_mens_team_candidates(
            requested_name
        )

        exact_candidates = [
            candidate
            for candidate in candidates
            if self._team_name_matches_exactly(
                requested_name,
                candidate.get("name"),
            )
        ]

        if exact_candidates:
            return exact_candidates[0]

        normalized_exact = [
            candidate
            for candidate in candidates
            if self._team_name_matches_safely(
                requested_name,
                candidate.get("name"),
            )
            and not self._is_non_senior_team(
                candidate.get("name")
            )
        ]

        if normalized_exact:
            normalized_exact.sort(
                key=lambda candidate: len(
                    str(candidate.get("name", ""))
                )
            )

            return normalized_exact[0]

        senior_candidates = [
            candidate
            for candidate in candidates
            if not self._is_non_senior_team(
                candidate.get("name")
            )
        ]

        if senior_candidates:
            senior_candidates.sort(
                key=lambda candidate: (
                    0
                    if self._team_name_matches_safely(
                        requested_name,
                        candidate.get("name"),
                    )
                    else 1,
                    len(
                        str(
                            candidate.get("name", "")
                        )
                    ),
                )
            )

            return senior_candidates[0]

        try:
            resolved = self.football.get_bsd_team(
                requested_name
            )
        except Exception:
            resolved = None

        if isinstance(resolved, dict):
            resolved_name = (
                resolved.get("name")
                or resolved.get("team_name")
                or resolved.get("short_name")
            )

            if (
                resolved_name
                and not self._is_non_senior_team(
                    resolved_name
                )
                and self._team_name_matches_safely(
                    requested_name,
                    resolved_name,
                )
            ):
                resolved_copy = dict(resolved)

                resolved_id = self._safe_int(
                    resolved.get("id")
                    or resolved.get("team_id")
                )

                if resolved_id is not None:
                    resolved_copy["id"] = resolved_id

                return resolved_copy

        return None

    # ============================================================
    # COMPETITION HELPERS
    # ============================================================

    def _get_competition_metadata(self, league_id):
        if league_id is None:
            return {
                "competition_id": None,
                "competition_name": None,
                "competition_display_name": None,
                "competition_type": None,
                "competition_country": None,
            }

        league_id = self._safe_int(league_id)

        if league_id is None:
            return {
                "competition_id": None,
                "competition_name": None,
                "competition_display_name": None,
                "competition_type": None,
                "competition_country": None,
            }

        if league_id in self.competition_cache:
            return self.competition_cache[league_id]

        try:
            data = self.football._request(
                "leagues",
                params={"id": league_id},
            )
        except Exception as error:
            return {
                "competition_id": league_id,
                "competition_name": None,
                "competition_display_name": None,
                "competition_type": None,
                "competition_country": None,
                "metadata_error": str(error),
            }

        response = (
            data.get("response", [])
            if isinstance(data, dict)
            else []
        )

        if not response:
            metadata = {
                "competition_id": league_id,
                "competition_name": None,
                "competition_display_name": None,
                "competition_type": None,
                "competition_country": None,
            }

            self.competition_cache[league_id] = metadata

            return metadata

        league = response[0]

        competition_name = league.get("name")
        competition_type = league.get("type")
        competition_country = league.get("countryName")

        display_name = self.COMPETITION_DISPLAY_NAMES.get(
            competition_name,
            competition_name,
        )

        metadata = {
            "competition_id": league.get(
                "id",
                league_id,
            ),
            "competition_name": competition_name,
            "competition_display_name": display_name,
            "competition_type": competition_type,
            "competition_country": competition_country,
        }

        self.competition_cache[league_id] = metadata

        return metadata

    # ============================================================
    # BSD TEAM HELPERS
    # ============================================================

    def _extract_team_league_ids(self, team_data):
        """
        Extract league IDs from whatever league-related structure
        BSD provides for a team.
        """
        if not isinstance(team_data, dict):
            return []

        league_ids = []

        possible_values = [
            team_data.get("league_id"),
            team_data.get("current_league_id"),
            team_data.get("major_league_ids"),
        ]

        for value in possible_values:
            if value is None:
                continue

            if isinstance(value, (list, tuple, set)):
                values = value
            else:
                values = [value]

            for item in values:
                if item is None:
                    continue

                try:
                    item = int(item)
                except (TypeError, ValueError):
                    continue

                if item not in league_ids:
                    league_ids.append(item)

        leagues = team_data.get("leagues")

        if isinstance(leagues, list):
            for league in leagues:
                if isinstance(league, dict):
                    league_id = (
                        league.get("id")
                        or league.get("league_id")
                    )

                    if league_id is not None:
                        try:
                            league_id = int(league_id)
                        except (TypeError, ValueError):
                            continue

                        if league_id not in league_ids:
                            league_ids.append(league_id)

        return league_ids

    def _extract_team_league_names(self, team_data):
        """
        Extract human-readable league names from BSD team data.
        """
        if not isinstance(team_data, dict):
            return []

        league_names = []

        possible_values = [
            team_data.get("major_leagues"),
            team_data.get("league_name"),
            team_data.get("current_league_name"),
        ]

        for value in possible_values:
            if value is None:
                continue

            if isinstance(value, (list, tuple, set)):
                values = value
            else:
                values = [value]

            for item in values:
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("league_name")
                    )
                else:
                    name = str(item).strip()

                if name and name not in league_names:
                    league_names.append(name)

        leagues = team_data.get("leagues")

        if isinstance(leagues, list):
            for league in leagues:
                if not isinstance(league, dict):
                    continue

                name = (
                    league.get("name")
                    or league.get("league_name")
                )

                if name and name not in league_names:
                    league_names.append(name)

        return league_names

    def _build_team_resolution(
        self,
        team_data,
        requested_name,
    ):
        """
        Convert a raw BSD team response into the structure expected
        by the SportsTools analysis methods.
        """
        if not isinstance(team_data, dict):
            return None

        team_id = (
            team_data.get("id")
            or team_data.get("team_id")
        )

        if team_id is None:
            return None

        try:
            team_id = int(team_id)
        except (TypeError, ValueError):
            return None

        team_name = (
            team_data.get("name")
            or team_data.get("team_name")
            or team_data.get("short_name")
            or requested_name
        )

        league_ids = self._extract_team_league_ids(
            team_data
        )

        league_names = self._extract_team_league_names(
            team_data
        )

        if not league_ids:
            possible_league_id = self._safe_int(
                team_data.get("_resolved_league_id")
            )

            if possible_league_id is not None:
                league_ids.append(possible_league_id)

        if not league_names and league_ids:
            for league_id in league_ids:
                league_name = self.MAJOR_LEAGUE_IDS.get(
                    league_id
                )

                if league_name:
                    league_names.append(league_name)

        return {
            "id": team_id,
            "name": team_name,
            "short_name": team_data.get("short_name"),
            "logo": (
                team_data.get("logo")
                or team_data.get("logo_url")
            ),
            "league_id": (
                team_data.get("league_id")
                or team_data.get("current_league_id")
                or (
                    league_ids[0]
                    if league_ids
                    else None
                )
            ),
            "league_name": (
                team_data.get("league_name")
                or team_data.get("current_league_name")
                or (
                    league_names[0]
                    if league_names
                    else None
                )
            ),
            "major_league_ids": league_ids,
            "major_leagues": league_names,
            "raw": team_data,
        }

    def _team_name_matches(
        self,
        first_name,
        second_name,
    ):
        """
        Compare two team names safely.
        """
        return self._team_name_matches_safely(
            first_name,
            second_name,
        )

    # ============================================================
    # CENTRAL TEAM RESOLUTION
    # ============================================================

    def _resolve_team_for_analysis(self, team_name):
        """
        Resolve an explicitly requested team through BSD.

        The watchlist is used only to determine whether the team is
        followed and to preserve its preferred name.

        The stored watchlist ID is NOT authoritative.

        BSD men's-only search is used to prevent accidental
        resolution to women's, reserve, or youth teams.
        """
        if team_name is None:
            return {
                "status": "error",
                "message": (
                    "Team name or team ID cannot be empty."
                ),
            }

        numeric_team_id = self._safe_int(team_name)

        if numeric_team_id is not None:
            try:
                team_data = self.football._bsd_request(
                    f"teams/{numeric_team_id}/"
                )
            except Exception as error:
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "message": (
                        "Could not resolve the team through BSD."
                    ),
                    "error": str(error),
                }

            if not isinstance(team_data, dict):
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "message": (
                        "BSD returned invalid team information."
                    ),
                }

            team_display_name = (
                team_data.get("name")
                or team_data.get("team_name")
                or str(numeric_team_id)
            )

            if self._is_non_senior_team(
                team_display_name
            ):
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "team": team_display_name,
                    "message": (
                        "The requested BSD team is not a "
                        "senior men's club."
                    ),
                }

            enrichment = self._build_team_resolution(
                team_data,
                str(numeric_team_id),
            )

            if not enrichment:
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "message": (
                        "Could not resolve the requested BSD team."
                    ),
                }

            return {
                "status": "success",
                "team_name": enrichment.get("name"),
                "team_id": enrichment.get("id"),
                "league_ids": enrichment.get(
                    "major_league_ids",
                    [],
                ),
                "leagues": enrichment.get(
                    "major_leagues",
                    [],
                ),
                "enrichment": enrichment,
            }

        requested_name = str(team_name).strip()

        if not requested_name:
            return {
                "status": "error",
                "message": "Team name cannot be empty.",
            }

        normalized_name = self._normalize_team_name(
            requested_name
        )

        try:
            watchlist = self.watchlist.get_teams()
        except Exception:
            watchlist = []

        if not isinstance(watchlist, list):
            watchlist = []

        matched_team = None

        for team in watchlist:
            if not isinstance(team, dict):
                continue

            stored_name = self._normalize_team_name(
                team.get("name")
            )

            if stored_name == normalized_name:
                matched_team = team
                break

        if matched_team is None:
            for team in watchlist:
                if not isinstance(team, dict):
                    continue

                stored_name = self._normalize_team_name(
                    team.get("name")
                )

                if (
                    normalized_name in stored_name
                    or stored_name in normalized_name
                ):
                    matched_team = team
                    break

        selected_team_name = (
            matched_team.get("name")
            if matched_team is not None
            else requested_name
        )

        if not selected_team_name:
            selected_team_name = requested_name

        team_data = self._resolve_mens_team(
            selected_team_name
        )

        if not isinstance(team_data, dict):
            return {
                "status": "error",
                "team": selected_team_name,
                "message": (
                    f"Could not find a supported men's "
                    f"club matching '{selected_team_name}'."
                ),
            }

        enrichment = self._build_team_resolution(
            team_data,
            selected_team_name,
        )

        if not enrichment:
            return {
                "status": "error",
                "team": selected_team_name,
                "message": (
                    "BSD returned incomplete team information."
                ),
            }

        resolved_name = (
            enrichment.get("name")
            or selected_team_name
        )

        resolved_team_id = self._safe_int(
            enrichment.get("id")
        )

        if resolved_team_id is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "message": (
                    "BSD team resolution returned no valid "
                    "team ID."
                ),
            }

        if not self._team_name_matches(
            selected_team_name,
            resolved_name,
        ):
            return {
                "status": "error",
                "team": selected_team_name,
                "message": (
                    "BSD returned a different team than "
                    "the requested club."
                ),
                "resolved_team": resolved_name,
                "resolved_team_id": resolved_team_id,
            }

        return {
            "status": "success",
            "team_name": resolved_name,
            "team_id": resolved_team_id,
            "league_ids": enrichment.get(
                "major_league_ids",
                [],
            ),
            "leagues": enrichment.get(
                "major_leagues",
                [],
            ),
            "enrichment": enrichment,
        }

    # ============================================================
    # TEAM SEARCH
    # ============================================================

    def search_teams(self, team_name):
        """
        Search men's club football teams using BSD.
        """
        if team_name is None:
            return {
                "status": "error",
                "error": "Team name cannot be empty.",
            }

        team_name = str(team_name).strip()

        if not team_name:
            return {
                "status": "error",
                "error": "Team name cannot be empty.",
            }

        raw_results = self._search_mens_team_candidates(
            team_name
        )

        if not raw_results:
            return {
                "status": "success",
                "query": team_name,
                "teams": [],
            }

        results = []

        for item in raw_results:
            candidate_id = self._safe_int(
                item.get("id")
            )

            candidate_name = (
                item.get("name")
                or item.get("team_name")
                or item.get("short_name")
            )

            if (
                candidate_id is None
                or not candidate_name
            ):
                continue

            enrichment = self._build_team_resolution(
                item,
                candidate_name,
            )

            if not enrichment:
                continue

            major_league_ids = enrichment.get(
                "major_league_ids",
                [],
            )

            major_leagues = enrichment.get(
                "major_leagues",
                [],
            )

            league_id = (
                major_league_ids[0]
                if major_league_ids
                else None
            )

            league_name = (
                major_leagues[0]
                if major_leagues
                else None
            )

            results.append(
                {
                    "id": candidate_id,
                    "name": candidate_name,
                    "country": item.get("country"),
                    "logo": self.football._get_bsd_team_logo(
                        candidate_id
                    ),
                    "venue": item.get("venue"),
                    "league_id": league_id,
                    "league_name": league_name,
                    "major_league_ids": major_league_ids,
                    "major_leagues": major_leagues,
                }
            )

        return {
            "status": "success",
            "query": team_name,
            "teams": results,
        }

    # ============================================================
    # WATCHLIST
    # ============================================================

    def add_team(self, team_id):
        """
        Add a BSD team to the current user's watchlist.
        """
        team_id = self._safe_int(team_id)

        if team_id is None:
            return {
                "status": "error",
                "error": "Invalid team ID.",
            }

        try:
            team_data = self.football._bsd_request(
                f"teams/{team_id}/"
            )
        except Exception as error:
            return {
                "status": "error",
                "team_id": team_id,
                "error": str(error),
            }

        if not isinstance(team_data, dict):
            return {
                "status": "error",
                "team_id": team_id,
                "error": (
                    "BSD returned invalid team information."
                ),
            }

        team_name = team_data.get("name")

        if not team_name:
            return {
                "status": "error",
                "team_id": team_id,
                "error": (
                    "Team information was incomplete."
                ),
            }

        if self._is_non_senior_team(team_name):
            return {
                "status": "error",
                "team_id": team_id,
                "team": team_name,
                "error": (
                    "Only senior men's club teams can "
                    "be added to the watchlist."
                ),
            }

        candidates = self._search_mens_team_candidates(
            team_name
        )

        matching_candidate = None

        for candidate in candidates:
            candidate_id = self._safe_int(
                candidate.get("id")
            )

            if candidate_id == team_id:
                matching_candidate = candidate
                break

        if matching_candidate is None:
            return {
                "status": "error",
                "team_id": team_id,
                "team": team_name,
                "error": (
                    "The selected team could not be verified "
                    "as a supported men's senior team."
                ),
            }

        resolved_team = matching_candidate

        enrichment = self._build_team_resolution(
            resolved_team,
            team_name,
        )

        if not enrichment:
            enrichment = {
                "id": team_id,
                "name": team_name,
                "major_league_ids": [],
                "major_leagues": [],
                "raw": resolved_team,
            }

        major_league_ids = enrichment.get(
            "major_league_ids",
            [],
        )

        major_leagues = enrichment.get(
            "major_leagues",
            [],
        )

        league_id = (
            major_league_ids[0]
            if major_league_ids
            else None
        )

        league_name = (
            major_leagues[0]
            if major_leagues
            else None
        )

        stored_team = {
            "id": team_id,
            "name": team_name,
            "league_id": league_id,
            "league_name": league_name,
            "country": team_data.get("country"),
        }

        added = self.watchlist.add_team(stored_team)

        if not added:
            return {
                "status": "already_exists",
                "team": stored_team,
            }

        return {
            "status": "success",
            "message": "Team added to the watchlist.",
            "team": stored_team,
        }

    def remove_team(self, team_name):
        """
        Remove a team from the user's watchlist.
        """
        if team_name is None:
            return {
                "status": "error",
                "error": "Team name cannot be empty.",
            }

        normalized_name = self._normalize_team_name(
            team_name
        )

        teams = self.watchlist.get_teams()

        selected_team = None

        for team in teams:
            name = self._normalize_team_name(
                team.get("name")
            )

            if name == normalized_name:
                selected_team = team
                break

        if selected_team is None:
            for team in teams:
                name = self._normalize_team_name(
                    team.get("name")
                )

                if (
                    normalized_name in name
                    or name in normalized_name
                ):
                    selected_team = team
                    break

        if selected_team is None:
            return {
                "status": "error",
                "team": team_name,
                "error": (
                    f"{team_name} is not currently in "
                    "the user's watchlist."
                ),
            }

        removed = self.watchlist.remove_team(
            selected_team.get("id")
        )

        if not removed:
            return {
                "status": "error",
                "team": selected_team.get("name"),
                "error": "Team could not be removed.",
            }

        return {
            "status": "success",
            "message": "Team removed from the watchlist.",
            "team": selected_team.get("name"),
        }

    def get_watchlist(self):
        """
        Return the current user's watchlist.

        The stored ID is retained for compatibility, while the
        current BSD men's ID and logo are resolved dynamically.
        """
        teams = self.watchlist.get_teams()

        if not isinstance(teams, list):
            return []

        results = []

        for team in teams:
            if not isinstance(team, dict):
                continue

            team_name = team.get("name")

            if not team_name:
                continue

            current_bsd_team = self._resolve_mens_team(
                team_name
            )

            current_bsd_id = None
            logo = None
            current_league_id = team.get("league_id")
            current_league_name = team.get("league_name")

            if isinstance(current_bsd_team, dict):
                current_bsd_id = self._safe_int(
                    current_bsd_team.get("id")
                )

                if current_bsd_id is not None:
                    logo = self.football._get_bsd_team_logo(
                        current_bsd_id
                    )

                enrichment = self._build_team_resolution(
                    current_bsd_team,
                    team_name,
                )

                if enrichment:
                    league_ids = enrichment.get(
                        "major_league_ids",
                        [],
                    )

                    league_names = enrichment.get(
                        "major_leagues",
                        [],
                    )

                    if league_ids:
                        current_league_id = league_ids[0]

                    if league_names:
                        current_league_name = league_names[0]

            results.append(
                {
                    "name": team_name,
                    "id": team.get("id"),
                    "bsd_team_id": current_bsd_id,
                    "league_id": current_league_id,
                    "league_name": current_league_name,
                    "country": team.get("country"),
                    "logo": logo,
                }
            )

        return results

    # ============================================================
    # UPCOMING MATCHES
    # ============================================================

    def get_upcoming_matches(
        self,
        team_name,
        league_id=None,
    ):
        """
        Get upcoming fixtures for a watched team.

        BSD is the primary fixture provider.

        The first five genuinely upcoming fixtures are returned.

        The stored watchlist ID is not trusted.
        """
        watchlist = self.watchlist.get_teams()

        if team_name is None:
            return {
                "status": "error",
                "error": "Team name cannot be empty.",
            }

        normalized_name = self._normalize_team_name(
            team_name
        )

        selected_team = None

        for team in watchlist:
            name = self._normalize_team_name(
                team.get("name")
            )

            if name == normalized_name:
                selected_team = team
                break

        if selected_team is None:
            for team in watchlist:
                name = self._normalize_team_name(
                    team.get("name")
                )

                if (
                    normalized_name in name
                    or name in normalized_name
                ):
                    selected_team = team
                    break

        if selected_team is None:
            return {
                "status": "error",
                "error": (
                    f"{team_name} is not currently in "
                    "the user's watchlist."
                ),
            }

        selected_team_name = (
            selected_team.get("name")
            or str(team_name)
        )

        resolved = self._resolve_team_for_analysis(
            selected_team_name
        )

        if resolved.get("status") != "success":
            return {
                "status": "error",
                "team": selected_team_name,
                "error": resolved.get(
                    "error",
                    resolved.get(
                        "message",
                        "Could not resolve the team.",
                    ),
                ),
            }

        selected_team_name = resolved.get(
            "team_name",
            selected_team_name,
        )

        selected_team_id = self._safe_int(
            resolved.get("team_id")
        )

        if selected_team_id is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "error": (
                    "BSD team resolution returned no valid "
                    "team ID."
                ),
            }

        today = datetime.now(timezone.utc).date()

        date_from = today.isoformat()
        date_to = f"{SEASON + 1}-06-30"

        try:
            data = self.football.get_bsd_fixtures(
                team_name=selected_team_name,
                team_id=selected_team_id,
                season_id=None,
                date_from=date_from,
                date_to=date_to,
                league_id=league_id,
                limit=200,
                offset=0,
            )
        except Exception as error:
            return {
                "status": "error",
                "team": selected_team_name,
                "team_id": selected_team_id,
                "error": str(error),
            }

        if isinstance(data, list):
            raw_fixtures = data

        elif isinstance(data, dict):
            raw_fixtures = data.get(
                "fixtures",
                data.get("results", []),
            )

        else:
            raw_fixtures = []

        if not isinstance(raw_fixtures, list):
            raw_fixtures = []

        now = datetime.now(timezone.utc)

        fixtures = []

        for item in raw_fixtures:
            if not isinstance(item, dict):
                continue

            fixture_date = item.get("date")

            if not fixture_date:
                continue

            try:
                match_time = datetime.fromisoformat(
                    str(fixture_date).replace(
                        "Z",
                        "+00:00",
                    )
                )
            except (ValueError, TypeError):
                continue

            if match_time.tzinfo is None:
                match_time = match_time.replace(
                    tzinfo=timezone.utc
                )

            if match_time <= now:
                continue

            home_team = item.get("home_team")
            away_team = item.get("away_team")

            home_team_name = self._extract_team_name(
                home_team
            )

            away_team_name = self._extract_team_name(
                away_team
            )

            home_team_id = (
                item.get("home_team_id")
                or self._extract_team_id(home_team)
            )

            away_team_id = (
                item.get("away_team_id")
                or self._extract_team_id(away_team)
            )

            home_logo = (
                item.get("home_logo")
                or self._extract_team_logo(home_team)
            )

            away_logo = (
                item.get("away_logo")
                or self._extract_team_logo(away_team)
            )

            selected_is_home = self._team_matches(
                home_team,
                expected_team_id=selected_team_id,
                expected_team_name=selected_team_name,
            )

            selected_is_away = self._team_matches(
                away_team,
                expected_team_id=selected_team_id,
                expected_team_name=selected_team_name,
            )

            if not selected_is_home:
                selected_is_home = (
                    selected_team_id is not None
                    and self._safe_int(home_team_id)
                    == selected_team_id
                )

            if not selected_is_away:
                selected_is_away = (
                    selected_team_id is not None
                    and self._safe_int(away_team_id)
                    == selected_team_id
                )

            home_away = None

            if selected_is_home:
                home_away = "Home"
            elif selected_is_away:
                home_away = "Away"

            if home_away is None:
                continue

            if item.get("home_away") in ("Home", "Away"):
                home_away = item.get("home_away")

            local_match_time = (
                self.timezone.convert_utc_to_local(
                    match_time
                )
            )

            competition_name = (
                self._extract_competition_name(item)
            )

            competition_display_name = (
                self.COMPETITION_DISPLAY_NAMES.get(
                    competition_name,
                    competition_name,
                )
            )

            competition_id = (
                self._extract_competition_id(item)
            )

            fixtures.append(
                {
                    "fixture_id": item.get("fixture_id"),
                    "date": item.get("date"),
                    "local_date": local_match_time.strftime(
                        "%Y-%m-%d"
                    ),
                    "local_time": local_match_time.strftime(
                        "%I:%M %p"
                    ),
                    "local_timezone": (
                        self.timezone.get_timezone_name()
                    ),
                    "status": item.get("status"),
                    "home_team": home_team_name,
                    "away_team": away_team_name,
                    "home_team_id": self._safe_int(
                        home_team_id
                    ),
                    "away_team_id": self._safe_int(
                        away_team_id
                    ),
                    "home_logo": home_logo,
                    "away_logo": away_logo,
                    "venue": self._extract_venue_name(item),
                    "venue_id": item.get("venue_id"),
                    "venue_city": self._extract_venue_city(item),
                    "venue_country": (
                        self._extract_venue_country(item)
                    ),
                    "home_away": home_away,
                    "competition_id": competition_id,
                    "competition_name": competition_name,
                    "competition_display_name": (
                        competition_display_name
                    ),
                    "competition_type": item.get(
                        "competition_type"
                    ),
                    "competition_country": item.get(
                        "competition_country"
                    ),
                    "season": item.get("season"),
                    "season_id": item.get("season_id"),
                    "season_name": item.get("season_name"),
                    "stage": item.get("stage"),
                    "stage_name": item.get("stage_name"),
                    "round": item.get("round"),
                    "round_label": item.get("round_label"),
                }
            )

        fixtures.sort(
            key=lambda fixture: fixture["date"]
        )

        fixtures = fixtures[:5]

        return {
            "status": "success",
            "team": selected_team_name,
            "team_id": selected_team_id,
            "fixtures": fixtures,
        }

    # ============================================================
    # CURRENT BSD SEASON HELPER
    # ============================================================

    def _get_current_bsd_season(self, league_id):
        """
        Resolve the current season for a BSD league.

        BSD's current-season endpoint returns:

            {
                "league_id": 3,
                "season": {
                    "id": 1307,
                    "name": "LaLiga 26/27",
                    "year": 2026,
                    "is_current": true,
                    ...
                }
            }

        The important part is that the season is returned under
        the top-level `season` key.
        """
        if league_id is None:
            return None

        league_id = self._safe_int(league_id)

        if league_id is None:
            return None

        try:
            data = self.football._bsd_request(
                f"leagues/{league_id}/season/"
            )
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        # --------------------------------------------------------
        # CONFIRMED BSD FORMAT:
        #
        # {
        #     "league_id": 3,
        #     "season": {
        #         "id": 1307,
        #         "name": "LaLiga 26/27",
        #         "is_current": True
        #     }
        # }
        # --------------------------------------------------------

        current_season = data.get("season")

        if isinstance(current_season, dict):
            season_id = (
                current_season.get("id")
                or current_season.get("season_id")
            )

            season_id = self._safe_int(season_id)

            if season_id is not None:
                return season_id

        # --------------------------------------------------------
        # Compatibility with possible list/dict responses.
        # --------------------------------------------------------

        raw_seasons = data.get(
            "seasons",
            data.get(
                "results",
                data.get(
                    "data",
                    [],
                ),
            ),
        )

        if isinstance(raw_seasons, dict):
            raw_seasons = [raw_seasons]

        if not isinstance(raw_seasons, list):
            raw_seasons = []

        if not raw_seasons:
            return None

        for season in raw_seasons:
            if not isinstance(season, dict):
                continue

            if (
                season.get("is_current") is True
                or season.get("current") is True
                or season.get("active") is True
            ):
                season_id = (
                    season.get("id")
                    or season.get("season_id")
                )

                season_id = self._safe_int(season_id)

                if season_id is not None:
                    return season_id

        configured_season_text = str(SEASON)

        for season in raw_seasons:
            if not isinstance(season, dict):
                continue

            season_name = str(
                season.get("name")
                or season.get("season_name")
                or ""
            )

            if configured_season_text in season_name:
                season_id = (
                    season.get("id")
                    or season.get("season_id")
                )

                season_id = self._safe_int(season_id)

                if season_id is not None:
                    return season_id

        valid = []

        for season in raw_seasons:
            if not isinstance(season, dict):
                continue

            season_id = (
                season.get("id")
                or season.get("season_id")
            )

            season_id = self._safe_int(season_id)

            if season_id is not None:
                valid.append(
                    (
                        season_id,
                        season,
                    )
                )

        if not valid:
            return None

        valid.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return valid[0][0]

    # ============================================================
    # TEAM RESULTS
    # ============================================================

    def get_team_results(
        self,
        team_name: str,
        league_id: int | None = None,
    ) -> dict:
        """
        Get completed results for an explicitly requested team.

        BSD is the primary source for completed match data.
        """
        resolved = self._resolve_team_for_analysis(
            team_name
        )

        if resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": resolved.get(
                    "message",
                    "Could not resolve the team.",
                ),
                "error": resolved.get("error"),
                "results": [],
            }

        selected_team_name = resolved.get("team_name")
        bsd_team_id = resolved.get("team_id")

        enrichment = resolved.get("enrichment", {})

        if league_id is None:
            league_ids = enrichment.get(
                "major_league_ids",
                [],
            )

            if league_ids:
                league_id = league_ids[0]

        season_id = None

        if league_id is not None:
            try:
                season_id = self._get_current_bsd_season(
                    league_id
                )
            except Exception as error:
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "league_id": league_id,
                    "message": (
                        "Could not determine the current "
                        "BSD season."
                    ),
                    "error": str(error),
                    "results": [],
                }

        try:
            data = self.football.get_bsd_results(
                team_id=bsd_team_id,
                season_id=season_id,
                league_id=league_id,
                limit=200,
            )
        except Exception as error:
            return {
                "status": "error",
                "team": selected_team_name,
                "league_id": league_id,
                "season_id": season_id,
                "message": (
                    "Could not retrieve completed "
                    "match results."
                ),
                "error": str(error),
                "results": [],
            }

        if isinstance(data, list):
            raw_results = data

        elif isinstance(data, dict):
            raw_results = data.get(
                "results",
                data.get("data", []),
            )

        else:
            raw_results = []

        if not isinstance(raw_results, list):
            raw_results = []

        results = []

        for match in raw_results:
            if not isinstance(match, dict):
                continue

            date_value = match.get("date")

            local_date = None
            local_time = None
            local_timezone = (
                self.timezone.get_timezone_name()
            )

            if date_value:
                try:
                    parsed = datetime.fromisoformat(
                        str(date_value).replace(
                            "Z",
                            "+00:00",
                        )
                    )

                    if parsed.tzinfo is None:
                        parsed = parsed.replace(
                            tzinfo=timezone.utc
                        )

                    local_dt = (
                        self.timezone.convert_utc_to_local(
                            parsed
                        )
                    )

                    local_date = local_dt.strftime(
                        "%Y-%m-%d"
                    )

                    local_time = local_dt.strftime(
                        "%I:%M %p"
                    )
                except (ValueError, TypeError):
                    pass

            home_team = match.get("home_team")
            away_team = match.get("away_team")

            home_team_name = self._extract_team_name(
                home_team
            )

            away_team_name = self._extract_team_name(
                away_team
            )

            home_team_id = (
                match.get("home_team_id")
                or self._extract_team_id(home_team)
            )

            away_team_id = (
                match.get("away_team_id")
                or self._extract_team_id(away_team)
            )

            home_logo = (
                match.get("home_logo")
                or self._extract_team_logo(home_team)
            )

            away_logo = (
                match.get("away_logo")
                or self._extract_team_logo(away_team)
            )

            contains_team = (
                self._team_matches(
                    home_team,
                    expected_team_id=bsd_team_id,
                    expected_team_name=selected_team_name,
                )
                or self._team_matches(
                    away_team,
                    expected_team_id=bsd_team_id,
                    expected_team_name=selected_team_name,
                )
                or (
                    self._safe_int(home_team_id)
                    == self._safe_int(bsd_team_id)
                )
                or (
                    self._safe_int(away_team_id)
                    == self._safe_int(bsd_team_id)
                )
            )

            if not contains_team:
                continue

            competition_name = (
                self._extract_competition_name(match)
            )

            competition_display_name = (
                self.COMPETITION_DISPLAY_NAMES.get(
                    competition_name,
                    competition_name,
                )
            )

            competition_id = (
                self._extract_competition_id(match)
            )

            results.append(
                {
                    "fixture_id": match.get("fixture_id"),
                    "date": date_value,
                    "local_date": local_date,
                    "local_time": local_time,
                    "local_timezone": local_timezone,
                    "status": match.get("status"),
                    "home_team": home_team_name,
                    "home_team_id": self._safe_int(
                        home_team_id
                    ),
                    "away_team": away_team_name,
                    "away_team_id": self._safe_int(
                        away_team_id
                    ),
                    "home_score": match.get("home_score"),
                    "away_score": match.get("away_score"),
                    "result": match.get("result"),
                    "competition_id": competition_id,
                    "competition_name": competition_name,
                    "competition_display_name": (
                        competition_display_name
                    ),
                    "competition_country": match.get(
                        "competition_country"
                    ),
                    "season_id": match.get("season_id"),
                    "stage": match.get("stage"),
                    "stage_name": match.get("stage_name"),
                    "round": match.get("round"),
                    "round_name": match.get("round_name"),
                    "round_label": match.get("round_label"),
                    "venue": self._extract_venue_name(match),
                    "venue_id": match.get("venue_id"),
                    "venue_city": self._extract_venue_city(match),
                    "venue_country": (
                        self._extract_venue_country(match)
                    ),
                    "home_logo": home_logo,
                    "away_logo": away_logo,
                }
            )

        latest_match = None
        latest_match_details = None
        latest_match_details_error = None

        dated_results = []

        for result in results:
            date_value = result.get("date")

            if not date_value:
                continue

            try:
                parsed_date = datetime.fromisoformat(
                    str(date_value).replace(
                        "Z",
                        "+00:00",
                    )
                )

                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(
                        tzinfo=timezone.utc
                    )

                dated_results.append(
                    (
                        parsed_date,
                        result,
                    )
                )
            except (ValueError, TypeError):
                continue

        if dated_results:
            dated_results.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            latest_match = dated_results[0][1]

        elif results:
            latest_match = results[0]

        if latest_match is not None:
            fixture_id = latest_match.get("fixture_id")

            if fixture_id is not None:
                try:
                    latest_match_details = (
                        self.football.get_bsd_match_details(
                            fixture_id,
                            requested_team_id=bsd_team_id,
                        )
                    )

                    if not isinstance(
                        latest_match_details,
                        dict,
                    ):
                        latest_match_details = None

                except Exception as error:
                    latest_match_details_error = str(error)

        response = {
            "status": "success",
            "team": {
                "id": bsd_team_id,
                "name": selected_team_name,
                "logo": self.football._get_bsd_team_logo(
                    bsd_team_id
                ),
            },
            "league_id": league_id,
            "season_id": season_id,
            "count": len(results),
            "results": results,
            "latest_match": latest_match,
            "latest_match_details": latest_match_details,
        }

        if latest_match_details_error:
            response["latest_match_details_error"] = (
                latest_match_details_error
            )

        return response

    # ============================================================
    # LEAGUE STANDINGS
    # ============================================================

    def get_league_standings(
        self,
        team_name: str,
        league_id: int | None = None,
    ) -> dict:
        """
        Get the current league standings and the requested team's
        position.
        """
        resolved = self._resolve_team_for_analysis(
            team_name
        )

        if resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": resolved.get(
                    "message",
                    "Could not resolve the team.",
                ),
                "error": resolved.get("error"),
                "standings": [],
            }

        selected_team_name = resolved.get("team_name")
        bsd_team_id = resolved.get("team_id")

        enrichment = resolved.get("enrichment", {})

        if league_id is None:
            league_ids = enrichment.get(
                "major_league_ids",
                [],
            )

            if league_ids:
                league_id = league_ids[0]

        # --------------------------------------------------------
        # IMPORTANT:
        #
        # Some BSD team responses do not contain league metadata.
        # Real Madrid is one confirmed example:
        #
        # team_id = 57
        # league_id = 3
        #
        # Therefore, when the team enrichment does not provide a
        # league, infer it from the known major men's leagues by
        # checking the current standings for the resolved team.
        #
        # This keeps the team resolver generic while allowing
        # standings to work with BSD's actual team response shape.
        # --------------------------------------------------------

        if league_id is None:
            for candidate_league_id in self.MAJOR_LEAGUE_IDS:
                candidate_league_id = self._safe_int(
                    candidate_league_id
                )

                if candidate_league_id is None:
                    continue

                try:
                    candidate_season_id = (
                        self._get_current_bsd_season(
                            candidate_league_id
                        )
                    )
                except Exception:
                    candidate_season_id = None

                if candidate_season_id is None:
                    continue

                try:
                    candidate_data = (
                        self.football.get_bsd_standings(
                            league_id=candidate_league_id,
                            season_id=candidate_season_id,
                        )
                    )
                except Exception:
                    continue

                if isinstance(candidate_data, list):
                    candidate_standings = candidate_data

                elif isinstance(candidate_data, dict):
                    candidate_standings = candidate_data.get(
                        "standings",
                        candidate_data.get(
                            "results",
                            candidate_data.get(
                                "data",
                                [],
                            ),
                        ),
                    )

                else:
                    candidate_standings = []

                if not isinstance(
                    candidate_standings,
                    list,
                ):
                    continue

                for row in candidate_standings:
                    if not isinstance(row, dict):
                        continue

                    row_team_id = (
                        row.get("team_id")
                        or self._extract_team_id(
                            row.get("team")
                        )
                    )

                    if (
                        self._safe_int(row_team_id)
                        == self._safe_int(bsd_team_id)
                    ):
                        league_id = candidate_league_id
                        break

                if league_id is not None:
                    break

        if league_id is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "message": (
                    f"No supported league is associated "
                    f"with {selected_team_name}."
                ),
                "standings": [],
            }

        season_id = None

        try:
            season_id = self._get_current_bsd_season(
                league_id
            )
        except Exception as error:
            return {
                "status": "error",
                "team": selected_team_name,
                "league_id": league_id,
                "message": (
                    "Could not determine the current "
                    "BSD season."
                ),
                "error": str(error),
                "standings": [],
            }

        if season_id is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "league_id": league_id,
                "message": (
                    "BSD returned no current season for "
                    "the requested league."
                ),
                "standings": [],
            }

        try:
            data = self.football.get_bsd_standings(
                league_id=league_id,
                season_id=season_id,
            )
        except Exception as error:
            return {
                "status": "error",
                "team": selected_team_name,
                "league_id": league_id,
                "season_id": season_id,
                "message": (
                    "Could not retrieve league standings."
                ),
                "error": str(error),
                "standings": [],
            }

        if isinstance(data, list):
            standings = data

        elif isinstance(data, dict):
            standings = data.get(
                "standings",
                data.get(
                    "results",
                    data.get(
                        "data",
                        [],
                    ),
                ),
            )

        else:
            standings = []

        if not isinstance(standings, list):
            standings = []

        team_row = None

        for row in standings:
            if not isinstance(row, dict):
                continue

            row_team_id = (
                row.get("team_id")
                or self._extract_team_id(
                    row.get("team")
                )
            )

            if (
                self._safe_int(row_team_id)
                == self._safe_int(bsd_team_id)
            ):
                team_row = row
                break

        if team_row is None:
            normalized_resolved_name = (
                self._normalize_team_name(
                    selected_team_name
                )
            )

            for row in standings:
                if not isinstance(row, dict):
                    continue

                row_name = (
                    row.get("team_name")
                    or self._extract_team_name(
                        row.get("team")
                    )
                    or ""
                )

                row_name = self._normalize_team_name(
                    row_name
                )

                if row_name == normalized_resolved_name:
                    team_row = row
                    break

        league_name = self.MAJOR_LEAGUE_IDS.get(
            self._safe_int(league_id)
        )

        return {
            "status": "success",
            "team": {
                "id": bsd_team_id,
                "name": selected_team_name,
                "logo": self.football._get_bsd_team_logo(
                    bsd_team_id
                ),
            },
            "league_id": league_id,
            "league_name": league_name,
            "season_id": season_id,
            "team_standing": team_row,
            "standings": standings,
            "count": len(standings),
        }

    # ============================================================
    # SQUAD
    # ============================================================

    def get_team_squad(self, team_name):
        """
        Get the squad for a watched team.

        Accepts:
        - team name, e.g. "Real Madrid"
        - BSD team ID, e.g. 57

        The team is resolved to a men's senior BSD team before
        requesting the squad.
        """
        if team_name is None:
            return {
                "status": "error",
                "error": (
                    "Team name or team ID cannot be empty."
                ),
            }

        numeric_team_id = self._safe_int(team_name)

        if numeric_team_id is not None:
            try:
                resolved_team = self.football._bsd_request(
                    f"teams/{numeric_team_id}/"
                )
            except Exception as error:
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "message": (
                        "Could not retrieve BSD team information."
                    ),
                    "error": str(error),
                }

            if not isinstance(resolved_team, dict):
                return {
                    "status": "error",
                    "team_id": numeric_team_id,
                    "message": (
                        "BSD returned invalid team information."
                    ),
                }

            selected_team_name = (
                resolved_team.get("name")
                or resolved_team.get("team_name")
                or str(numeric_team_id)
            )

            bsd_team_id = numeric_team_id

        else:
            requested_name = str(team_name).strip()

            if not requested_name:
                return {
                    "status": "error",
                    "error": (
                        "Team name cannot be empty."
                    ),
                }

            watchlist = self.watchlist.get_teams()

            if not isinstance(watchlist, list):
                watchlist = []

            selected_watchlist_team = None

            normalized_requested = (
                self._normalize_team_name(
                    requested_name
                )
            )

            for team in watchlist:
                if not isinstance(team, dict):
                    continue

                stored_name = (
                    self._normalize_team_name(
                        team.get("name")
                    )
                )

                if stored_name == normalized_requested:
                    selected_watchlist_team = team
                    break

            if selected_watchlist_team is None:
                for team in watchlist:
                    if not isinstance(team, dict):
                        continue

                    stored_name = (
                        self._normalize_team_name(
                            team.get("name")
                        )
                    )

                    if (
                        normalized_requested in stored_name
                        or stored_name in normalized_requested
                    ):
                        selected_watchlist_team = team
                        break

            if selected_watchlist_team is None:
                return {
                    "status": "error",
                    "team": requested_name,
                    "error": (
                        f"{requested_name} is not currently "
                        "in the user's watchlist."
                    ),
                }

            selected_team_name = (
                selected_watchlist_team.get("name")
                or requested_name
            )

            resolved_team = self._resolve_mens_team(
                selected_team_name
            )

            if not isinstance(resolved_team, dict):
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "message": (
                        "Could not resolve the followed team "
                        "to a men's senior BSD team."
                    ),
                    "error": (
                        "BSD men's team resolution returned "
                        "no matching team."
                    ),
                }

            bsd_team_id = self._safe_int(
                resolved_team.get("id")
                or resolved_team.get("team_id")
            )

            resolved_name = (
                resolved_team.get("name")
                or resolved_team.get("team_name")
                or selected_team_name
            )

            if bsd_team_id is None:
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "message": (
                        "BSD team resolution returned no "
                        "valid team ID."
                    ),
                }

            if not self._team_name_matches(
                selected_team_name,
                resolved_name,
            ):
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "message": (
                        "BSD returned a different team than "
                        "the requested club."
                    ),
                    "resolved_team": resolved_name,
                    "resolved_team_id": bsd_team_id,
                }

            selected_team_name = resolved_name

        try:
            squad_data = self.football.get_bsd_squad(
                bsd_team_id
            )
        except Exception as error:
            return {
                "status": "error",
                "team": selected_team_name,
                "team_id": bsd_team_id,
                "message": (
                    "Could not retrieve the team squad from BSD."
                ),
                "error": str(error),
            }

        if isinstance(squad_data, dict):
            provider_status = squad_data.get("status")

            if provider_status == "error":
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "team_id": bsd_team_id,
                    "message": (
                        squad_data.get("message")
                        or "BSD could not retrieve the squad."
                    ),
                    "error": squad_data.get("error"),
                }

        if isinstance(squad_data, list):
            raw_players = squad_data

        elif isinstance(squad_data, dict):
            raw_players = squad_data.get("players")

            if raw_players is None:
                raw_players = squad_data.get("data")

            if raw_players is None:
                raw_players = squad_data.get("results")

        else:
            raw_players = None

        if raw_players is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "team_id": bsd_team_id,
                "message": (
                    "BSD returned no recognizable squad data."
                ),
                "error": (
                    f"Unexpected squad response type: "
                    f"{type(squad_data).__name__}"
                ),
            }

        if not isinstance(raw_players, list):
            return {
                "status": "error",
                "team": selected_team_name,
                "team_id": bsd_team_id,
                "message": (
                    "BSD returned an invalid squad format."
                ),
                "error": "Expected a list of players.",
            }

        players = []

        for player in raw_players:
            if not isinstance(player, dict):
                continue

            nested_player = player.get("player")

            if isinstance(nested_player, dict):
                merged_player = {
                    **nested_player,
                    **player,
                }
            else:
                merged_player = dict(player)

            player_id = self._safe_int(
                merged_player.get("id")
                or merged_player.get("player_id")
            )

            player_name = (
                merged_player.get("name")
                or merged_player.get("player_name")
            )

            if not player_name:
                continue

            players.append(
                {
                    "id": player_id,
                    "name": player_name,
                    "short_name": merged_player.get(
                        "short_name"
                    ),
                    "position": (
                        merged_player.get("position")
                        or merged_player.get("position_name")
                    ),
                    "jersey_number": (
                        merged_player.get("jersey_number")
                        or merged_player.get("number")
                        or merged_player.get("shirt_number")
                    ),
                    "nationality": (
                        merged_player.get("nationality")
                        or merged_player.get("nationality_name")
                    ),
                    "date_of_birth": (
                        merged_player.get("date_of_birth")
                        or merged_player.get("birth_date")
                    ),
                    "availability": merged_player.get(
                        "availability"
                    ),
                    "injury_type": (
                        merged_player.get("injury_type")
                        or merged_player.get("injury")
                    ),
                    "injury_expected_return": (
                        merged_player.get(
                            "injury_expected_return"
                        )
                        or merged_player.get(
                            "expected_return"
                        )
                    ),
                    "photo": (
                        merged_player.get("photo")
                        or merged_player.get("photo_url")
                    ),
                }
            )

        if not players and raw_players:
            return {
                "status": "error",
                "team": selected_team_name,
                "team_id": bsd_team_id,
                "message": (
                    "BSD returned squad records, but none of "
                    "the player records contained usable data."
                ),
                "error": (
                    "Player records could not be normalized."
                ),
            }

        enrichment = self._build_team_resolution(
            resolved_team,
            selected_team_name,
        )

        if not enrichment:
            enrichment = {
                "major_league_ids": [],
                "major_leagues": [],
            }

        team_logo = self.football._get_bsd_team_logo(
            bsd_team_id
        )

        return {
            "status": "success",
            "team": selected_team_name,
            "team_id": bsd_team_id,
            "team_logo": team_logo,
            "league_ids": enrichment.get(
                "major_league_ids",
                [],
            ),
            "leagues": enrichment.get(
                "major_leagues",
                [],
            ),
            "player_count": len(players),
            "players": players,
        }

    # ============================================================
    # LIVE MATCHES
    # ============================================================

    def get_live_matches(self):
        """
        Get currently live football matches.

        KickoffAPI remains the live-score provider for now.
        """
        try:
            data = self.football.get_live_scores()
        except Exception as error:
            return {
                "status": "error",
                "error": str(error),
            }

        if not isinstance(data, dict):
            return {
                "status": "success",
                "matches": [],
            }

        matches = []

        for item in data.get("response", []):
            if not isinstance(item, dict):
                continue

            home_team = item.get("homeTeam", {})
            away_team = item.get("awayTeam", {})

            if not isinstance(home_team, dict):
                home_team = {}

            if not isinstance(away_team, dict):
                away_team = {}

            league_id = item.get("leagueId")

            competition = (
                self._get_competition_metadata(
                    league_id
                )
            )

            matches.append(
                {
                    "fixture_id": item.get("id"),
                    "home_team": home_team.get("name"),
                    "away_team": away_team.get("name"),
                    "home_score": item.get("goalsHome"),
                    "away_score": item.get("goalsAway"),
                    "minute": item.get("elapsed"),
                    "status": item.get("statusLong"),
                    "competition_id": league_id,
                    "competition_display_name": (
                        competition.get(
                            "competition_display_name"
                        )
                    ),
                    "competition_type": (
                        competition.get(
                            "competition_type"
                        )
                    ),
                    "competition_country": (
                        competition.get(
                            "competition_country"
                        )
                    ),
                    "league_id": league_id,
                }
            )

        return {
            "status": "success",
            "matches": matches,
        }

    # ============================================================
    # TV / BROADCASTS
    # ============================================================

    def get_match_broadcasts(
        self,
        event_id,
        country_code=None,
    ):
        """
        Get TV/broadcast listings for a specific match.
        """
        try:
            event_id = self._safe_int(event_id)

            if event_id is None:
                return {
                    "status": "error",
                    "event_id": event_id,
                    "broadcasts": [],
                    "count": 0,
                    "message": "Invalid event ID.",
                }

            broadcasts = self.football.get_bsd_broadcasts(
                event_id=event_id,
                country_code=country_code,
            )

            if not isinstance(broadcasts, list):
                broadcasts = []

            resolved_country_code = country_code

            if resolved_country_code is None and broadcasts:
                first = broadcasts[0]
                if isinstance(first, dict):
                    resolved_country_code = first.get("country_code")

            return {
                "status": "success",
                "event_id": event_id,
                "country_code": resolved_country_code,
                "broadcasts": broadcasts,
                "count": len(broadcasts),
            }

        except Exception as exc:
            return {
                "status": "error",
                "event_id": event_id,
                "broadcasts": [],
                "count": 0,
                "message": str(exc),
            }

    # ============================================================
    # MATCH SOCIAL
    # ============================================================

    def get_match_social(
        self,
        event_id,
        limit=10,
    ):
        """
        Get social posts/videos linked to a specific match.
        """
        try:
            event_id = self._safe_int(event_id)

            if event_id is None:
                return {
                    "status": "error",
                    "event_id": event_id,
                    "social": [],
                    "count": 0,
                    "message": "Invalid event ID.",
                }

            try:
                limit = max(1, min(int(limit), 50))
            except (TypeError, ValueError):
                limit = 10

            social = self.football.get_bsd_social(
                event_id=event_id,
                limit=limit,
            )

            if not isinstance(social, list):
                social = []

            return {
                "status": "success",
                "event_id": event_id,
                "social": social,
                "count": len(social),
            }

        except Exception as exc:
            return {
                "status": "error",
                "event_id": event_id,
                "social": [],
                "count": 0,
                "message": str(exc),
            }

    # ============================================================
    # TEAM SOCIAL
    # ============================================================

    def get_team_social(
        self,
        team_name,
        limit=10,
    ):
        """
        Get recent social posts/videos linked to a football team.
        """
        try:
            resolved = self._resolve_team_for_analysis(team_name)

            if resolved.get("status") != "success":
                return {
                    "status": "error",
                    "team": team_name,
                    "social": [],
                    "count": 0,
                    "message": resolved.get(
                        "message",
                        resolved.get(
                            "error",
                            f"Could not resolve team: {team_name}",
                        ),
                    ),
                }

            team_id = self._safe_int(resolved.get("team_id"))
            resolved_team_name = resolved.get("team_name", team_name)

            if team_id is None:
                return {
                    "status": "error",
                    "team": resolved_team_name,
                    "social": [],
                    "count": 0,
                    "message": (
                        "Team resolution returned no valid BSD team ID."
                    ),
                }

            try:
                limit = max(1, min(int(limit), 50))
            except (TypeError, ValueError):
                limit = 10

            social = self.football.get_bsd_social(
                team_id=team_id,
                limit=limit,
            )

            if not isinstance(social, list):
                social = []

            return {
                "status": "success",
                "team": resolved_team_name,
                "team_id": team_id,
                "social": social,
                "count": len(social),
            }

        except Exception as exc:
            return {
                "status": "error",
                "team": team_name,
                "social": [],
                "count": 0,
                "message": str(exc),
            }

    # ============================================================
    # MATCH MONITOR
    # ============================================================

    def monitor_match(
        self,
        home_team,
        away_team,
        match_date=None,
    ):
        """
        Resolve and monitor a specific football match.

        This is intentionally independent of the user's watchlist, so
        one-off matches such as Portugal vs Wales can be monitored
        without permanently adding either team.

        The method resolves the match through BSD, then fetches rich
        match details plus TV broadcasts and social posts.
        Calling it again refreshes the live state.
        """
        try:
            from datetime import datetime, timezone

            if not home_team or not away_team:
                return {
                    "status": "error",
                    "message": "Both home_team and away_team are required.",
                }

            if match_date:
                date_value = str(match_date).strip()
            else:
                date_value = datetime.now(timezone.utc).date().isoformat()

            home_resolved = self._resolve_team_for_analysis(home_team)
            away_resolved = self._resolve_team_for_analysis(away_team)

            if home_resolved.get("status") != "success":
                return {
                    "status": "error",
                    "message": home_resolved.get(
                        "message",
                        home_resolved.get(
                            "error",
                            f"Could not resolve home team: {home_team}",
                        ),
                    ),
                }

            if away_resolved.get("status") != "success":
                return {
                    "status": "error",
                    "message": away_resolved.get(
                        "message",
                        away_resolved.get(
                            "error",
                            f"Could not resolve away team: {away_team}",
                        ),
                    ),
                }

            home_id = self._safe_int(home_resolved.get("team_id"))
            away_id = self._safe_int(away_resolved.get("team_id"))

            if home_id is None or away_id is None:
                return {
                    "status": "error",
                    "message": "Could not resolve valid BSD team IDs for both teams.",
                }

            events = self.football._get_bsd_events(
                team_id=home_id,
                date_from=date_value,
                date_to=date_value,
                limit=50,
                offset=0,
            )

            if not isinstance(events, list):
                events = []

            matched_event = None

            for event in events:
                if not isinstance(event, dict):
                    continue

                event_home = self._extract_team_name(
                    event.get("home_team")
                ) or event.get("home_team_name")
                event_away = self._extract_team_name(
                    event.get("away_team")
                ) or event.get("away_team_name")

                event_home_id = self._safe_int(
                    self._extract_team_id(event.get("home_team"))
                    or event.get("home_team_id")
                )
                event_away_id = self._safe_int(
                    self._extract_team_id(event.get("away_team"))
                    or event.get("away_team_id")
                )

                ids_match = (
                    event_home_id == home_id
                    and event_away_id == away_id
                )

                names_match = (
                    self._team_name_matches_safely(home_team, event_home)
                    and self._team_name_matches_safely(away_team, event_away)
                )

                if ids_match or names_match:
                    matched_event = event
                    break

            if matched_event is None:
                return {
                    "status": "error",
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": date_value,
                    "message": (
                        f"No match found for {home_team} vs {away_team} "
                        f"on {date_value}."
                    ),
                }

            event_id = self._safe_int(
                matched_event.get("fixture_id")
                or matched_event.get("event_id")
                or matched_event.get("id")
            )

            if event_id is None:
                return {
                    "status": "error",
                    "message": "BSD returned the match without a valid event ID.",
                }

            details = self.football.get_bsd_match_details(event_id)

            try:
                broadcasts = self.football.get_bsd_broadcasts(
                    event_id=event_id,
                )
            except Exception as exc:
                broadcasts = []
                broadcast_error = str(exc)
            else:
                broadcast_error = None

            try:
                social = self.football.get_bsd_social(
                    event_id=event_id,
                    limit=10,
                )
            except Exception as exc:
                social = []
                social_error = str(exc)
            else:
                social_error = None

            return {
                "status": "success",
                "event_id": event_id,
                "home_team": home_team,
                "away_team": away_team,
                "match_date": date_value,
                "match": details if isinstance(details, dict) else matched_event,
                "broadcasts": broadcasts if isinstance(broadcasts, list) else [],
                "social": social if isinstance(social, list) else [],
                "broadcast_error": broadcast_error,
                "social_error": social_error,
            }

        except Exception as exc:
            return {
                "status": "error",
                "home_team": home_team,
                "away_team": away_team,
                "message": str(exc),
            }

    def get_team_transfers(self, team_name):
        """Get recent incoming/outgoing transfers for a team from BSD."""
        resolved = self._resolve_team_for_analysis(team_name)
        if not isinstance(resolved, dict) or resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": resolved.get("message", "Could not resolve the team.") if isinstance(resolved, dict) else "Could not resolve the team.",
                "transfers": [],
            }

        team_id = self._safe_int(resolved.get("team_id"))
        team_name_resolved = resolved.get("team_name") or team_name
        if team_id is None:
            return {"status": "error", "team": team_name_resolved, "transfers": [], "message": "No valid BSD team ID."}

        raw = []
        try:
            data = self.football._bsd_request(f"teams/{team_id}/")
            if isinstance(data, dict):
                raw = data.get("transfers") or data.get("transfer_history") or []
                if isinstance(raw, dict):
                    raw = raw.get("results", raw.get("data", []))
        except Exception:
            raw = []

        if not isinstance(raw, list) or not raw:
            try:
                data = self.football._bsd_request(
                    "transfers/",
                    params={"team_id": team_id, "limit": 200, "offset": 0},
                )
                if isinstance(data, dict):
                    raw = data.get("results", data.get("transfers", data.get("data", [])))
                elif isinstance(data, list):
                    raw = data
            except Exception as error:
                return {"status": "error", "team": team_name_resolved, "team_id": team_id, "transfers": [], "message": "Could not retrieve team transfers.", "error": str(error)}

        if not isinstance(raw, list):
            raw = []

        transfers = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            player = item.get("player") if isinstance(item.get("player"), dict) else {}
            from_team = item.get("from_team") or item.get("team_from") or item.get("from")
            to_team = item.get("to_team") or item.get("team_to") or item.get("to")

            def team_name_value(value, fallback_keys):
                if isinstance(value, dict):
                    return value.get("name") or value.get("team_name") or value.get("short_name")
                if isinstance(value, str) and value.strip():
                    return value.strip()
                for key in fallback_keys:
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                return None

            from_name = team_name_value(from_team, ("from_team_name", "team_from_name"))
            to_name = team_name_value(to_team, ("to_team_name", "team_to_name"))
            from_id = self._safe_int(from_team.get("id") or from_team.get("team_id") if isinstance(from_team, dict) else item.get("from_team_id"))
            to_id = self._safe_int(to_team.get("id") or to_team.get("team_id") if isinstance(to_team, dict) else item.get("to_team_id"))

            direction = item.get("direction")
            if not direction:
                if to_id == team_id or self._team_name_matches(team_name_resolved, to_name):
                    direction = "in"
                elif from_id == team_id or self._team_name_matches(team_name_resolved, from_name):
                    direction = "out"

            transfers.append({
                "id": self._safe_int(item.get("id") or item.get("transfer_id")),
                "player_id": self._safe_int(player.get("id") or player.get("player_id") or item.get("player_id")),
                "player_name": player.get("name") or player.get("player_name") or item.get("player_name") or item.get("name"),
                "from_team_id": from_id,
                "from_team": from_name,
                "to_team_id": to_id,
                "to_team": to_name,
                "direction": direction,
                "transfer_type": item.get("transfer_type") or item.get("type") or item.get("move_type"),
                "date": item.get("date") or item.get("transfer_date"),
                "season": item.get("season"),
                "season_id": self._safe_int(item.get("season_id")),
                "fee": item.get("fee"),
                "fee_amount": item.get("fee_amount"),
                "contract_status": item.get("contract_status"),
            })

        return {
            "status": "success",
            "team": {"id": team_id, "name": team_name_resolved, "logo": self.football._get_bsd_team_logo(team_id)},
            "count": len(transfers),
            "transfers": transfers,
        }

    # ============================================================
    # NEWS
    # ============================================================

    def get_team_news(self, team_name):
        """
        Get relevant football news for a specific team.
        """
        try:
            result = self.news.search_news(team_name)
        except Exception as error:
            return {
                "status": "error",
                "team": team_name,
                "error": str(error),
            }

        if isinstance(result, list):
            articles = result

        elif isinstance(result, dict):
            articles = result.get("articles", [])

        else:
            return {
                "status": "error",
                "team": team_name,
                "error": (
                    "News service returned an unexpected "
                    "response format."
                ),
            }

        news = []

        for article in articles:
            if not isinstance(article, dict):
                continue

            source = article.get("source") or {}

            if isinstance(source, dict):
                source_name = source.get("name")
            else:
                source_name = str(source)

            news.append(
                {
                    "title": article.get("title"),
                    "description": article.get("description"),
                    "source": source_name,
                    "published_at": article.get("publishedAt"),
                    "url": article.get("url"),
                }
            )

        return {
            "status": "success",
            "team": team_name,
            "article_count": len(news),
            "articles": news,
        }