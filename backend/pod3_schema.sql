-- POD-3 自有说明（进 main 后不再单独建 users/activities/credentials）。
-- 官方表结构以 schema.sql v1.5 的 credentials 为准：
--   issued → confirmed → signed
-- 本文件只补 POD-3 需要、且不会覆盖共享表的索引。

CREATE UNIQUE INDEX IF NOT EXISTS uq_credentials_activity_user
    ON credentials (activity_id, user_id);
