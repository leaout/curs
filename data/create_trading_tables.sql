-- 创建策略信号表
CREATE TABLE IF NOT EXISTS strategy_signals (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    signal_type VARCHAR(10) NOT NULL, -- 'BUY' or 'SELL'
    price DECIMAL(10, 2),
    volume INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    order_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, EXECUTED, CANCELLED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_strategy_signals_timestamp ON strategy_signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_strategy_signals_stock_code ON strategy_signals(stock_code);
CREATE INDEX IF NOT EXISTS idx_strategy_signals_strategy_name ON strategy_signals(strategy_name);
CREATE INDEX IF NOT EXISTS idx_strategy_signals_status ON strategy_signals(status);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_strategy_signals_updated_at ON strategy_signals;
CREATE TRIGGER update_strategy_signals_updated_at
    BEFORE UPDATE ON strategy_signals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建股票池表
CREATE TABLE IF NOT EXISTS stock_pool (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL UNIQUE,
    stock_name VARCHAR(100),
    category VARCHAR(50) DEFAULT 'default', -- 股票分类，如：热门、关注、黑名单等
    added_by VARCHAR(50) DEFAULT 'system', -- 添加者
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE, -- 是否激活
    notes TEXT -- 备注信息
);

-- 创建股票池索引
CREATE INDEX IF NOT EXISTS idx_stock_pool_category ON stock_pool(category);
CREATE INDEX IF NOT EXISTS idx_stock_pool_active ON stock_pool(is_active);
CREATE INDEX IF NOT EXISTS idx_stock_pool_stock_code ON stock_pool(stock_code);

-- 创建股票池更新触发器
DROP TRIGGER IF EXISTS update_stock_pool_updated_at ON stock_pool;
CREATE TRIGGER update_stock_pool_updated_at
    BEFORE UPDATE ON stock_pool
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 创建涨停股票表
CREATE TABLE IF NOT EXISTS zt_stocks (
    trade_date DATE NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    CONSTRAINT zt_stocks_pkey PRIMARY KEY (trade_date, stock_code)
);

-- 创建涨停股票索引
CREATE INDEX IF NOT EXISTS idx_zt_stocks_stock_code ON zt_stocks(stock_code);
CREATE INDEX IF NOT EXISTS idx_zt_stocks_trade_date ON zt_stocks(trade_date);

-- 创建订单跟踪表
CREATE TABLE IF NOT EXISTS order_tracking (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    order_type VARCHAR(10) NOT NULL,
    volume INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    filled_volume INTEGER DEFAULT 0,
    filled_price DECIMAL(10, 2),
    cancel_count INTEGER DEFAULT 0,
    order_time TIMESTAMP NOT NULL,
    filled_time TIMESTAMP,
    cancel_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_order_tracking_order_id ON order_tracking(order_id);
CREATE INDEX IF NOT EXISTS idx_order_tracking_stock_code ON order_tracking(stock_code);
CREATE INDEX IF NOT EXISTS idx_order_tracking_status ON order_tracking(status);

-- 创建盈利统计表
CREATE TABLE IF NOT EXISTS profit_stats (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    order_id VARCHAR(50),
    buy_price DECIMAL(10, 2) NOT NULL,
    buy_time TIMESTAMP NOT NULL,
    filled_price DECIMAL(10, 2),
    filled_time TIMESTAMP,
    sell_price DECIMAL(10, 2),
    sell_time TIMESTAMP,
    max_profit_pct DECIMAL(10, 2),
    time_to_max_profit_seconds INTEGER,
    hold_seconds INTEGER,
    profit_pct DECIMAL(10, 2),
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_profit_stats_stock_code ON profit_stats(stock_code);
CREATE INDEX IF NOT EXISTS idx_profit_stats_status ON profit_stats(status);
CREATE INDEX IF NOT EXISTS idx_profit_stats_buy_time ON profit_stats(buy_time);

-- 创建股票代码名称表
CREATE TABLE IF NOT EXISTS stock_info (
    stock_code VARCHAR(20) NOT NULL PRIMARY KEY,
    stock_name VARCHAR(100),
    exchange VARCHAR(10),
    list_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_info_name ON stock_info(stock_name);
CREATE INDEX IF NOT EXISTS idx_stock_info_exchange ON stock_info(exchange);
