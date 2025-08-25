import logging
import pyodbc
import mod_logMsg #mod_logMsg.py

# MSSQL接続情報

#LetsNote Local
server = None
database = None
username = None
password = None

#0=Let's Note
#1=ThinkPad X240
computer_type =2

if computer_type == 0:
    server		= 'localhost\\SQLEXPRESS'
    database 	= 'dis'
    username 	= 'sa'
    password 	= 'origin'
elif computer_type == 1:
    server		= '(localdb)\\MSSQLLocalDB'
    database	= 'discord_communityDB'
    username	= ''
    password	= ''
elif computer_type ==2:
    server		= 'localhost'
    database	= 'discord_communityDB'
    username	= ''
    password	= ''

# Windows認証で接続する例
connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;'

# 接続生成メソッド
def get_connection():
    try:
        logging.info("DB接続開始")
        conn = pyodbc.connect(connection_string)
        logging.info("DB接続成功")
        logging.info(f"return conn:[{conn}]")
        return conn
    except Exception as e:
        logging.error(f"DB接続失敗: {e}")
        raise



#==============================================
# tblUser

tblUser_keys={
    "seq_no",
    "join_dt",
    "user_id",
    "user_name",
    "user_nickname",
    "room_id",
    "room_name",
    "first_reaction",
    "balance",
    "last_reacted_post_id"
}


def insert_rec_tblUser(dt, conn):
    cursor = conn.cursor()
    try:
        sql = "SELECT COUNT(*) FROM tblUser WHERE user_id = ?"
        param = (dt["user_id"],)
        logging.info(f"[SQL実行][tblUser]ユーザーレコード存在確認")
        cursor.execute(sql, param)
        count = cursor.fetchone()[0]
        if count == 0:
            logging.info(f"ユーザーレコードが見つかりませんでした。新規作成します")
            keys = list(tblUser_keys - {"seq_no"})  # seq_noは自動採番なので除外
            columns = ", ".join(keys)
            placeholders = ", ".join(["?"] * len(keys))
            sql = f"INSERT INTO tblUser({columns}) VALUES ({placeholders})"
            param = tuple(dt[k] for k in keys)
            logging.info(f"[SQL実行][tblUser]ユーザーレコード追加")
            cursor.execute(sql, param)
            cursor.execute("SELECT SCOPE_IDENTITY()")
            conn.commit()
            logging.info(f"新規ユーザーレコードをtblUserに追加しました")
            logging.error(mod_logMsg.rt)
            return True
        else:
            logging.info(f"既にレコードが存在します")
            logging.info(mod_logMsg.rf)
            return False
    except Exception as e:
        logging.error(f"[SQLエラー][tblUser] {e}")
        return False
    finally:
        cursor.close()





def get_rec_tblUser(user_id, conn):
    cursor = conn.cursor()
    keys = list(tblUser_keys)
    columns = ", ".join(keys)
    sql = f"SELECT {columns} FROM tblUser WHERE user_id = ?"
    param = (user_id,)
    logging.info(f"[SQL実行][tblUser]user_id({user_id})が一致するレコードを取得")
    #logging.info(f"[SQL実行]{sql}[パラメーター]{repr(param)}")
    cursor.execute(sql, param)
    result = cursor.fetchone()
    cursor.close()
    if result:
        record = dict(zip(keys, result))
        logging.info(f"レコードを取得しました。")
        #logging.info(f"return record : [{record}]")
        return record
    else:
        logging.error(f"レコードを取得できませんでした")
        logging.error(f"return None")
        return None





def update_tblUser_byKey(user_id,key,value,conn):
    try:
        cursor = conn.cursor()
        if key not in tblUser_keys:
            logging.error(f"不正なカラム名です。[{key}]")
            logging.error(mod_logMsg.rf)
            return False
        sql = f"UPDATE tblUser SET {key} = ? WHERE user_id = ?"
        param = (value, user_id)
        logging.info(f"[SQL実行][tblUser]user_id({user_id})の[{key}]を[{value}]に更新")
        #logging.info(f"[SQL実行]{sql}[パラメーター]{param}")
        cursor.execute(sql, param)
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        logging.error(f"DB更新中にエラー: {e}")
        logging.error(mod_logMsg.rf)
        return False




#==============================================
# tblReactedHistory

tblReactedHistory_keys_ordered = ["reacted_dt", "post_id", "author_id", "reacted_user_id","channel_id"]


def insert_tblReactedHistory(reacted_dt, post_id, author_id, reactor_id, ch_id, conn):
    cursor = conn.cursor()
    columns = ", ".join(tblReactedHistory_keys_ordered)
    placeholders = ", ".join(["?"] * len(tblReactedHistory_keys_ordered))
    sql = f"INSERT INTO tblReactedHistory ({columns}) VALUES ({placeholders})"
    param = (reacted_dt, post_id, author_id, reactor_id, ch_id)
    logging.info(f"[SQL実行][tblReactedHistory]レコード追加")
    cursor.execute(sql, param)
    cursor.execute("SELECT SCOPE_IDENTITY()")
    conn.commit()
    cursor.close()
    logging.info(mod_logMsg.rt)
    return True

def get_rec_tblReactedhistory_top5(uid, conn):
    cursor = conn.cursor()
    sql = """
    SELECT TOP 5 post_id, channel_id, COUNT(*) AS cnt
    FROM dbo.tblReactedHistory
    WHERE author_id = ?
    GROUP BY post_id, channel_id
    ORDER BY cnt DESC
    """
    cursor.execute(sql, (uid,))
    rows = cursor.fetchall()
    cursor.close()
    # (post_id, channel_id)のタプルのリストを返す
    top5 = [(row[0], row[1]) for row in rows]
    return top5