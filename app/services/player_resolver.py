class PlayerResolver:

    def __init__(self, football_service):
        self.football = football_service
        self.squad_cache = {}

    def normalize(self, text):
        if not isinstance(text, str):
            return ""

        return (
            text.lower()
            .strip()
            .replace("-", " ")
            .replace(".", "")
        )

    def get_squad(self, team_id):
        if team_id in self.squad_cache:
            return self.squad_cache[team_id]

        data = self.football.get_team_squad(team_id)

        players = data.get("response", [])

        self.squad_cache[team_id] = players

        return players

    def extract_players(self, team_id):
        squad = self.get_squad(team_id)

        players = {}

        for entry in squad:
            player = entry.get("player", {})

            player_id = entry.get("playerId")

            if not player_id:
                player_id = player.get("id")

            if not player_id:
                continue

            if player_id not in players:
                players[player_id] = {
                    "id": player_id,
                    "name": player.get("name") or "",
                    "firstname": player.get("firstname") or "",
                    "lastname": player.get("lastname") or "",
                    "age": player.get("age"),
                    "nationality": player.get("nationality") or "",
                    "photo": player.get("photo") or "",
                    "position": entry.get("position") or "",
                    "number": entry.get("number"),
                    "team_id": entry.get("teamId") or team_id,
                    "squad_entry_id": entry.get("id"),
                    "updated_at": entry.get("updateAt"),
                }

        return list(players.values())

    def build_search_terms(self, player):
        name = player.get("name") or ""
        firstname = player.get("firstname") or ""
        lastname = player.get("lastname") or ""

        name = name.strip()
        firstname = firstname.strip()
        lastname = lastname.strip()

        terms = []

        if name:
            terms.append(name)

        if firstname and lastname:
            terms.append(firstname)
            terms.append(f"{firstname} {lastname}")
            terms.append(
                f"{firstname[0]}. {lastname}"
            )

        elif lastname:
            terms.append(lastname)

        unique_terms = []
        seen = set()

        for term in terms:
            normalized = self.normalize(term)

            if normalized and normalized not in seen:
                unique_terms.append(term)
                seen.add(normalized)

        return unique_terms

    def build_player_identity(self, player):
        name = player.get("name") or ""
        firstname = player.get("firstname") or ""
        lastname = player.get("lastname") or ""

        name = name.strip()
        firstname = firstname.strip()
        lastname = lastname.strip()

        short_name = name

        if firstname and lastname:
            short_name = f"{firstname[0]}. {lastname}"

        return {
            "id": player.get("id"),
            "name": name,
            "short_name": short_name,
            "team_id": player.get("team_id"),
            "position": player.get("position") or "",
            "number": player.get("number"),
            "age": player.get("age"),
            "nationality": player.get("nationality") or "",
            "photo": player.get("photo") or "",
            "squad_entry_id": player.get("squad_entry_id"),
            "updated_at": player.get("updated_at"),
            "search_terms": self.build_search_terms(player),
        }

    def get_players(self, team_id):
        players = self.extract_players(team_id)

        return [
            self.build_player_identity(player)
            for player in players
        ]