import os
import psycopg2

DATABASE_URL = os.environ['DATABASE_URL']
# DATABASE_URL = "postgres://xkimwgnucflqrz:fe509e3c0ccc68bdecb004cb294875a8bb4dd6698e0c6d255bb3be16a12b6fa9@ec2-46-137-177-160.eu-west-1.compute.amazonaws.com:5432/dls48gf8nv0ko"


class UserBot:
    def __init__(self):
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
            SELECT '{user_id}', '{first_name.capitalize()}', '{last_name.capitalize()}'
            WHERE NOT EXISTS (SELECT * FROM botuser WHERE identifiant = '{user_id}' AND nom = '{first_name}' AND prenom = '{last_name}')
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


# class UserChoice(UserBot):
#     def __init__(self):
#         self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
#         self.cursor = self.conn.cursor()
#         self._create_table()

#     def _create_table(self):
#         self.cursor.execute(
#             """
#         CREATE TABLE IF NOT EXISTS userChoice(
#             identifiant INT,
#             choix VARCHAR(100)
#         ) """
#         )

#     def add_data(self, user_id, choice):
#         self.cursor.execute(f"INSERT INTO userChoice (identifiant, choix) VALUES ('{user_id}', '{choice}')")

#         UserChoice.commit_data(self)
