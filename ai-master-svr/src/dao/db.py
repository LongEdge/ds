import sqlite3

class CDB:
    @classmethod
    def get_conn(cls):
        conn = sqlite3.connect('test.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn