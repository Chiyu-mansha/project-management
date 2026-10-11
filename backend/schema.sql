-- 校园活动智能通知&报名助理 数据库 schema v1.1
-- SQLite 版本;与飞书《数据库 Schema v1.1》文档保持一致
-- 任何结构变更先找技术负责人批准,改完立即更新本文档并升版本号
-- 约定:表名复数、字段 snake_case、主键统一 id 自增;每张表标注负责 POD

-- 一、users 用户表(负责:POD-2)——仅存学生;发布者见 organizers 表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,                     -- 真实姓名
    student_id TEXT NOT NULL UNIQUE,        -- 学号(发布者无学号,不入此表)
    major TEXT,                             -- 专业(推荐匹配用)
    grade TEXT,                             -- 年级(推荐匹配用)
    interests TEXT,                         -- 兴趣标签,逗号分隔
    skills TEXT,                            -- 技能标签,逗号分隔
    need_comprehensive_score INTEGER,       -- 综合素养评定积分画像(0/1 是否需要)
    need_conduct_score INTEGER,             -- 操行分画像(0/1)
    need_innovation_score INTEGER,          -- 创新分画像(0/1)
    created_at TEXT DEFAULT (datetime(now)),
    updated_at TEXT DEFAULT (datetime(now))
);

-- 二、organizers 发布者表(负责:POD-1,新增 v1.1)
CREATE TABLE organizers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL UNIQUE,           -- 工号(登录账号)
    password_hash TEXT NOT NULL,            -- 密码哈希
    name TEXT NOT NULL,                     -- 发布者姓名
    organization TEXT,                      -- 组织/社团
    created_at TEXT DEFAULT (datetime(now))
);

-- 三、activities 活动/竞赛表(负责:POD-1)
CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT,                              -- 学科类/文体类/科创竞赛/社会实践
    organizer_id INTEGER,                   -- 发布人 organizers.id(外键引用)
    start_time TEXT,                        -- 开始时间
    end_time TEXT,                          -- 结束时间
    location TEXT,
    description TEXT,                       -- 活动介绍(推文生成的基础信息)
    requirements TEXT,                      -- 报名条件
    tags TEXT,                              -- 标签,逗号分隔(推荐匹配用)
    has_ticket INTEGER DEFAULT 1,           -- 是否发电子活动票 1/0
    comprehensive_score INTEGER,            -- 综合素养评定积分(0/1 是否加分)
    conduct_score DECIMAL(3,1),             -- 操行分(具体分值)
    innovation_score DECIMAL(3,1),          -- 创新分(具体分值)
    registration_deadline TEXT,             -- 报名截止
    min_team_member INTEGER NOT NULL,       -- 队伍最少人数(含队长,发布时设置)
    max_team_member INTEGER NOT NULL,       -- 队伍最多人数(含队长,发布时设置)
    max_participants INTEGER,               -- 报名上限(队数,空=不限)
    status TEXT DEFAULT draft,              -- draft/published/ongoing/finished
    created_at TEXT DEFAULT (datetime(now))
);

-- 四、registrations 报名表(负责:POD-2)
CREATE TABLE registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,           -- 对应 activities.id
    user_id INTEGER NOT NULL,               -- 对应 users.id(队长)
    form_id INTEGER NOT NULL,               -- 对应 forms.id
    registered_at TEXT DEFAULT (datetime(now)),
    extra_fields TEXT,                      -- 自定义报名字段,JSON
    UNIQUE(activity_id, user_id),           -- 每个用户只能作为队长报名一次
    FOREIGN KEY(activity_id) REFERENCES activities(id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(form_id) REFERENCES forms(id)
);

-- 五、forms 报名表格式表(负责:POD-2,新增 v1.1)
CREATE TABLE forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL UNIQUE,    -- 一个活动一张表单
    organizer_id INTEGER NOT NULL,          -- 发布者 organizers.id
    form_team_schema TEXT,                  -- 队伍公共表单 JSON(原 team_fields)
    form_member_schema TEXT,                -- 每个队员的表单 JSON(原 member_fields)
    created_at TEXT DEFAULT (datetime(now)),
    updated_at TEXT DEFAULT (datetime(now)),
    FOREIGN KEY(activity_id) REFERENCES activities(id),
    FOREIGN KEY(organizer_id) REFERENCES organizers(id)
);

-- 六、registration_members 报名成员子表(负责:POD-2,新增 v1.1)
CREATE TABLE registration_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL,       -- 关联 registrations.id 报名单
    user_id INTEGER NOT NULL,               -- 队员 user_id,关联 users.id
    role TEXT NOT NULL,                     -- 枚举:captain / member(member=非队长队员)
    activity_id INTEGER NOT NULL,           -- 对应 activities.id
    UNIQUE(activity_id, user_id),           -- 每个用户在同一活动只能加入一支队伍
    FOREIGN KEY(registration_id) REFERENCES registrations(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(activity_id) REFERENCES activities(id)
);

-- 七、credentials 电子活动票/综测凭证表(负责:POD-3,仅 POD-3 写)
-- 状态流转:issued(发放)→ confirmed(名单确认)→ signed(已签章)
CREATE TABLE credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT DEFAULT issued,             -- issued/confirmed/signed
    checkin_time TEXT,                      -- 签到时间
    confirmed_at TEXT,                      -- 负责人确认名单时间
    signed_at TEXT,                         -- 电子签章时间
    pdf_path TEXT,                          -- 凭证 PDF 文件路径
    comprehensive_score INTEGER,            -- 本活动综测加分(0/1,冗余,导出用)
    created_at TEXT DEFAULT (datetime(now))
);

-- 八、faqs FAQ 表(负责:POD-1)
CREATE TABLE faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER,                    -- 空=全局FAQ,非空=某活动专属
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,                          -- 报名/时间/地点/奖项/综测等
    source TEXT DEFAULT auto,               -- auto(AI自动沉淀)/manual(人工新增)/llm
    status TEXT DEFAULT online,             -- online/offline(下架)
    updated_at TEXT DEFAULT (datetime(now))
);

-- 九、notifications 通知表(负责:POD-1,读写全归 POD-1)
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,               -- 接收人 users.id
    activity_id INTEGER,                    -- 关联活动,可空
    type TEXT,                              -- 报名提醒/截止预警/变更通知/开奖提醒/凭证通知
    content TEXT,
    is_read INTEGER DEFAULT 0,
    sent_at TEXT DEFAULT (datetime(now))
);
