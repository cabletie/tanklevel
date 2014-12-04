import sqlite3
con = sqlite3.connect('adcpiv2.db')
cur = con.cursor()
cur.execute('select * from adcpiv2 where rowid = (select seq from sqlite_sequence where name="adcpiv2");')
last_df_write = ','.join(str(i) for i in cur.fetchone())
print last_df_write
con.close()
