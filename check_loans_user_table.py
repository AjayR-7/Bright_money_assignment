import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Check if the loans_user table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='loans_user';")
table_exists = cursor.fetchone()

if table_exists:
    print("The loans_user table exists.")
else:
    print("The loans_user table does not exist.")

# Close the connection
conn.close()
