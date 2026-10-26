-- 校园活动智能通知&报名助理 数据库 schema v1.5
-- SQLite 版本;与飞书《数据库 Schema v1.5》文档保持一致
-- 任何结构变更先找技术负责人批准,改完立即更新本文档并升版本号
-- v1.5 备注(10-20 变更申请):activities 新增 article(AI推文展示)、cover_image(卡片流封面)(POD-1 申请,PM 批准);users/organizers 新增 avatar(账号管理头像,变更记录 #17,10-26 PM 追认补记)
-- v1.3 备注(10-11 变更申请):faqs 改 status 枚举 published/draft、category 按活动类型口径、新增 origin_title;新增 qa_logs 表(POD-1 申请,PM 批准)
-- v1.4 备注(10-19 新增):新增 activity_scores 打分结果表(POD-2 登录/画像/推荐,记录用户-比赛-各项得分)
-- 10-12 修正(POD-2 指出):时间默认值 datetime(now) → datetime('now'),不加引号会被 SQLite 当列名解析为 NULL
-- v1.2 备注(10-11 拍板):activities.status 增加 cancelled(POD-1 提案,PM 拍板)
-- v1.1 备注(10-11 复议):activities 报名截止字段回退为 signup_deadline
-- (POD-1 实现已用该名,原提出方撤回 registration_deadline)
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
    avatar TEXT,                            -- 头像(base64/URL,账号管理 #17 追认)
    need_comprehensive_score INTEGER,       -- 综合素养评定积分画像(0/1 是否需要)
    need_conduct_score INTEGER,             -- 操行分画像(0/1)
    need_innovation_score INTEGER,          -- 创新分画像(0/1)
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 二、organizers 发布者表(负责:POD-1,新增 v1.1)
CREATE TABLE organizers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL UNIQUE,           -- 工号(登录账号)
    password_hash TEXT NOT NULL,            -- 密码哈希
    name TEXT NOT NULL,                     -- 发布者姓名
    organization TEXT,                      -- 组织/社团
    avatar TEXT,                            -- 头像(base64/URL,账号管理 #17 追认)
    created_at TEXT DEFAULT (datetime('now'))
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
    signup_deadline TEXT,                   -- 报名截止(10-11 复议回退,以 POD-1 实现为准)
    min_team_member INTEGER NOT NULL,       -- 队伍最少人数(含队长,发布时设置)
    max_team_member INTEGER NOT NULL,       -- 队伍最多人数(含队长,发布时设置)
    max_participants INTEGER,               -- 报名上限(队数,空=不限)
    status TEXT DEFAULT draft,              -- draft/published/ongoing/finished/cancelled(v1.2 新增)
    article TEXT,                           -- AI 生成的推文 Markdown(v1.5 新增,发布者保存后学生详情页展示)
    cover_image TEXT,                       -- 封面图 URL(v1.5 新增,卡片流用,可空)
    created_at TEXT DEFAULT (datetime('now'))
);

-- 四、registrations 报名表(负责:POD-2)
CREATE TABLE registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL,           -- 对应 activities.id
    user_id INTEGER NOT NULL,               -- 对应 users.id(队长)
    form_id INTEGER NOT NULL,               -- 对应 forms.id
    registered_at TEXT DEFAULT (datetime('now')),
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
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
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
    created_at TEXT DEFAULT (datetime('now'))
);

-- 八、faqs FAQ 表(负责:POD-1)
CREATE TABLE faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER,                    -- 空=全局FAQ,非空=某活动专属
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,                          -- 竞赛类/讲座/分享类/培训/工作坊类/招募类/文体活动类/通知类
    source TEXT DEFAULT auto,               -- auto(AI自动沉淀)/manual(人工新增)/llm
    status TEXT DEFAULT published,          -- published(已发布)/draft(待审核,AI沉淀先入draft人工审核)
    origin_title TEXT DEFAULT '',           -- 推文AI提取时的来源推文标题
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 九、notifications 通知表(负责:POD-1,读写全归 POD-1)
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,               -- 接收人 users.id
    activity_id INTEGER,                    -- 关联活动,可空
    type TEXT,                              -- 报名提醒/截止预警/变更通知/开奖提醒/凭证通知
    content TEXT,
    is_read INTEGER DEFAULT 0,
    sent_at TEXT DEFAULT (datetime('now'))
);

-- 十、qa_logs 答疑日志表(负责:POD-1,新增 v1.3,只写日志不改业务表)
CREATE TABLE qa_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER,
    question TEXT NOT NULL,
    answer TEXT,
    source TEXT,
    count INTEGER DEFAULT 1,                -- 同问题出现次数(高频沉淀统计用)
    created_at TEXT
);

-- 十一、activity_scores 活动打分结果表(负责:POD-2,新增 v1.4)
-- 记录「用户-比赛-各项得分」;由推荐接口 a(打分入库)写入,接口 b(推荐列表)只读本表
CREATE TABLE activity_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,               -- 学生 users.id
    activity_id INTEGER NOT NULL,           -- 活动 activities.id
    signup_deadline TEXT,                   -- 报名截止时间(打分时从 activities 快照)
    eligible INTEGER NOT NULL DEFAULT 0,    -- 报名条件 0/10(打分项①,10=满足)
    major_score REAL,                       -- 专业匹配 0~10(打分项②,按程度)
    interests_score REAL,                   -- 兴趣 0~10(打分项③,按程度)
    skills_score REAL,                      -- 技能锻炼 0~10(打分项④,按程度)
    conduct_score INTEGER,                  -- 操行分 0/10(打分项⑤)
    innovation_score INTEGER,               -- 创新分 0/10(打分项⑥)
    comprehensive_score INTEGER,            -- 综合素养评定积分 0/10(打分项⑦)
    source TEXT,                            -- 打分来源(契约字段,llm/mock)
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, activity_id),           -- 一个用户对一个活动一条打分
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(activity_id) REFERENCES activities(id)
);
