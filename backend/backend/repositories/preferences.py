import sqlite3


def get_theme(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT theme FROM preferences WHERE id = 1"
    ).fetchone()
    if row is None:
        raise RuntimeError("preferences row is missing")
    return str(row["theme"])


def set_theme(conn: sqlite3.Connection, theme: str) -> str:
    conn.execute(
        "UPDATE preferences SET theme = ? WHERE id = 1",
        (theme,),
    )
    return theme
