"""灌入演示数据（发布者/学生/活动/表单）。

用法（演示前跑一次，先停掉后端）：
    python seed_demo.py
"""
from __future__ import annotations

import json

import db

# 每次从干净库开始，保证可重复执行
if db.DB_PATH.exists():
    db.DB_PATH.unlink()
db.init_db()

with db.transaction() as conn:
    # 学生（users）
    conn.execute("INSERT INTO users (password_hash, name, student_id, major, grade) VALUES ('x','张三','2023001','软件工程','2023')")
    conn.execute("INSERT INTO users (password_hash, name, student_id, major, grade) VALUES ('x','李四','2023002','数字媒体','2023')")
    conn.execute("INSERT INTO users (password_hash, name, student_id, major, grade) VALUES ('x','王五','2023003','计算机','2023')")
    # 发布者（organizers）
    conn.execute("INSERT INTO organizers (account, password_hash, name, organization) VALUES ('g001','x','王老师','校团委')")
    # 活动（activities）
    cur1 = conn.execute(
        "INSERT INTO activities (title, type, organizer_id, status, signup_deadline, min_team_member, max_team_member, max_participants, description) "
        "VALUES ('软件创新大赛', '科创竞赛', 1, 'published', '2099-01-01T00:00:00', 2, 4, 10, '面向全校的软件创新比赛')"
    )
    act1 = cur1.lastrowid
    cur2 = conn.execute(
        "INSERT INTO activities (title, type, organizer_id, status, signup_deadline, min_team_member, max_team_member, max_participants, description) "
        "VALUES ('AI 讲座报名', '讲座', 1, 'published', '2099-01-01T00:00:00', 1, 1, NULL, '单人报名讲座')"
    )
    act2 = cur2.lastrowid

# 给活动1 预置一张报名表单（队伍项目 + 队员学号/姓名/专业），学生可直接报名
team = [
    {"field_key": "project_name", "label": "项目名称", "type": "text", "required": True},
    {"field_key": "project_intro", "label": "项目简介", "type": "textarea", "required": False},
]
member = [
    {"field_key": "student_id", "label": "学号", "type": "text", "required": True},
    {"field_key": "name", "label": "姓名", "type": "text", "required": True},
    {"field_key": "major", "label": "专业", "type": "text", "required": False},
]
db.execute(
    "INSERT INTO forms (activity_id, organizer_id, form_team_schema, form_member_schema) VALUES (?, ?, ?, ?)",
    (act1, 1, json.dumps(team, ensure_ascii=False), json.dumps(member, ensure_ascii=False)),
)

print("演示数据已灌入:")
print("  学生: 张三 id=1(token=student:1) / 李四 id=2(student:2) / 王五 id=3(student:3)")
print("  发布者: 王老师 id=1(token=organizer:1)")
print(f"  活动: {act1}=软件创新大赛(组队2-4人, 已配表单)  {act2}=AI讲座报名(单人, 未配表单)")
print("  演示页: http://localhost:5173/demo/index.html")
