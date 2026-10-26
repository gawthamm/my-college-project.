"""
Database Setup Script for Campus Lost & Found System
Supports both MySQL and SQLite database initialization.
Usage:
    python setup_database.py --engine mysql --user root --password your_password
    python setup_database.py --engine sqlite
"""

import argparse
import sys
import os
import pymysql
from werkzeug.security import generate_password_hash
from config import Config

def setup_mysql(host, port, user, password, db_name):
    print(f"\n[*] Connecting to MySQL Server at {host}:{port} as '{user}'...")
    try:
        # Connect without DB first to create database
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print(f"[+] Connected to MySQL Server successfully!")
        
        # Create database
        print(f"[*] Creating database '{db_name}' if not exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE `{db_name}`;")
        
        # Read schema.sql
        schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_file):
            print(f"[*] Executing schema.sql statements...")
            with open(schema_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            # Execute commands
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            for stmt in statements:
                # Skip comments or USE/CREATE DATABASE
                if stmt.upper().startswith(('CREATE DATABASE', 'USE')):
                    continue
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    print(f"    [!] Notice during statement: {e}")
            conn.commit()
            print(f"[SUCCESS] MySQL database '{db_name}' has been completely set up and populated!")
        else:
            print(f"[!] Warning: schema.sql not found at {schema_file}")

        conn.close()
        return True
    except pymysql.MySQLError as err:
        print(f"\n[ERROR] MySQL Connection Failed: {err}")
        print("\nTroubleshooting tips:")
        print("1. Ensure MySQL Server is running (Open 'services.msc' -> Start 'MySQL267' or XAMPP MySQL).")
        print("2. Check your MySQL root password.")
        print("3. Verify port 3306 is open.\n")
        return False

def setup_sqlite():
    print("\n[*] Initializing SQLite database...")
    import database
    database.init_db()
    print(f"[SUCCESS] SQLite database initialized at {Config.SQLITE_PATH}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initialize Campus Lost & Found Database")
    parser.add_argument('--engine', choices=['mysql', 'sqlite', 'auto'], default='auto', help="Database engine to setup")
    parser.add_argument('--host', default=Config.MYSQL_HOST, help="MySQL Host")
    parser.add_argument('--port', type=int, default=Config.MYSQL_PORT, help="MySQL Port")
    parser.add_argument('--user', default=Config.MYSQL_USER, help="MySQL Username")
    parser.add_argument('--password', default=Config.MYSQL_PASSWORD, help="MySQL Password")
    parser.add_argument('--db', default=Config.MYSQL_DB, help="MySQL Database Name")
    
    args = parser.parse_args()

    if args.engine == 'mysql':
        success = setup_mysql(args.host, args.port, args.user, args.password, args.db)
        if not success:
            sys.exit(1)
    elif args.engine == 'sqlite':
        setup_sqlite()
    else:
        # Auto mode: try MySQL, if not reachable initialize SQLite
        print("[*] Running in auto mode...")
        import database
        if database.is_mysql_available():
            print("[+] MySQL service detected! Setting up MySQL...")
            setup_mysql(args.host, args.port, args.user, args.password, args.db)
        else:
            print("[!] MySQL service is not reachable on port 3306. Initializing local database...")
            setup_sqlite()
