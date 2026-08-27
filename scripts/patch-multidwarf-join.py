#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
path = root / "src/session_policy.cpp"
text = path.read_text(encoding="utf-8-sig")


def replace_once(old, new, label):
    global text
    if old not in text:
        raise RuntimeError(f"{label}: expected source fragment not found")
    text = text.replace(old, new, 1)


replace_once(
    "#include <chrono>\n#include <fstream>\n",
    "#include <chrono>\n#include <cctype>\n#include <fstream>\n",
    "cctype include",
)

prune = '''void prune_presence_locked(long long now) {
    for (auto it = g_presence.begin(); it != g_presence.end();) {
        if (now - it->second.last_ms > kPresenceStaleMs) it = g_presence.erase(it);
        else ++it;
    }
}
'''
helpers = prune + r'''
std::string normalized_player_name(const std::string& value) {
    const std::string cleaned = trim(value);
    if (cleaned.size() < 3 || cleaned.size() > 24) return {};
    std::string normalized;
    normalized.reserve(cleaned.size());
    for (unsigned char ch : cleaned) {
        if (!(std::isalnum(ch) || ch == '_' || ch == '-')) return {};
        normalized.push_back(static_cast<char>(std::tolower(ch)));
    }
    return normalized;
}

bool player_name_taken_locked(const std::string& normalized,
                              const std::string& except_player = {}) {
    for (const auto& entry : g_presence) {
        if (!except_player.empty() && entry.first == except_player) continue;
        if (normalized_player_name(entry.second.name) == normalized) return true;
    }
    return false;
}

bool reserve_player_name(const std::string& player, const std::string& requested,
                         std::string& accepted, std::string& error) {
    accepted = trim(requested);
    const std::string normalized = normalized_player_name(accepted);
    if (normalized.empty()) {
        error = "name must be 3-24 characters using A-Z, a-z, 0-9, _ or -";
        return false;
    }

    const long long now = now_ms();
    std::lock_guard<std::mutex> lock(g_mutex);
    prune_presence_locked(now);
    if (player_name_taken_locked(normalized, player)) {
        error = "player name already in use";
        return false;
    }

    SessionPresence& entry = g_presence[player.substr(0, 64)];
    entry.name = accepted;
    entry.last_ms = now;
    return true;
}

bool player_has_join_reservation(const std::string& player) {
    const long long now = now_ms();
    std::lock_guard<std::mutex> lock(g_mutex);
    prune_presence_locked(now);
    const auto found = g_presence.find(player);
    return found != g_presence.end() && !normalized_player_name(found->second.name).empty();
}

std::string lobby_json() {
    const long long now = now_ms();
    std::lock_guard<std::mutex> lock(g_mutex);
    prune_presence_locked(now);
    std::ostringstream out;
    out << "{\"ok\":true,\"count\":" << g_presence.size() << ",\"players\":[";
    bool first = true;
    for (const auto& entry : g_presence) {
        if (!first) out << ",";
        first = false;
        out << "{\"name\":" << json_string(entry.second.name)
            << ",\"ageMs\":" << std::max<long long>(0, now - entry.second.last_ms) << "}";
    }
    out << "]}\n";
    return out.str();
}
'''
replace_once(prune, helpers, "join helpers")

old_heartbeat = '''void session_presence_heartbeat(const std::string& player, const std::string& name) {
    if (player.empty()) return;
    std::lock_guard<std::mutex> lock(g_mutex);
    SessionPresence& entry = g_presence[player.substr(0, 64)];
    entry.name = name.substr(0, 32);
    entry.last_ms = now_ms();
}
'''
new_heartbeat = '''void session_presence_heartbeat(const std::string& player, const std::string& name) {
    if (player.empty()) return;
    const long long now = now_ms();
    const std::string key = player.substr(0, 64);
    std::lock_guard<std::mutex> lock(g_mutex);
    prune_presence_locked(now);

    SessionPresence& entry = g_presence[key];
    const std::string requested = trim(name);
    const std::string normalized = normalized_player_name(requested);
    if (!normalized.empty() && !player_name_taken_locked(normalized, key)) {
        entry.name = requested;
    } else if (entry.name.empty()) {
        entry.name = key;
    }
    entry.last_ms = now;
}
'''
replace_once(old_heartbeat, new_heartbeat, "unique heartbeat names")

identity_routes = '''    server.Get("/identity", identity);
    server.Post("/identity", identity);

    server.Get("/session", [](const httplib::Request& req, httplib::Response& res) {
'''
join_routes = '''    server.Get("/identity", identity);
    server.Post("/identity", identity);

    server.Get("/lobby-state", [](const httplib::Request&, httplib::Response& res) {
        res.set_header("Cache-Control", "no-store");
        res.set_content(lobby_json(), "application/json; charset=utf-8");
    });

    server.Get("/join-check", [](const httplib::Request& req, httplib::Response& res) {
        const std::string player = session_request_player_id(req);
        res.set_header("Cache-Control", "no-store");
        if (!player_has_join_reservation(player)) {
            res.status = 401;
            res.set_content("{\"ok\":false,\"error\":\"join required\"}\n",
                            "application/json; charset=utf-8");
            return;
        }
        res.status = 204;
    });

    server.Post("/join", [](const httplib::Request& req, httplib::Response& res) {
        std::string player = cookie_value(req.get_header_value("Cookie"), "dfcap_player");
        if (!valid_stable_player_id(player) && req.has_param("candidate")) {
            const std::string candidate = req.get_param_value("candidate");
            if (valid_stable_player_id(candidate)) player = candidate;
        }
        if (!valid_stable_player_id(player)) player = random_player_id();

        const std::string requested = req.has_param("name")
            ? req.get_param_value("name") : std::string();
        std::string accepted;
        std::string error;
        if (!reserve_player_name(player, requested, accepted, error)) {
            res.status = error == "player name already in use" ? 409 : 400;
            res.set_header("Cache-Control", "no-store");
            res.set_content("{\"ok\":false,\"error\":" + json_string(error) + "}\n",
                            "application/json; charset=utf-8");
            return;
        }

        res.set_header("Cache-Control", "no-store");
        res.set_header("Set-Cookie", "dfcap_player=" + player +
            "; Path=/; Max-Age=31536000; SameSite=Strict; HttpOnly");
        res.set_content("{\"ok\":true,\"playerId\":" + json_string(player) +
            ",\"displayName\":" + json_string(accepted) + "}\n",
            "application/json; charset=utf-8");
    });

    server.Get("/session", [](const httplib::Request& req, httplib::Response& res) {
'''
replace_once(identity_routes, join_routes, "join routes")

path.write_text(text, encoding="utf-8")
print("Join lobby patch applied successfully")
