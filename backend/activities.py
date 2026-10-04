from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from database import get_conn, dict_row

router = APIRouter(prefix="/api/activities", tags=["activities"])


class ActIn(BaseModel):
    title: str
    description: Optional[str] = ""
    organizer: Optional[str] = ""
    type: Optional[str] = ""
    status: Optional[str] = "published"


@router.get("")
def list_activities():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, title FROM activities ORDER BY id DESC LIMIT 200").fetchall()
    except Exception:
        rows = []
    conn.close()
    return {"items": [dict_row(r) for r in rows], "total": len(rows)}


@router.post("")
def create_activity(body: ActIn):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO activities(title,description,organizer,type,status) VALUES(?,?,?,?,?)",
        (body.title, body.description, body.organizer, body.type, body.status),
    )
    conn.commit()
    nid = cur.lastrowid
    row = conn.execute("SELECT id, title FROM activities WHERE id=?", (nid,)).fetchone()
    conn.close()
    return dict_row(row)
