"""Iron Fitness project package."""

# Use PyMySQL (pure Python, works on Vercel) in place of mysqlclient.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # only needed when DB_ENGINE=mysql
    pass
