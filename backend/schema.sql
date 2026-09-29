-- 校园活动智能通知&报名助理 数据库 schema v1
-- SQLite 版本,改动需经技术负责人批准并升级版本号

-- 用户表(POD-2 读,POD-1 只读脱敏画像)
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT UNIQUE NOT NULL,          -- 学号
    name          TEXT NOT NULL,
    major         TEXT,                          -- 专业
    grade         TEXT,                          -- 年级
    interests     TEXT,                          -- 兴趣标签,逗号分隔
    skills        TEXT,                          -- 技能标签,逗号分隔
    plan_requirements TEXT,                      -- 综测/规划需求
    role          TEXT DEFAULT 'student'         -- student / admin
);

-- 活动表(POD-1 读写)
CREATE TABLE activities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT,
    organizer     TEXT,                          -- 主办方
    type          TEXT,                          -- 讲座/竞赛/文体...
    tags          TEXT,                          -- 逗号分隔
    location      TEXT,
    start_time    TEXT,                          -- ISO8601
    end_time      TEXT,
    signup_deadline TEXT,
    max_participants INTEGER,
    has_ticket    INTEGER DEFAULT 0,             -- 是否发电子票
    zongce_score  TEXT,                          -- 综测加分说明
    status        TEXT DEFAULT 'draft'           -- draft/published/cancelled
);

-- 报名表(POD-2 读写,POD-1 读)
CREATE TABLE registrations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id   INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    team_name     TEXT,                          -- 团队报名用
    team_members  TEXT,                          -- 团队成员,逗号分隔
    extra_fields  TEXT,                          -- 报名表单自定义字段 JSON
    status        TEXT DEFAULT 'submitted',      -- submitted/approved/rejected
    created_at    TEXT
);

-- 凭证表(仅 POD-3 可写,防篡改)
CREATE TABLE credentials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    activity_id   INTEGER NOT NULL,
    status        TEXT DEFAULT 'issued',         -- issued/confirmed/signed
    checkin_time  TEXT,                          -- 现场签到时间
    confirmed_at  TEXT,                          -- 确认到场时间
    signed_at     TEXT,                          -- 电子签名时间
    pdf_path      TEXT                           -- 综测凭证 PDF 路径
);

-- FAQ 表(POD-1 读写)
CREATE TABLE faqs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id   INTEGER,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    source        TEXT DEFAULT 'manual'          -- manual / auto(AI 生成)
);

-- 站内通知表(POD-2 读,POD-1 写)
CREATE TABLE notifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    title         TEXT NOT NULL,
    content       TEXT,
    activity_id   INTEGER,
    is_read       INTEGER DEFAULT 0,
    created_at    TEXT
);
