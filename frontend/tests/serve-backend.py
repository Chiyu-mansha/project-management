"""Run existing backend routes against disposable fixtures, never backend/campus.db.

From frontend/: python tests/serve-backend.py --port 8012
Then set VITE_DEV_API_TARGET=http://127.0.0.1:8012 before starting Vite.
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8012)
parser.add_argument('--recommendations', action='store_true', help='Add recommendation fixtures and a local deterministic HTTP scoring gateway; never calls a real AI provider.')
args = parser.parse_args()
# Exercise member-1's internal notification HTTP call against this disposable backend.
os.environ['BACKEND_BASE_URL'] = f'http://127.0.0.1:{args.port}'
backend = Path(__file__).resolve().parents[2] / 'backend'
sys.path.insert(0, str(backend))

from auth_routes import hash_password

SMOKE_PASSWORD = 'smoke123'

if args.recommendations:
    class FixtureGateway(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path != '/api/ai/score' or payload['profile'].get('skills') == 'force_gateway_error':
                self.send_error(503, 'Fixture scoring unavailable')
                return
            activity = payload['activity']
            scores = {'major': 6 + activity['id'] % 5, 'interests': 8, 'skills': 7}
            scores.update({key: 10 if (activity.get(field) or 0) > 0 else 0 for key, field in [
                ('conduct', 'conduct_score'), ('innovation', 'innovation_score'), ('comprehensive', 'comprehensive_score')
            ]})
            body = json.dumps({'eligible': 10, 'scores': scores, 'source': 'mock'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    gateway = ThreadingHTTPServer(('127.0.0.1', 0), FixtureGateway)
    os.environ['AI_GATEWAY_URL'] = f'http://127.0.0.1:{gateway.server_port}'
    threading.Thread(target=gateway.serve_forever, daemon=True).start()
    print('TEST ONLY: deterministic local HTTP scoring fixture (source=mock), no real LLM call.', flush=True)

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
        if args.recommendations:
            conn.execute("UPDATE users SET major='计算机',grade='2024',interests='算法,竞赛',skills='Python',need_conduct_score=1,need_innovation_score=0,need_comprehensive_score=1 WHERE id=1")
            for aid in range(10, 36):
                conn.execute(
                    "INSERT INTO activities(id,title,organizer_id,type,status,signup_deadline,min_team_member,max_team_member,description,tags,conduct_score,innovation_score,comprehensive_score,article) VALUES(?,?,10,'科创竞赛','published','2099-12-31T23:59:59',1,4,?,'算法,编程',0.5,0,1,?)",
                    (aid, f'推荐联调活动 {aid}', 'POD-1 批量活动查询与 POD-2 推荐展示联调', f'# 推荐联调活动 {aid}\n\n这是临时测试活动，可进入报名。'),
                )
                member_schema = [{'field_key': 'student_id', 'label': '学号', 'type': 'text', 'required': True}, {'field_key': 'name', 'label': '姓名', 'type': 'text', 'required': True}]
                conn.execute("INSERT INTO forms(activity_id,organizer_id,form_team_schema,form_member_schema) VALUES(?,10,'[]',?)", (aid, json.dumps(member_schema)))
            for aid, state in [(6, 'ongoing'), (7, 'draft'), (8, 'finished')]:
                conn.execute("INSERT INTO activities(id,title,organizer_id,status,signup_deadline,min_team_member,max_team_member) VALUES(?,?,10,?,'2099-12-31T23:59:59',1,1)", (aid, f'状态联调活动 {aid}', state))
            conn.execute("INSERT INTO notifications(user_id,activity_id,type,content) VALUES(1,10,'报名提醒','临时通知联调记录：用于验证列表与已读接口')")
    import db
    import database
    db.DB_PATH = fixture_db
    database.DB_PATH = fixture_db
    from main import app
    import uvicorn
    print('Disposable review DB. Students: 1 (S1), 2 (S2); organizer: 10; activities: 1-4.', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port)
