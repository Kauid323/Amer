import sqlite3

def initialize_database():
    conn = sqlite3.connect("./amer.db")
    c = conn.cursor()
    
    # 创建 QQ_table
    c.execute('''
    CREATE TABLE QQ_table (
        QQ_group_id TEXT PRIMARY KEY,
        YH_group_ids TEXT,  -- 存储 云湖 平台的群号列表，JSON 格式
        MC_server_ids TEXT  -- 存储 MC 平台的 token 列表，JSON 格式
    )
    ''')

    # 创建 YH_table
    c.execute('''
    CREATE TABLE YH_table (
        YH_group_id TEXT PRIMARY KEY,
        QQ_group_ids TEXT,  -- 存储 QQ 平台的群号列表，JSON 格式
        MC_server_ids TEXT  -- 存储 MC 平台的 token 列表，JSON 格式
    )
    ''')

    # 创建 MC_table
    c.execute('''
    CREATE TABLE MC_table (
        MCToken TEXT PRIMARY KEY,
        QQ_group_ids TEXT,  -- 存储 QQ 平台的群号列表，JSON 格式
        YH_group_ids TEXT   -- 存储 云湖 平台的群号列表，JSON 格式
    )
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成。")

if __name__ == "__main__":
    initialize_database()