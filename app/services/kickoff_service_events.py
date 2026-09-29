import os

from typing import Any, Dict, List, Optional

import requests
from app.services.timezone_service import TimezoneService


class KickoffEventsMixin:
    """Event, fixture, results, standings, squad, broadcast and social methods."""

    def _get_bsd_events(
        self,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        stage: Optional[str] = None,
        round_name: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Fetch events from BSD /events/.

        This endpoint intentionally remains the lightweight list
        endpoint. Rich match details are retrieved separately using
        get_bsd_match_details().
        """

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if league_id is not None:
            params["league_id"] = league_id

        if season_id is not None:
            params["season_id"] = season_id

        if team_id is not None:
            params["team_id"] = team_id

        if team_name:
            params["team_name"] = team_name

        if status:
            params["status"] = status

        if date_from:
            params["date_from"] = date_from

        if date_to:
            params["date_to"] = date_to

        if stage:
            params["stage"] = stage

        if round_name:
            params["round"] = round_name

        data = self._bsd_request(
            "events/",
            params=params,
        )

        return self._extract_event_collection(data)

    def _get_bsd_live_events(
        self,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        team_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch live events from BSD's dedicated live endpoint.

        BSD:
            GET /events/live/

        Optional filters:
            - league_id
            - season_id
            - team_id

        Unlike the generic /events/ endpoint, this uses BSD's dedicated
        live-event feed.

        The live endpoint returns its event collection under the
        "events" key, which is already supported by
        _extract_event_collection().
        """

        params: Dict[str, Any] = {}

        if league_id is not None:
            params["league_id"] = league_id

        if season_id is not None:
            params["season_id"] = season_id

        if team_id is not None:
            params["team_id"] = team_id

        data = self._bsd_request(
            "events/live/",
            params=params,
        )

        return self._extract_event_collection(data)

    # ============================================================
    # MATCH DETAIL ENDPOINTS
    # ============================================================

    def _get_bsd_event_detail(
        self,
        event_id: Any,
    ) -> Dict[str, Any]:
        """
        Fetch complete static information for a match.

        BSD:
            GET /events/{id}/
        """

        data = self._bsd_request(
            f"events/{event_id}/"
        )

        return self._extract_single_event(data)

    def _get_bsd_event_incidents(
        self,
        event_id: Any,
    ) -> Any:
        """
        Fetch chronological match incidents.

        BSD:
            GET /events/{id}/incidents/

        Includes things such as:
            - goals
            - cards
            - substitutions
            - VAR
        """

        return self._bsd_request(
            f"events/{event_id}/incidents/"
        )

    def _get_bsd_event_stats(
        self,
        event_id: Any,
    ) -> Any:
        """
        Fetch match statistics.

        BSD:
            GET /events/{id}/stats/

        May include:
            - possession
            - shots
            - xG
            - shot map
            - momentum
            - xG timeline
        """

        return self._bsd_request(
            f"events/{event_id}/stats/"
        )

    def _get_bsd_event_lineups(
        self,
        event_id: Any,
    ) -> Any:
        """
        Fetch match lineups.

        BSD:
            GET /events/{id}/lineups/

        Added here for future richer match analysis, but not required
        by get_bsd_match_details() yet.
        """

        return self._bsd_request(
            f"events/{event_id}/lineups/"
        )

    def _normalize_incidents(
        self,
        data: Any,
    ) -> Any:
        """
        Keep BSD incident information intact while making list-style
        responses easier for the AI layer to consume.
        """

        incidents = self._extract_event_collection(data)

        if incidents:
            return incidents

        # If BSD returns a dictionary with an unexpected structure,
        # preserve it rather than throwing away information.

        return data

    def _normalize_stats(
        self,
        data: Any,
    ) -> Any:
        """
        Keep BSD statistics intact.

        The stats schema can contain multiple structures such as
        team statistics, shotmaps, momentum and xG series, so we
        do not aggressively rename fields here.
        """

        return data

    def get_bsd_match_details(
        self,
        event_id: Any,
        requested_team_id: Optional[int] = None,
        include_lineups: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch a complete match package.

        Requests:
            1. /events/{id}/
            2. /events/{id}/incidents/
            3. /events/{id}/stats/

        Optionally:
            4. /events/{id}/lineups/

        The result is normalized into the same structure used by
        get_bsd_results(), while preserving raw BSD responses.

        This is the main method the AI agent should use when it needs
        to answer questions such as:

            "What happened in Chelsea's last game?"

            "How did Real Madrid lose to Atletico?"

            "Who scored?"

            "What happened in the second half?"

            "What were the stats?"
        """

        if event_id is None:
            raise ValueError("event_id is required.")

        # --------------------------------------------------------
        # 1. MATCH DETAIL
        # --------------------------------------------------------

        detail_raw = self._get_bsd_event_detail(event_id)

        if not detail_raw:
            return {}

        normalized = self._normalize_bsd_event(
            detail_raw,
            requested_team_id=requested_team_id,
        )

        # --------------------------------------------------------
        # 2. INCIDENTS
        # --------------------------------------------------------

        try:
            incidents_raw = self._get_bsd_event_incidents(
                event_id
            )

            normalized["incidents"] = self._normalize_incidents(
                incidents_raw
            )

            normalized["incidents_raw"] = incidents_raw

        except requests.RequestException as exc:
            normalized["incidents"] = None
            normalized["incidents_raw"] = None
            normalized["incidents_error"] = str(exc)

        # --------------------------------------------------------
        # 3. STATISTICS
        # --------------------------------------------------------

        try:
            stats_raw = self._get_bsd_event_stats(
                event_id
            )

            normalized["statistics"] = self._normalize_stats(
                stats_raw
            )

            normalized["stats_raw"] = stats_raw

        except requests.RequestException as exc:
            normalized["statistics"] = None
            normalized["stats_raw"] = None
            normalized["stats_error"] = str(exc)

        # --------------------------------------------------------
        # 4. OPTIONAL LINEUPS
        # --------------------------------------------------------

        if include_lineups:

            try:
                lineups_raw = self._get_bsd_event_lineups(
                    event_id
                )

                normalized["lineups"] = lineups_raw
                normalized["lineups_raw"] = lineups_raw

            except requests.RequestException as exc:
                normalized["lineups"] = None
                normalized["lineups_raw"] = None
                normalized["lineups_error"] = str(exc)

        # --------------------------------------------------------
        # Preserve complete raw detail response.
        # --------------------------------------------------------

        normalized["detail_raw"] = detail_raw
        normalized["event_id"] = event_id

        return normalized

    # ============================================================
    # FIXTURES
    # ============================================================

    def get_bsd_fixtures(
        self,
        team_name: Optional[str] = None,
        league_name: Optional[str] = None,
        limit: int = 10,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        team_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming fixtures from BSD.

        When a team ID is known, BSD's team-specific fixtures endpoint is
        used because it returns the team's actual upcoming fixtures even
        when the generic /events/ endpoint does not expose them reliably.
        """

        # Be tolerant if a higher-level caller accidentally passes a numeric
        # team ID through team_name. This also prevents string-only helpers
        # from receiving an int.
        if team_id is None and isinstance(team_name, int):
            team_id = team_name
            team_name = None

        if league_id is None and league_name:
            league_id = self.resolve_bsd_league_id(str(league_name))

        if season_id is None and league_id is not None:
            season_id = self.resolve_current_bsd_season_id(league_id)

        if team_id is None and team_name:
            team = self.resolve_bsd_team(
                team_name=str(team_name),
                league_id=league_id,
                season_id=season_id,
            )

            if team:
                team_id = self._first_present(team, "id", "team_id")

        events: List[Any] = []

        # Team-specific BSD endpoint - this is the reliable path for team
        # fixture queries such as Portugal's Nations League fixtures.
        if team_id is not None:
            params: Dict[str, Any] = {}

            if season_id is not None:
                params["season_id"] = season_id

            try:
                data = self._bsd_request(
                    f"teams/{team_id}/fixtures/",
                    params=params,
                )

                events = self._extract_event_collection(data)

            except requests.RequestException:
                # Preserve compatibility with the generic endpoint if the
                # team-specific endpoint is temporarily unavailable.
                events = []

        if not events:
            events = self._get_bsd_events(
                league_id=league_id,
                season_id=season_id,
                team_id=team_id,
                date_from=date_from,
                date_to=date_to,
                limit=200,
                offset=offset,
            )

        normalized: List[Dict[str, Any]] = []

        for event in events:

            if not isinstance(event, dict):
                continue

            # Some BSD team-specific responses can contain richer event data
            # but do not need another team-name lookup.
            item = self._normalize_bsd_event(
                event,
                requested_team_id=team_id,
            )

            if not item or not item.get("date"):
                continue

            # Strictly enforce the requested team ID. This protects against
            # unrelated events returned by broad API searches.
            if team_id is not None:

                home_id = item.get("home_team", {}).get("id")
                away_id = item.get("away_team", {}).get("id")

                try:
                    if int(team_id) not in {
                        int(home_id),
                        int(away_id),
                    }:
                        continue

                except (TypeError, ValueError):
                    continue

            # Apply optional filters locally because the team-specific
            # endpoint does not accept all generic event filters.
            if league_id is not None:

                try:
                    if int(item.get("league_id")) != int(league_id):
                        continue

                except (TypeError, ValueError):
                    continue

            event_date = str(item.get("date") or "")[:10]

            if date_from and event_date < str(date_from)[:10]:
                continue

            if date_to and event_date > str(date_to)[:10]:
                continue

            normalized.append(item)

        normalized.sort(
            key=lambda item: str(item.get("date") or "")
        )

        return normalized[offset:offset + limit]

    def get_bsd_results(
        self,
        team_name: Optional[str] = None,
        league_name: Optional[str] = None,
        limit: int = 10,
        include_details: bool = False,
        include_lineups: bool = False,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        team_id: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get completed results from BSD.

        Explicit BSD IDs are supported while preserving the original
        name-based interface.
        """

        if league_id is None and league_name:
            league_id = self.resolve_bsd_league_id(league_name)

        if season_id is None and league_id is not None:
            season_id = self.resolve_current_bsd_season_id(league_id)

        if team_id is None and team_name:
            team = self.resolve_bsd_team(
                team_name=team_name,
                league_id=league_id,
                season_id=season_id,
            )

            if team:
                team_id = self._first_present(
                    team,
                    "id",
                    "team_id",
                )

        events = self._get_bsd_events(
            league_id=league_id,
            season_id=season_id,
            team_id=team_id,
            status="finished",
            limit=200,
            offset=offset,
        )

        normalized = []

        for event in events:

            item = self._normalize_bsd_event(
                event,
                requested_team_id=team_id,
            )

            if item:
                normalized.append(item)

        normalized.sort(
            key=lambda item: str(item.get("date") or ""),
            reverse=True,
        )

        normalized = normalized[:limit]

        if include_details:

            enriched = []

            for item in normalized:

                event_id = item.get("id")

                if not event_id:
                    enriched.append(item)
                    continue

                try:

                    detailed = self.get_bsd_match_details(
                        event_id=event_id,
                        requested_team_id=team_id,
                        include_lineups=include_lineups,
                    )

                    if detailed:
                        enriched.append(detailed)
                    else:
                        enriched.append(item)

                except requests.RequestException as exc:
                    item["details_error"] = str(exc)
                    enriched.append(item)

            normalized = enriched

        return normalized

    def get_bsd_standings(
        self,
        league_name: Optional[str] = None,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get current league standings.

        Either league_id or league_name may be supplied. Explicit IDs
        take precedence so SportsTools can use its resolved BSD IDs.

        BSD endpoint:
            GET /leagues/{league_id}/standings/?season_id={season_id}
        """

        if league_id is None and league_name:
            league_id = self.resolve_bsd_league_id(league_name)

        if league_id is None:
            return []

        if season_id is None:
            season_id = self.resolve_current_bsd_season_id(league_id)

        if season_id is None:
            return []

        # BSD standings are exposed through the league-specific endpoint.
        #
        # Correct route:
        #
        #     /leagues/3/standings/?season_id=1307
        #
        data = self._bsd_request(
            f"leagues/{league_id}/standings/",
            params={
                "season_id": season_id,
            },
        )

        # BSD standings responses are structured differently from the
        # generic event collection responses:
        #
        # {
        #     "league_id": 3,
        #     "season": {...},
        #     "grouped": False,
        #     "zones": [...],
        #     "standings": [...]
        # }
        #
        # Therefore do NOT pass this response through
        # _extract_event_collection(). The actual table rows are stored
        # directly under the "standings" key.
        if isinstance(data, dict):

            standings = data.get("standings")

            if isinstance(standings, list):
                return standings

        return []

    def get_bsd_squad(
        self,
        team_name: Optional[str] = None,
        league_name: Optional[str] = None,
        team_id: Optional[int] = None,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get a team's squad.

        Supports both a team name and an explicit BSD team ID. Numeric
        values passed through team_name are treated as IDs so the resolver
        never calls string-only operations such as .lower() on an int.
        """

        if team_id is None and isinstance(team_name, int):
            team_id = team_name
            team_name = None

        if league_id is None and league_name:
            league_id = self.resolve_bsd_league_id(str(league_name))

        if season_id is None and league_id is not None:
            season_id = self.resolve_current_bsd_season_id(league_id)

        if team_id is None and team_name:
            team = self.resolve_bsd_team(
                team_name=str(team_name),
                league_id=league_id,
                season_id=season_id,
            )

            if team:
                team_id = self._first_present(
                    team,
                    "id",
                    "team_id",
                )

        if team_id is None:
            return {
                "status": "error",
                "message": (
                    f"Could not resolve team: {team_name}"
                    if team_name
                    else "Team ID is required."
                ),
            }

        params: Dict[str, Any] = {}

        if season_id is not None:
            params["season_id"] = season_id

        data = self._bsd_request(
            f"teams/{team_id}/squad/",
            params=params,
        )

        enriched = self._enrich_bsd_squad_images(data)

        if isinstance(enriched, dict):

            enriched = dict(enriched)
            enriched["status"] = "success"
            enriched["team_id"] = team_id

            team_logo = self.get_bsd_team_logo(team_id)

            enriched["team_logo"] = team_logo
            enriched["team_logo_url"] = team_logo

            # Keep a human-readable name even when the caller supplied only
            # an ID.
            if team_name:
                enriched["team_name"] = str(team_name)

            else:

                try:

                    team = self._bsd_request(
                        f"teams/{team_id}/"
                    )

                    team = self._extract_single_event(team)

                    if team:
                        enriched["team_name"] = self._first_present(
                            team,
                            "name",
                            "team_name",
                            "short_name",
                        )

                except requests.RequestException:
                    pass

        return enriched

    def search_bsd_teams(
        self,
        team_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search BSD teams by name.
        """

        search_names = self._team_search_names(team_name)

        data = self._bsd_request(
            "teams/",
            params={
                "name": (
                    search_names[0]
                    if search_names
                    else team_name
                ),
                "is_women": False,
                "limit": limit,
            },
        )

        return self._extract_event_collection(data)

    def enrich_team(
        self,
        team: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add common normalized team fields.
        """

        if not isinstance(team, dict):
            return {}

        team_id = self._first_present(
            team,
            "id",
            "team_id",
        )

        name = self._first_present(
            team,
            "name",
            "team_name",
            "short_name",
        )

        result = dict(team)

        result["id"] = team_id
        result["name"] = name

        result["logo"] = (
            self._get_bsd_team_logo(team_id)
            if team_id
            else None
        )

        return result

    # ============================================================
    # BROADCASTS
    # ============================================================

    # ============================================================
    # BROADCAST MARKET / COUNTRY
    # ============================================================

    def _get_broadcast_country_code(self) -> Optional[str]:
        """Derive the broadcast market from the user's local timezone."""

        try:
            timezone_name = TimezoneService().get_timezone_name()

        except Exception:
            return None

        timezone_to_country = {
            "Asia/Karachi": "PK",
            "Asia/Kolkata": "IN",
            "Asia/Calcutta": "IN",
            "Asia/Dubai": "AE",
            "Asia/Riyadh": "SA",
            "Asia/Qatar": "QA",
            "Asia/Muscat": "OM",
            "Asia/Singapore": "SG",
            "Asia/Tokyo": "JP",
            "Asia/Seoul": "KR",
            "Asia/Shanghai": "CN",
            "Asia/Hong_Kong": "HK",
            "Asia/Bangkok": "TH",
            "Asia/Jakarta": "ID",
            "Asia/Manila": "PH",
            "Europe/London": "GB",
            "Europe/Dublin": "IE",
            "Europe/Lisbon": "PT",
            "Europe/Madrid": "ES",
            "Europe/Paris": "FR",
            "Europe/Berlin": "DE",
            "Europe/Rome": "IT",
            "Europe/Amsterdam": "NL",
            "Europe/Brussels": "BE",
            "Europe/Zurich": "CH",
            "Europe/Vienna": "AT",
            "Europe/Stockholm": "SE",
            "Europe/Oslo": "NO",
            "Europe/Copenhagen": "DK",
            "Europe/Helsinki": "FI",
            "Europe/Athens": "GR",
            "Europe/Warsaw": "PL",
            "Europe/Istanbul": "TR",
            "America/New_York": "US",
            "America/Chicago": "US",
            "America/Denver": "US",
            "America/Los_Angeles": "US",
            "America/Toronto": "CA",
            "America/Vancouver": "CA",
            "America/Mexico_City": "MX",
            "America/Sao_Paulo": "BR",
            "America/Argentina/Buenos_Aires": "AR",
            "Australia/Sydney": "AU",
            "Australia/Melbourne": "AU",
            "Australia/Brisbane": "AU",
            "Pacific/Auckland": "NZ",
        }

        return timezone_to_country.get(timezone_name)

    def get_bsd_broadcasts(
        self,
        event_id: Any,
        country_code: Optional[str] = None,
        channel_id: Optional[int] = None,
        league_id: Optional[int] = None,
        team_id: Optional[int] = None,
        season_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get TV/broadcast listings for a BSD event.

        If no country code is supplied, derive the broadcast market from
        the user's local timezone instead of hardcoding a country.
        """

        if event_id is None:
            raise ValueError("event_id is required.")

        if not country_code:
            country_code = self._get_broadcast_country_code()

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        if country_code:
            params["country_code"] = country_code.upper()

        if channel_id is not None:
            params["channel_id"] = channel_id

        if league_id is not None:
            params["league_id"] = league_id

        if team_id is not None:
            params["team_id"] = team_id

        if season_id is not None:
            params["season_id"] = season_id

        if date_from:
            params["date_from"] = date_from

        if date_to:
            params["date_to"] = date_to

        data = self._bsd_request(
            f"events/{event_id}/broadcasts/",
            params=params,
        )

        items = self._extract_event_collection(data)

        normalized: List[Dict[str, Any]] = []

        for item in items:

            if not isinstance(item, dict):
                continue

            result = dict(item)

            result["event_id"] = result.get(
                "event_id",
                event_id,
            )

            result["channel_name"] = self._first_present(
                result,
                "channel_name",
                "name",
                "channel",
            )

            result["channel_id"] = self._first_present(
                result,
                "channel_id",
                "tv_channel_id",
            )

            result["channel_link"] = self._first_present(
                result,
                "channel_link",
                "url",
                "link",
                default="",
            )

            result["country_code"] = self._first_present(
                result,
                "country_code",
                default=(
                    country_code.upper()
                    if country_code
                    else None
                ),
            )

            normalized.append(result)

        normalized.sort(
            key=lambda x: str(
                x.get("scheduled_start_time")
                or x.get("event_date")
                or ""
            )
        )

        return normalized

    # ============================================================
    # SOCIAL FEED
    # ============================================================

    def get_bsd_social(
        self,
        team_id: Optional[int] = None,
        event_id: Optional[int] = None,
        player_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        social_type: Optional[str] = None,
        account_verified: Optional[bool] = None,
        published_after: Optional[str] = None,
        published_before: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Return BSD social posts/videos with duplicates removed.

        At least one entity filter is required. The BSD response is
        normalized into a compact, stable structure for the agent/UI.
        """

        filters = {
            "team_id": team_id,
            "event_id": event_id,
            "player_id": player_id,
            "manager_id": manager_id,
            "league_id": league_id,
            "season_id": season_id,
        }

        if not any(
            value is not None
            for value in filters.values()
        ):
            raise ValueError(
                "At least one of team_id, event_id, player_id, manager_id, "
                "league_id, or season_id is required."
            )

        params: Dict[str, Any] = {
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
        }

        for key, value in filters.items():

            if value is not None:
                params[key] = value

        if social_type:
            params["type"] = social_type.lower().strip()

        if account_verified is not None:
            params["account_verified"] = account_verified

        if published_after:
            params["published_after"] = published_after

        if published_before:
            params["published_before"] = published_before

        data = self._bsd_request(
            "social/",
            params=params,
        )

        results = (
            data.get("results", [])
            if isinstance(data, dict)
            else []
        )

        if not isinstance(results, list):
            return []

        normalized: List[Dict[str, Any]] = []
        seen = set()

        for item in results:

            if not isinstance(item, dict):
                continue

            url = item.get("url")
            item_id = item.get("id")

            dedupe_key = url or item_id

            if (
                dedupe_key is not None
                and dedupe_key in seen
            ):
                continue

            if dedupe_key is not None:
                seen.add(dedupe_key)

            account = item.get("account")

            if not isinstance(account, dict):
                account = {}

            linked = item.get("linked")

            if not isinstance(linked, dict):
                linked = {}

            normalized.append(
                {
                    "id": item_id,
                    "type": item.get("type"),
                    "url": url,
                    "text": item.get("text"),
                    "title": item.get("title"),
                    "thumbnail": item.get("thumbnail"),
                    "media": item.get("media") or [],
                    "published_at": item.get("published_at"),
                    "account": {
                        "handle": account.get("handle"),
                        "name": account.get("name"),
                        "verified": account.get("verified"),
                    },
                    "linked": {
                        "teams": linked.get("teams") or [],
                        "events": linked.get("events") or [],
                        "players": linked.get("players") or [],
                        "managers": linked.get("managers") or [],
                    },
                }
            )

        return normalized

    def get_social(
        self,
        team_id: Optional[int] = None,
        event_id: Optional[int] = None,
        player_id: Optional[int] = None,
        manager_id: Optional[int] = None,
        league_id: Optional[int] = None,
        season_id: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Compatibility wrapper for BSD social lookups."""

        return self.get_bsd_social(
            team_id=team_id,
            event_id=event_id,
            player_id=player_id,
            manager_id=manager_id,
            league_id=league_id,
            season_id=season_id,
            **kwargs,
        )

    def get_broadcasts(
        self,
        event_id: Any,
        country_code: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Compatibility wrapper for broadcast lookups."""

        return self.get_bsd_broadcasts(
            event_id,
            country_code,
            **kwargs,
        )

    # ============================================================
    # COMPATIBILITY WRAPPERS
    # ============================================================

    def get_team_fixtures(
        self,
        team_name: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Compatibility wrapper used by SportsTools.
        """

        return self.get_bsd_fixtures(
            team_name=team_name,
            limit=limit,
        )

    def get_team_results(
        self,
        team_name: str,
        limit: int = 10,
        include_details: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Compatibility wrapper used by SportsTools.

        Existing callers remain compatible because include_details
        defaults to False.
        """

        return self.get_bsd_results(
            team_name=team_name,
            limit=limit,
            include_details=include_details,
        )

    def get_team_standings(
        self,
        league_name: Optional[str] = None,
        league_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compatibility wrapper.
        """

        return self.get_bsd_standings(
            league_name=league_name,
            league_id=league_id,
        )

    def get_team_squad(
        self,
        team_name: str,
        league_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compatibility wrapper.
        """

        return self.get_bsd_squad(
            team_name=team_name,
            league_name=league_name,
        )