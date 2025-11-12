import sqlite3

conn = sqlite3.connect("customers.db")
c = conn.cursor()

# 用户表
c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)''')

# 客户表
c.execute('''CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT,
    whatsapp TEXT,
    line TEXT,
    telegram TEXT,
    country TEXT,
    city TEXT,
    age INTEGER,
    job TEXT,
    salary TEXT,
    status TEXT,
    amount REAL,
    level TEXT,
    progress TEXT,
    main_manager TEXT,
    assistant TEXT,
    remark TEXT,
    created_at TEXT
)''')

# 操作日志
c.execute('''CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    action TEXT,
    timestamp TEXT
)''')

# 默认管理员
c.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")

conn.commit()
conn.close()
