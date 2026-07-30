"""Okuma/yazma fonksiyonları — customer_app ve agent_console bu modül üzerinden konuşur."""
import hashlib
import hmac
import json
import secrets

from config.departments import DEPARTMENTS
from config.settings import STAFF_DEMO_PASSWORD
from storage.db import create_schema, get_connection


STAFF_HASH_SCHEME = "pbkdf2_sha256"
STAFF_HASH_ITERATIONS = 210_000


def _staff_password_material(staff_id, password):
    return f"{staff_id}:{password}".encode()


def _legacy_hash_staff_password(staff_id, password):
    return hashlib.sha256(_staff_password_material(staff_id, password)).hexdigest()


def hash_staff_password(staff_id, password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        _staff_password_material(staff_id, password),
        salt.encode(),
        STAFF_HASH_ITERATIONS,
    ).hex()
    return f"{STAFF_HASH_SCHEME}${STAFF_HASH_ITERATIONS}${salt}${digest}"


def _verify_staff_password_hash(staff_id, password, stored_hash):
    if stored_hash.startswith(f"{STAFF_HASH_SCHEME}$"):
        try:
            _, iterations, salt, expected = stored_hash.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                _staff_password_material(staff_id, password),
                salt.encode(),
                int(iterations),
            ).hex()
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(expected, digest)
    return hmac.compare_digest(stored_hash, _legacy_hash_staff_password(staff_id, password))


def _seed_staff():
    conn = get_connection()
    existing = conn.execute("SELECT COUNT(*) AS n FROM staff").fetchone()["n"]
    if existing:
        return
    for dept_key, dept in DEPARTMENTS.items():
        for member in dept["staff"]:
            conn.execute(
                "INSERT INTO staff (name, department, is_online) VALUES (?, ?, ?)",
                (member["name"], dept_key, int(member["is_online"])),
            )
    conn.commit()


def _backfill_staff_passwords():
    """password_hash bos olan (yeni kolon eklendiginde mevcut satirlar,
    ya da yeni seed edilen satirlar) her personele paylasilan demo sifreyi
    atar. Zaten dolu satirlara dokunmaz, tekrar calisirsa no-op."""
    conn = get_connection()
    rows = conn.execute("SELECT id FROM staff WHERE password_hash IS NULL").fetchall()
    for row in rows:
        conn.execute(
            "UPDATE staff SET password_hash = ? WHERE id = ?",
            (hash_staff_password(row["id"], STAFF_DEMO_PASSWORD), row["id"]),
        )
    conn.commit()


def init_db():
    create_schema()
    _seed_staff()
    _backfill_staff_passwords()


def create_session(language):
    conn = get_connection()
    cur = conn.execute("INSERT INTO sessions (language) VALUES (?)", (language,))
    conn.commit()
    return cur.lastrowid


def get_session(session_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def add_message(session_id, role, content, agent_name=None, tool_calls=None, sources=None,
                 orchestrator=None, flow_status=None):
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO messages (session_id, role, content, agent_name, tool_calls_json,
                                  sources_json, orchestrator_json, flow_status_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id, role, content, agent_name,
            json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            json.dumps(sources, ensure_ascii=False) if sources else None,
            json.dumps(orchestrator, ensure_ascii=False) if orchestrator else None,
            json.dumps(flow_status, ensure_ascii=False) if flow_status else None,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_messages(session_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id = ? ORDER BY id", (session_id,)
    ).fetchall()
    messages = []
    for row in rows:
        m = dict(row)
        m["tool_calls"] = json.loads(m.pop("tool_calls_json")) if m.get("tool_calls_json") else []
        m["sources"] = json.loads(m.pop("sources_json")) if m.get("sources_json") else []
        m["orchestrator"] = json.loads(m.pop("orchestrator_json")) if m.get("orchestrator_json") else None
        m["flow_status"] = json.loads(m.pop("flow_status_json")) if m.get("flow_status_json") else None
        messages.append(m)
    return messages


def create_handoff(session_id, department, reason, summary, urgency, pause_session=True):
    """pause_session=False: musteri canli bir insan yaniti BEKLEMIYOR (ör.
    satis lead'i — asenkron takip icin panele dusuyor ama musteri botla
    normal sohbete devam edebilir)."""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO handoffs (session_id, department, reason, summary, urgency)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, department, reason, summary, urgency),
    )
    if pause_session:
        conn.execute("UPDATE sessions SET status = 'waiting_human' WHERE id = ?", (session_id,))
    conn.commit()
    return cur.lastrowid


def list_pending_handoffs(department=None):
    conn = get_connection()
    if department:
        rows = conn.execute(
            "SELECT * FROM handoffs WHERE status = 'pending' AND department = ? ORDER BY created_at",
            (department,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM handoffs WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()
    return [dict(row) for row in rows]


def claim_handoff(handoff_id, staff_name, department=None):
    """department verilirse, handoff'un gercek departmani eslesmiyorsa
    reddedilir (savunma amacli — kuyruk zaten departmana gore filtrelendigi
    icin normal kullanimda tetiklenmez, sadece yaris durumlarina karsi).
    reason='sales_lead' olan kayitlar musterinin canli bekledigi bir devir
    DEGIL (asenkron takip) — bu yuzden claim edilince musterinin oturumu
    'with_human'a cekilmez, botla sohbetine kesintisiz devam eder."""
    conn = get_connection()
    row = conn.execute(
        "SELECT department, reason, session_id FROM handoffs WHERE id = ?", (handoff_id,)
    ).fetchone()
    if not row:
        return False
    if department and row["department"] != department:
        return False
    conn.execute(
        """UPDATE handoffs SET status = 'claimed', assigned_to = ?, claimed_at = datetime('now')
           WHERE id = ?""",
        (staff_name, handoff_id),
    )
    if row["reason"] != "sales_lead":
        conn.execute("UPDATE sessions SET status = 'with_human' WHERE id = ?", (row["session_id"],))
    conn.commit()
    return True


def post_human_reply(session_id, staff_name, content):
    return add_message(session_id, "human_agent", content, agent_name=staff_name)


def close_handoff(handoff_id):
    conn = get_connection()
    conn.execute("UPDATE handoffs SET status = 'closed' WHERE id = ?", (handoff_id,))
    row = conn.execute("SELECT session_id FROM handoffs WHERE id = ?", (handoff_id,)).fetchone()
    if row:
        conn.execute("UPDATE sessions SET status = 'bot' WHERE id = ?", (row["session_id"],))
    conn.commit()


def resume_bot_mode(session_id):
    """Musteri escalation beklerken 'bot ile devam et' dedi — SADECE
    session durumunu geri cevirir, handoff'a DOKUNMAZ (talep acik kalir,
    personel isterse yine yanitlayabilir)."""
    conn = get_connection()
    conn.execute("UPDATE sessions SET status = 'bot' WHERE id = ?", (session_id,))
    conn.commit()


def log_tool_call(session_id, tool_name, args, summary):
    conn = get_connection()
    conn.execute(
        "INSERT INTO tool_logs (session_id, tool_name, args_json, summary) VALUES (?, ?, ?, ?)",
        (session_id, tool_name, json.dumps(args, ensure_ascii=False), summary),
    )
    conn.commit()


def set_staff_online(staff_id, is_online):
    conn = get_connection()
    conn.execute("UPDATE staff SET is_online = ? WHERE id = ?", (int(is_online), staff_id))
    conn.commit()


def list_online_staff(department):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM staff WHERE department = ? AND is_online = 1", (department,)
    ).fetchall()
    return [dict(row) for row in rows]


def list_staff(department):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM staff WHERE department = ? ORDER BY name", (department,)
    ).fetchall()
    return [dict(row) for row in rows]


def list_all_staff():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM staff ORDER BY department, name").fetchall()
    return [dict(row) for row in rows]


def verify_staff_password(staff_id, password):
    conn = get_connection()
    row = conn.execute("SELECT password_hash FROM staff WHERE id = ?", (staff_id,)).fetchone()
    if not row or not row["password_hash"]:
        return False
    return _verify_staff_password_hash(staff_id, password, row["password_hash"])


def get_handoff(handoff_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM handoffs WHERE id = ?", (handoff_id,)).fetchone()
    return dict(row) if row else None


def get_handoff_for_session(session_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM handoffs WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_notes(session_id, profile, case_notes):
    conn = get_connection()
    conn.execute(
        """INSERT INTO session_notes (session_id, profile_json, case_json, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(session_id) DO UPDATE SET
               profile_json = excluded.profile_json,
               case_json = excluded.case_json,
               updated_at = excluded.updated_at""",
        (
            session_id,
            json.dumps(profile, ensure_ascii=False),
            json.dumps(case_notes, ensure_ascii=False),
        ),
    )
    conn.commit()


def get_notes(session_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM session_notes WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not row:
        return {"profile": {}, "case_notes": {}, "updated_at": None}
    return {
        "profile": json.loads(row["profile_json"]) if row["profile_json"] else {},
        "case_notes": json.loads(row["case_json"]) if row["case_json"] else {},
        "updated_at": row["updated_at"],
    }
