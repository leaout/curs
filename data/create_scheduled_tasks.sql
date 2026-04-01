-- 定时任务表
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    task_type VARCHAR(50) NOT NULL,
    cron_expression VARCHAR(100),
    interval_seconds INTEGER,
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    config JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务执行日志表
CREATE TABLE IF NOT EXISTS scheduled_task_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES scheduled_tasks(id),
    status VARCHAR(20) NOT NULL,
    message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    duration_seconds NUMERIC(10, 2),
    error_detail TEXT
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON scheduled_task_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_started_at ON scheduled_task_logs(started_at DESC);
