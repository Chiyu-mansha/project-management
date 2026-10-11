-- 校园活动智能通知&报名助理 数据库 schema v1.2
-- SQLite 版本,改动需经技术负责人批准并升级版本号
-- v1.2: activities 改造(organizer_id/综测三字段/组队人数/五态) + 新增 organizers 表

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
    type          TEXT,                          -- 学科类/文体类/科创竞赛/社会实践
    organizer_id  INTEGER,                       -- 发布人 organizers.id（MVP 先可空）
    start_time    TEXT,                          -- 开始时间 ISO8601
    end_time      TEXT,                          -- 结束时间
    location      TEXT,
    description   TEXT,                          -- 活动介绍(推文生成基础信息)
    requirements  TEXT,                          -- 报名条件
    tags          TEXT,                          -- 标签,逗号分隔
    has_ticket    INTEGER DEFAULT 1,             -- 是否发电子活动票 1/0
    comprehensive_score INTEGER DEFAULT 0,       -- 综合素养评定积分 0/1(能否加分)
    conduct_score REAL,                          -- 操行分(具体分值)
    innovation_score REAL,                       -- 创新分(具体分值)
    signup_deadline TEXT,                        -- 报名截止
    min_team_member INTEGER NOT NULL DEFAULT 1,  -- 一支队伍最少人数(含队长)
    max_team_member INTEGER NOT NULL DEFAULT 1,  -- 一支队伍最多人数(含队长)
    max_participants INTEGER,                    -- 报名上限(队伍数;空=不限)
    status        TEXT DEFAULT 'draft',          -- draft/published/ongoing/finished/cancelled
    created_at    TEXT DEFAULT (datetime('now'))
);

-- 发布者表(POD-1 读写,新增 v1.2)
CREATE TABLE organizers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id       TEXT UNIQUE NOT NULL,          -- 工号(登录用)
    password_hash TEXT NOT NULL,                 -- 密码哈希
    name          TEXT NOT NULL,                 -- 姓名
    organization  TEXT NOT NULL,                 -- 组织/社团
    created_at    TEXT DEFAULT (datetime('now'))
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
