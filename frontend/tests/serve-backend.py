"""Run existing backend routes against disposable fixtures, never backend/campus.db.

From frontend/: python tests/serve-backend.py --port 8012
Then set VITE_DEV_API_TARGET=http://127.0.0.1:8012 before starting Vite.
"""
import argparse
from pathlib import Path
import sqlite3
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8012)
args = parser.parse_args()
backend = Path(__file__).resolve().parents[2] / 'backend'
sys.path.insert(0, str(backend))

from auth_routes import hash_password

SMOKE_PASSWORD = 'smoke123'

with tempfile.TemporaryDirectory(prefix='pod2-frontend-') as fixture_dir:
    fixture_db = Path(fixture_dir) / 'review.db'
    with sqlite3.connect(fixture_db) as conn:
        conn.executescript((backend / 'schema.sql').read_text(encoding='utf-8'))
        ph = hash_password(SMOKE_PASSWORD)
        conn.executemany(
            'INSERT INTO users(id,password_hash,name,student_id) VALUES(?,?,?,?)',
            [(1, ph, '示例队长', 'S1'), (2, ph, '示例队员', 'S2')],
        )
        conn.execute("INSERT INTO organizers(id,account,password_hash,name) VALUES(10,'review',?,'联调发布者')", (ph,))
        for activity_id, title, status, deadline in [
            (1, 'POD-2 前端联调活动', 'published', '2099-12-31T23:59:59'),
            (2, '已取消活动', 'cancelled', '2099-12-31T23:59:59'),
            (3, '已截止活动', 'published', '2000-01-01T00:00:00'),
            (4, '空白报名表单活动', 'published', '2099-12-31T23:59:59'),
        ]:
            conn.execute(
                'INSERT INTO activities(id,title,organizer_id,status,signup_deadline,min_team_member,max_team_member,max_participants) VALUES(?,?,10,?,?,1,4,10)',
                (activity_id, title, status, deadline),
            )
    import db
    import database
    db.DB_PATH = fixture_db
    database.DB_PATH = fixture_db
    from main import app
    import uvicorn
    print('Disposable review DB. Students: 1 (S1), 2 (S2); organizer: 10; activities: 1-4.', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port)
