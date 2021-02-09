import os

import psycopg2
from .credential import DATABASE

try:
    DATABASE_URL = os.environ['DATABASE_URL']
except KeyError:
    DATABASE_URL = DATABASE


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
            prenom VARCHAR(100),
            lang VARCHAR(50)
        )"""
        )

    async def add_data(self, user_id, first_name, last_name, lang):
        await self._create_table()

        self.cursor.execute(
            f"""
            INSERT INTO botUser (identifiant, nom, prenom, lang)
            SELECT '{user_id}', '{first_name}', '{last_name}', '{lang}'
            WHERE NOT EXISTS (SELECT * FROM botuser WHERE identifiant = '{user_id}')
            """
        )

        self.conn.commit()

    async def update_data(self, user_id, lang):
        update_query = """UPDATE botuser set lang = %s where identifiant = %s"""
        self.cursor.execute(update_query, (lang, user_id))

        self.conn.commit()

    async def get_lang(self, user_id):
        data = "SELECT lang FROM botuser WHERE identifiant = %s"
        self.cursor.execute(data, (user_id,))

        return self.cursor.fetchall()

    @property
    async def select_data(self):
        self.cursor.execute("SELECT identifiant, nom, prenom, lang FROM botuser")

        return self.cursor.fetchall()

    @property
    async def commit_data(self):
        self.cursor.close()
        self.conn.close()
