import os
import psycopg2

DATABASE_URL = os.environ['DATABASE_URL']
# DATABASE_URL = "postgres://jsyycamnrliaqp:fb5d7dab0ccbfcffbfa1ba55c5ed660a3471d032b74b7d2ab9fd320110f95617@ec2-46-137-84-140.eu-west-1.compute.amazonaws.com:5432/d6juremsp6ctc1"


class UserBot:
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        try:
            self.cursor = self.conn.cursor()
        except psycopg2.InterfaceError:
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            self.cursor = self.conn.cursor()
        

    async def _create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS botuser(
            ID SERIAL PRIMARY KEY,
            identifiant INT,
            nom VARCHAR(100),
            prenom VARCHAR(100)
        )"""
        )

    async def add_data(self, user_id, first_name, last_name):
        await self._create_table()
        
        self.cursor.execute(
            f"""
            INSERT INTO botUser (identifiant, nom, prenom)
            SELECT '{user_id}', '{first_name}', '{last_name}'
            WHERE NOT EXISTS (SELECT * FROM botuser WHERE identifiant = '{user_id}')
            """
        )

        await self.commit_data()

    @property
    async def select_data(self):
        self.cursor.execute("SELECT identifiant, nom, prenom FROM botuser")

        data = self.cursor.fetchall()
        return data

    async def commit_data(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()