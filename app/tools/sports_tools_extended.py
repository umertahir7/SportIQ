from __future__ import annotations


class SportsToolsExtendedMixin:
    """Extended SportsTools methods mixed into SportsTools."""

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

    def get_team_manager(self, team_name):
        """
        Get the current manager/head coach for a team.

        BSD team detail is the primary source because it exposes the
        manager attached to the current team profile.
        """
        resolved = self._resolve_team_for_analysis(team_name)

        if resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": resolved.get("message", "Could not resolve the team."),
                "error": resolved.get("error"),
            }

        selected_team_name = resolved.get("team_name")
        bsd_team_id = self._safe_int(resolved.get("team_id"))

        if bsd_team_id is None:
            return {
                "status": "error",
                "team": selected_team_name,
                "message": "BSD team resolution returned no valid team ID.",
            }

        team_detail = None

        try:
            data = self.football._bsd_request(f"teams/{bsd_team_id}/")
            if isinstance(data, dict):
                team_detail = data.get("team") if isinstance(data.get("team"), dict) else data
        except Exception:
            team_detail = None

        manager = team_detail.get("manager") if isinstance(team_detail, dict) else None

        # Keep a fallback for BSD responses that do not embed manager data
        # in the team profile. Do not blindly take the first historical coach.
        if not isinstance(manager, dict):
            try:
                data = self.football._bsd_request(
                    "managers/",
                    params={"team_id": bsd_team_id, "limit": 20, "offset": 0},
                )
            except Exception:
                data = None

            managers = []
            if isinstance(data, dict):
                managers = data.get("results", data.get("data", []))
            elif isinstance(data, list):
                managers = data

            if isinstance(managers, list):
                active_candidates = []
                for candidate in managers:
                    if not isinstance(candidate, dict):
                        continue
                    candidate_team_id = self._safe_int(
                        candidate.get("current_team_id")
                        or candidate.get("team_id")
                        or candidate.get("current_team", {}).get("id")
                        if isinstance(candidate.get("current_team"), dict)
                        else candidate.get("current_team_id")
                        or candidate.get("team_id")
                    )
                    is_current = candidate.get("is_current") is True or candidate.get("current") is True or candidate.get("active") is True
                    if candidate_team_id == bsd_team_id or is_current:
                        active_candidates.append(candidate)
                if active_candidates:
                    manager = active_candidates[0]

        if not isinstance(manager, dict):
            return {
                "status": "success",
                "team": selected_team_name,
                "team_id": bsd_team_id,
                "manager": None,
                "message": "BSD currently has no current manager listed for this team.",
            }

        manager_id = self._safe_int(manager.get("id") or manager.get("manager_id"))
        manager_name = manager.get("name") or manager.get("manager_name") or manager.get("short_name")

        # BSD's image proxy provides manager portraits by manager ID.
        manager_image = (
            f"{self.football.BSD_IMAGE_PROXY}/manager/{manager_id}/?bg=transparent"
            if manager_id is not None and hasattr(self.football, "BSD_IMAGE_PROXY")
            else (
                f"https://sports.bzzoiro.com/img/manager/{manager_id}/?bg=transparent"
                if manager_id is not None
                else None
            )
        )

        return {
            "status": "success",
            "team": selected_team_name,
            "team_id": bsd_team_id,
            "manager": {
                "id": manager_id,
                "name": manager_name,
                "image": manager_image,
                "photo": manager_image,
            },
        }

    def get_team_transfers(self, team_name):
        """Get incoming and outgoing transfers with readable club names."""
        resolved = self._resolve_team_for_analysis(team_name)

        if resolved.get("status") != "success":
            return {
                "status": "error",
                "team": team_name,
                "message": resolved.get("message", "Could not resolve the team."),
                "error": resolved.get("error"),
                "transfers": [],
            }

        selected_team_name = resolved.get("team_name")
        bsd_team_id = self._safe_int(resolved.get("team_id"))
        if bsd_team_id is None:
            return {"status": "error", "team": selected_team_name, "transfers": [], "error": "No valid BSD team ID."}

        # Team detail is the same BSD source used by the public team page and
        # normally contains transfer records with human-readable club names.
        raw_transfers = []
        try:
            data = self.football._bsd_request(f"teams/{bsd_team_id}/")
            if isinstance(data, dict):
                raw_transfers = data.get("transfers") or data.get("transfer_history") or []
                if isinstance(raw_transfers, dict):
                    raw_transfers = raw_transfers.get("results", raw_transfers.get("data", []))
        except Exception:
            raw_transfers = []

        # Fallback to the dedicated endpoint when team detail does not expose
        # the transfer collection.
        if not isinstance(raw_transfers, list) or not raw_transfers:
            try:
                data = self.football._bsd_request(
                    "transfers/",
                    params={"team_id": bsd_team_id, "limit": 200, "offset": 0},
                )
            except Exception as error:
                return {
                    "status": "error",
                    "team": selected_team_name,
                    "team_id": bsd_team_id,
                    "message": "Could not retrieve team transfers.",
                    "error": str(error),
                    "transfers": [],
                }
            if isinstance(data, dict):
                raw_transfers = data.get("results", data.get("transfers", data.get("data", [])))
            elif isinstance(data, list):
                raw_transfers = data
            else:
                raw_transfers = []

        if not isinstance(raw_transfers, list):
            raw_transfers = []

        team_name_cache = {bsd_team_id: selected_team_name}

        def resolve_club_name(team_value, team_id):
            if isinstance(team_value, dict):
                name = team_value.get("name") or team_value.get("team_name") or team_value.get("short_name")
                if name:
                    return name
                team_id = self._safe_int(team_value.get("id") or team_value.get("team_id")) or team_id
            elif isinstance(team_value, str) and team_value.strip():
                return team_value.strip()

            team_id = self._safe_int(team_id)
            if team_id is None:
                return None
            if team_id in team_name_cache:
                return team_name_cache[team_id]

            try:
                detail = self.football._bsd_request(f"teams/{team_id}/")
                if isinstance(detail, dict):
                    detail = detail.get("team") if isinstance(detail.get("team"), dict) else detail
                    name = detail.get("name") or detail.get("team_name") or detail.get("short_name")
                    if name:
                        team_name_cache[team_id] = name
                        return name
            except Exception:
                pass
            return None

        transfers = []
        for item in raw_transfers:
            if not isinstance(item, dict):
                continue

            player = item.get("player") if isinstance(item.get("player"), dict) else {}
            player_id = self._safe_int(player.get("id") or player.get("player_id") or item.get("player_id"))
            player_name = player.get("name") or player.get("player_name") or item.get("player_name") or item.get("name")

            from_value = item.get("from_team") or item.get("team_from") or item.get("from")
            to_value = item.get("to_team") or item.get("team_to") or item.get("to")
            from_id = self._safe_int(
                from_value.get("id") or from_value.get("team_id") if isinstance(from_value, dict) else item.get("from_team_id") or item.get("from_team") if isinstance(item.get("from_team"), int) else None
            )
            to_id = self._safe_int(
                to_value.get("id") or to_value.get("team_id") if isinstance(to_value, dict) else item.get("to_team_id") or item.get("to_team") if isinstance(item.get("to_team"), int) else None
            )

            from_name = resolve_club_name(from_value, from_id) or item.get("from_team_name") or item.get("team_from_name")
            to_name = resolve_club_name(to_value, to_id) or item.get("to_team_name") or item.get("team_to_name")

            direction = item.get("direction")
            if not direction:
                if to_id == bsd_team_id or self._team_name_matches(selected_team_name, to_name):
                    direction = "in"
                elif from_id == bsd_team_id or self._team_name_matches(selected_team_name, from_name):
                    direction = "out"

            transfers.append({
                "id": self._safe_int(item.get("id") or item.get("transfer_id")),
                "player_id": player_id,
                "player_name": player_name,
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
            "team": {"id": bsd_team_id, "name": selected_team_name, "logo": self.football._get_bsd_team_logo(bsd_team_id)},
            "count": len(transfers),
            "transfers": transfers,
        }

    def get_top_scorers(self, team_name, league_id=None):
        """Get current top scorers for the selected team's league."""
        resolved = self._resolve_team_for_analysis(team_name)
        if resolved.get("status") != "success":
            return {"status": "error", "team": team_name, "error": resolved.get("error"), "scorers": []}

        selected_team_name = resolved.get("team_name")
        bsd_team_id = self._safe_int(resolved.get("team_id"))

        if league_id is None and bsd_team_id is not None and hasattr(self, "_resolve_team_league_from_standings"):
            league_resolution = self._resolve_team_league_from_standings(bsd_team_id)
            if league_resolution.get("status") == "success":
                league_id = league_resolution.get("league_id")

        league_id = self._safe_int(league_id)
        if league_id is None:
            return {"status": "error", "team": selected_team_name, "team_id": bsd_team_id, "error": f"Could not determine the league for {selected_team_name}.", "scorers": []}

        season_resolution = self._current_bsd_season_cache.get(league_id) if hasattr(self, "_current_bsd_season_cache") else None
        if season_resolution is None:
            season_resolution = self._get_current_bsd_season(league_id)
            if isinstance(season_resolution, dict) and season_resolution.get("status") == "success" and hasattr(self, "_current_bsd_season_cache"):
                self._current_bsd_season_cache[league_id] = season_resolution

        season_id = season_resolution.get("season_id") if isinstance(season_resolution, dict) else self._safe_int(season_resolution)
        season_id = self._safe_int(season_id)

        params = {"limit": 20, "offset": 0}
        if season_id is not None:
            params["season_id"] = season_id

        try:
            data = self.football._bsd_request(f"leagues/{league_id}/top/scorers/", params=params)
        except Exception as error:
            return {"status": "error", "team": selected_team_name, "team_id": bsd_team_id, "league_id": league_id, "season_id": season_id, "message": "Could not retrieve league top scorers.", "error": str(error), "scorers": []}

        if isinstance(data, dict):
            raw_scorers = data.get("results", data.get("scorers", data.get("data", [])))
        elif isinstance(data, list):
            raw_scorers = data
        else:
            raw_scorers = []

        if not isinstance(raw_scorers, list):
            raw_scorers = []

        scorers = []
        for item in raw_scorers:
            if not isinstance(item, dict):
                continue
            player = item.get("player") if isinstance(item.get("player"), dict) else item
            player_id = self._safe_int(player.get("id") or player.get("player_id"))
            player_name = player.get("name") or player.get("player_name")
            if not player_name:
                continue
            team = item.get("team") if isinstance(item.get("team"), dict) else {}
            team_id = self._safe_int(team.get("id") or team.get("team_id") or item.get("team_id"))
            team_name_value = team.get("name") or team.get("team_name") or item.get("team_name")
            goals = item.get("goals") if item.get("goals") is not None else item.get("total")
            scorers.append({"player_id": player_id, "player_name": player_name, "team_id": team_id, "team_name": team_name_value, "goals": goals, "assists": item.get("assists")})

        return {"status": "success", "team": selected_team_name, "team_id": bsd_team_id, "league_id": league_id, "league_name": self.MAJOR_LEAGUE_IDS.get(league_id, f"League {league_id}"), "season_id": season_id, "count": len(scorers), "scorers": scorers}

    def get_match_h2h(self, fixture_id):
        """
        Get head-to-head history for a specific BSD match/event.

        BSD exposes H2H as an event sub-resource:
            /api/v2/events/{id}/h2h/
        """
        fixture_id = self._safe_int(
            fixture_id
        )

        if fixture_id is None:
            return {
                "status": "error",
                "error": "Invalid fixture/event ID.",
            }

        try:
            data = self.football._bsd_request(
                f"events/{fixture_id}/h2h/"
            )
        except Exception as error:
            return {
                "status": "error",
                "fixture_id": fixture_id,
                "message": (
                    "Could not retrieve head-to-head data."
                ),
                "error": str(error),
            }

        if not isinstance(data, dict):
            return {
                "status": "error",
                "fixture_id": fixture_id,
                "message": (
                    "BSD returned an unexpected H2H response."
                ),
                "h2h": None,
            }

        head_to_head = data.get(
            "head_to_head"
        )

        # Some BSD responses may expose the H2H fields directly.
        if head_to_head is None:
            head_to_head = data

        home_form = data.get(
            "home_form"
        )

        away_form = data.get(
            "away_form"
        )

        return {
            "status": "success",
            "fixture_id": fixture_id,
            "head_to_head": head_to_head,
            "home_form": home_form,
            "away_form": away_form,
            "raw": data,
        }

