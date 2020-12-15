import os

import psycopg2

# DATABASE_URL = os.environ['DATABASE_URL']
DATABASE_URL = "postgres://ptqrlbdhjodmii:010d69afabc3ee421677c2474702deb95b1b2981ec541bac535b69ae77b19a70@ec2-54-159-138-67.compute-1.amazonaws.com:5432/dtsrh6mt2bmlc"


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

        await self.commit_data()

    @property
    async def select_data(self):
        self.cursor.execute("SELECT identifiant, nom, prenom, lang FROM botuser")

        return self.cursor.fetchall()

    async def commit_data(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
