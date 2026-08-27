#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
cpp_path = root / "src/player_ownership.cpp"
guards_path = root / "src/write_guards.cpp"
js_path = root / "web/js/dfcapture-player-ownership.js"

cpp = cpp_path.read_text(encoding="utf-8-sig")
guards = guards_path.read_text(encoding="utf-8-sig")
js = js_path.read_text(encoding="utf-8-sig")


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"{label}: expected source fragment not found")
    return text.replace(old, new, 1)


# Ownership policy: players may claim only unowned active citizens, release only
# their own citizens, and may own at most five active citizens. Host management
# remains unrestricted.
cpp = replace_once(
    cpp,
    "constexpr int kSchema = 1;\n",
    "constexpr int kSchema = 1;\nconstexpr int kClaimLimit = 5;\n",
    "claim limit",
)

cpp = replace_once(
    cpp,
    "Json::Value snapshot_json(bool host) {\n"
    "    Json::Value root(Json::objectValue);\n"
    "    root[\"ok\"] = true;\n"
    "    root[\"schema\"] = kSchema;\n"
    "    root[\"saveDir\"] = g_save_dir;\n"
    "    root[\"host\"] = host;\n",
    "Json::Value snapshot_json(bool host, const std::string& requester) {\n"
    "    Json::Value root(Json::objectValue);\n"
    "    root[\"ok\"] = true;\n"
    "    root[\"schema\"] = kSchema;\n"
    "    root[\"saveDir\"] = g_save_dir;\n"
    "    root[\"host\"] = host;\n"
    "    root[\"playerId\"] = requester;\n"
    "    root[\"claimLimit\"] = kClaimLimit;\n",
    "snapshot requester",
)

cpp = replace_once(
    cpp,
    "    root[\"analytics\"][\"ownedByPlayer\"] = Json::Value(Json::objectValue);\n"
    "    for (const auto& count : owned_counts)\n"
    "        root[\"analytics\"][\"ownedByPlayer\"][count.first] = count.second;\n"
    "    return root;\n",
    "    root[\"analytics\"][\"ownedByPlayer\"] = Json::Value(Json::objectValue);\n"
    "    for (const auto& count : owned_counts)\n"
    "        root[\"analytics\"][\"ownedByPlayer\"][count.first] = count.second;\n"
    "    const auto requester_count = owned_counts.find(requester);\n"
    "    root[\"claimCount\"] = requester_count == owned_counts.end()\n"
    "        ? 0 : requester_count->second;\n"
    "    return root;\n",
    "snapshot claim count",
)

cpp = replace_once(
    cpp,
    "            snapshot = snapshot_json(session_request_is_host(req));\n",
    "            snapshot = snapshot_json(session_request_is_host(req),\n"
    "                                     session_request_player_id(req));\n",
    "snapshot route requester",
)

old_action_head = '''    server.Post("/ownership-action", [](const httplib::Request& req, httplib::Response& res) {
        if (!session_request_is_host(req)) {
            json_error(res, 403, "host only");
            return;
        }
        const std::string action =
            req.has_param("action") ? req.get_param_value("action") : std::string();
        if (action != "assign" && action != "transfer" && action != "clear" &&
                action != "scheduler-toggle") {
            json_error(res, 400,
                       "action must be assign, transfer, clear, or scheduler-toggle");
            return;
        }
'''
new_action_head = '''    server.Post("/ownership-action", [](const httplib::Request& req, httplib::Response& res) {
        const bool host = session_request_is_host(req);
        const std::string actor = session_request_player_id(req);
        const std::string action =
            req.has_param("action") ? req.get_param_value("action") : std::string();
        if (action != "assign" && action != "transfer" && action != "clear" &&
                action != "scheduler-toggle" && action != "claim" &&
                action != "release") {
            json_error(res, 400,
                       "action must be assign, transfer, clear, scheduler-toggle, claim, or release");
            return;
        }
        if (!host && action != "claim" && action != "release") {
            json_error(res, 403, "host only");
            return;
        }
        if (!host) {
            const auto players = session_players_snapshot();
            const bool joined = std::any_of(players.begin(), players.end(),
                [&](const SessionPlayer& player) { return player.player_id == actor; });
            if (!joined) {
                json_error(res, 403, "join the multiplayer lobby before claiming dwarves");
                return;
            }
        }
'''
cpp = replace_once(cpp, old_action_head, new_action_head, "ownership action authorization")

old_owner = '''        const std::string owner =
            req.has_param("owner") ? req.get_param_value("owner") : std::string();
        if (action != "clear" && !is_safe_player_id(owner)) {
            json_error(res, 400, "invalid player id");
            return;
        }
        const std::string owner_name = req.has_param("ownerName")
            ? req.get_param_value("ownerName").substr(0, 32)
            : session_display_name(owner).substr(0, 32);
'''
new_owner = '''        const std::string requested_owner =
            req.has_param("owner") ? req.get_param_value("owner") : std::string();
        const std::string owner = action == "claim" ? actor : requested_owner;
        if ((action == "assign" || action == "transfer" || action == "claim") &&
                !is_safe_player_id(owner)) {
            json_error(res, 400, "invalid player id");
            return;
        }
        const std::string owner_name = action == "claim"
            ? session_display_name(actor).substr(0, 32)
            : (req.has_param("ownerName")
                ? req.get_param_value("ownerName").substr(0, 32)
                : session_display_name(owner).substr(0, 32));
'''
cpp = replace_once(cpp, old_owner, new_owner, "claim owner identity")

cpp = replace_once(
    cpp,
    "            const std::string actor = session_request_player_id(req);\n"
    "            const long long timestamp = system_now_ms();\n",
    "            const long long timestamp = system_now_ms();\n",
    "reuse request actor",
)

old_mutation = '''            if (action == "clear") {
                if (previous == next_records.end()) {
                    json_error(res, 404, "unit has no owner");
                    return;
                }
                next_records.erase(unit_id);
            } else {
                Record record;
                record.unit_id = unit_id;
                record.historical_figure_id = unit->hist_figure_id;
                record.player_id = owner;
                record.player_name = owner_name.empty() ? owner : owner_name;
                record.assigned_by = actor;
                record.assigned_at_ms = timestamp;
                record.notes = notes;
                next_records[unit_id] = std::move(record);
            }
'''
new_mutation = '''            if (action == "clear" || action == "release") {
                if (previous == next_records.end()) {
                    json_error(res, 404, "unit has no owner");
                    return;
                }
                if (action == "release" && previous->second.player_id != actor) {
                    json_error(res, 403, "you may release only your own dwarf");
                    return;
                }
                next_records.erase(unit_id);
            } else {
                if (action == "claim") {
                    if (previous != next_records.end()) {
                        json_error(res, 409, "dwarf is already owned");
                        return;
                    }
                    int active_claims = 0;
                    for (const auto& entry : next_records) {
                        if (entry.second.player_id != actor) continue;
                        df::unit* claimed = df::unit::find(entry.first);
                        if (assignable_citizen(claimed)) ++active_claims;
                    }
                    if (active_claims >= kClaimLimit) {
                        json_error(res, 409,
                                   "claim limit reached (5 active dwarves per player)");
                        return;
                    }
                }
                Record record;
                record.unit_id = unit_id;
                record.historical_figure_id = unit->hist_figure_id;
                record.player_id = owner;
                record.player_name = owner_name.empty() ? owner : owner_name;
                record.assigned_by = actor;
                record.assigned_at_ms = timestamp;
                record.notes = notes;
                next_records[unit_id] = std::move(record);
            }
'''
cpp = replace_once(cpp, old_mutation, new_mutation, "self claim mutation")

# nginx always adds X-Forwarded-For/X-Real-IP before forwarding to the loopback
# DFCapture backend. Treat a local Host header as host unless a real external
# proxy marker (Cloudflare or RFC Forwarded) is present. Port 8765 remains bound
# to 127.0.0.1 on the Docker host, so remote players reach it only via Cloudflare.
old_host = '''bool request_is_host_tab(const httplib::Request& req) {
    const bool forwarded = req.has_header("X-Forwarded-For") || req.has_header("CF-Connecting-IP") ||
                           req.has_header("Forwarded") || req.has_header("X-Real-IP");
    return peer_ip_is_loopback(req.remote_addr) && !forwarded &&
           host_header_is_local(req.get_header_value("Host"));
}
'''
new_host = '''bool request_is_host_tab(const httplib::Request& req) {
    const bool externally_forwarded = req.has_header("CF-Connecting-IP") ||
                                      req.has_header("Forwarded");
    return peer_ip_is_loopback(req.remote_addr) && !externally_forwarded &&
           host_header_is_local(req.get_header_value("Host"));
}
'''
guards = replace_once(guards, old_host, new_host, "nginx-aware host detection")

# Player UI: show claim/release controls to normal players while preserving the
# host's existing transfer UI.
old_filters = '''    const filterOptions = (snapshot.players || []).map(row =>
      `<option value="${esc(row.playerId)}"${ownerFilter === row.playerId ? " selected" : ""}>${esc(row.name)}</option>`
    ).join("");
    const rows = visibleUnits().map(unit => {
'''
new_filters = '''    const filterOptions = (snapshot.players || []).map(row =>
      `<option value="${esc(row.playerId)}"${ownerFilter === row.playerId ? " selected" : ""}>${esc(row.name)}</option>`
    ).join("");
    const currentPlayer = String(snapshot.playerId || storagePlayer());
    const claimLimit = Number(snapshot.claimLimit) || 5;
    const claimCount = Number(snapshot.claimCount) || 0;
    const rows = visibleUnits().map(unit => {
'''
js = replace_once(js, old_filters, new_filters, "ownership player counters")

old_controls = '''      const controls = snapshot.host ? `
        <div class="ownership-controls">
          <select data-owner-select="${unit.unitId}" aria-label="Owner for ${esc(unit.name)}">
            <option value="">Unowned</option>${playerOptions(owner)}
          </select>
          <input data-owner-notes="${unit.unitId}" maxlength="128"
            value="${esc(unit.owner?.notes || "")}" placeholder="Role or note (optional)">
          <button type="button" data-owner-save="${unit.unitId}">Save</button>
        </div>` : "";
'''
new_controls = '''      const mine = owner && owner === currentPlayer;
      const controls = snapshot.host ? `
        <div class="ownership-controls">
          <select data-owner-select="${unit.unitId}" aria-label="Owner for ${esc(unit.name)}">
            <option value="">Unowned</option>${playerOptions(owner)}
          </select>
          <input data-owner-notes="${unit.unitId}" maxlength="128"
            value="${esc(unit.owner?.notes || "")}" placeholder="Role or note (optional)">
          <button type="button" data-owner-save="${unit.unitId}">Save</button>
        </div>` : (!owner ? `
        <div class="ownership-controls">
          <button type="button" data-owner-claim="${unit.unitId}"
            ${claimCount >= claimLimit ? "disabled" : ""}>Claim</button>
          <span>${claimCount}/${claimLimit} dwarves</span>
        </div>` : (mine ? `
        <div class="ownership-controls">
          <span>Owned by you</span>
          <button type="button" data-owner-release="${unit.unitId}">Release</button>
        </div>` : `
        <div class="ownership-controls"><span>🔒 Owned by ${esc(playerName(owner))}</span></div>`));
'''
js = replace_once(js, old_controls, new_controls, "claim release controls")

js = replace_once(
    js,
    '''        <span>${Number(a.unownedCitizens) || 0} unowned</span>
        <span>${Number(a.alignedActiveOrders) || 0} owner-aligned active orders</span>
''',
    '''        <span>${Number(a.unownedCitizens) || 0} unowned</span>
        <span>My dwarves ${claimCount}/${claimLimit}</span>
        <span>${Number(a.alignedActiveOrders) || 0} owner-aligned active orders</span>
''',
    "claim summary",
)

js = replace_once(
    js,
    '''      snapshot.host
        ? "Assignments persist with this fortress save."
        : "Only the host can assign, transfer, or clear dwarf ownership.");
''',
    '''      snapshot.host
        ? "Host can assign, transfer, or clear ownership. Assignments persist with this fortress save."
        : `Claim up to ${claimLimit} unowned active dwarves. You may release only your own dwarves.`);
''',
    "ownership footer",
)

bind_anchor = '''    clientPanel.querySelectorAll("[data-owner-save]").forEach(button => {
'''
claim_bindings = '''    clientPanel.querySelectorAll("[data-owner-claim]").forEach(button => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await jsonFetch("/ownership-action", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ action: "claim", unit: button.dataset.ownerClaim }).toString()
          });
          await load();
          render();
          window.dfAttribution?.invalidate?.(document);
        } catch (error) {
          button.disabled = false;
          alert(error.message);
        }
      });
    });
    clientPanel.querySelectorAll("[data-owner-release]").forEach(button => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await jsonFetch("/ownership-action", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ action: "release", unit: button.dataset.ownerRelease }).toString()
          });
          await load();
          render();
          window.dfAttribution?.invalidate?.(document);
        } catch (error) {
          button.disabled = false;
          alert(error.message);
        }
      });
    });
    clientPanel.querySelectorAll("[data-owner-save]").forEach(button => {
'''
js = replace_once(js, bind_anchor, claim_bindings, "claim release bindings")

for required in (
    'constexpr int kClaimLimit = 5;',
    'action != "claim"',
    'action == "release"',
    'root["claimLimit"] = kClaimLimit;',
    'root["claimCount"]',
):
    if required not in cpp:
        raise RuntimeError(f"ownership C++ patch missing expected fragment: {required}")

for required in (
    'data-owner-claim',
    'data-owner-release',
    'My dwarves ${claimCount}/${claimLimit}',
):
    if required not in js:
        raise RuntimeError(f"ownership UI patch missing expected fragment: {required}")

if 'X-Forwarded-For") || req.has_header("CF-Connecting-IP")' in guards:
    raise RuntimeError("old host detection still rejects nginx forwarding headers")

cpp_path.write_text(cpp, encoding="utf-8")
guards_path.write_text(guards, encoding="utf-8")
js_path.write_text(js, encoding="utf-8")
print("Self-claim ownership patch applied successfully")
