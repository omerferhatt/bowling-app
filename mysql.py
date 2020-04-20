import mysql.connector


class MySQL:
    def __init__(self, host, user, passwd, database=None, device_name=None):
        self.host = host
        self.user = user
        self.passwd = passwd
        self.database = database
        self.device_name = device_name
        self.connection = mysql.connector.connect(
            host=self.host,
            user=self.user,
            passwd=self.passwd,
            database=self.database
        )
        self.cursor = self.connection.cursor(prepared=True)
