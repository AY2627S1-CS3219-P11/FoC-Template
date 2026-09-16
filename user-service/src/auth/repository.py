from uuid import UUID

from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation

from common.db import get_db_connection
from auth.exceptions import UserAlreadyExistsError
from auth.models import UserRecord, UserRoleResponse


def create_user(username: str, email: str, hashed_password: str) -> UserRecord:
    try:
        # email should already be normalized
        with get_db_connection() as db:
            with db.cursor(row_factory=dict_row) as cs:
                res = cs.execute(
                    """
                    INSERT INTO users(username, user_email, password_hash)
                    VALUES (%s, %s, %s)
                    RETURNING user_id, username, user_email, password_hash, user_role
                    """,
                    (username, email, hashed_password),
                ).fetchone()
    except UniqueViolation:
        raise UserAlreadyExistsError("Username or email already exists") from None


    return UserRecord(id=str(res["user_id"]), username=res["username"], 
                      email=res["user_email"], hashed_password=res["password_hash"], user_role=res["user_role"])

def find_user_by_email(email: str) -> UserRecord | None:
    with get_db_connection() as db:
        with db.cursor(row_factory=dict_row) as cs:
            res = cs.execute(
                """
                SELECT user_id, username, user_email, password_hash, user_role
                FROM users
                WHERE user_email = %s
                """
                , (email,),
            ).fetchone()

    if res is None:
        return None
    return UserRecord(id=str(res["user_id"]), username=res["username"], 
                      email=res["user_email"], hashed_password=res["password_hash"], user_role=res["user_role"])

def find_user_by_username(username: str) -> UserRecord | None:
    with get_db_connection() as db:
        with db.cursor(row_factory=dict_row) as cs:
            res = cs.execute(
                """
                SELECT user_id, username, user_email, password_hash, user_role
                FROM users
                WHERE username = %s
                """
                , (username,),
            ).fetchone()

    if res is None:
        return None
    return UserRecord(id=str(res["user_id"]), username=res["username"], 
                      email=res["user_email"], hashed_password=res["password_hash"], user_role=res["user_role"])


def find_user_role_by_id(user_id: UUID) -> UserRoleResponse | None:
    with get_db_connection() as db:
        with db.cursor(row_factory=dict_row) as cs:
            res = cs.execute(
                """
                SELECT user_id, user_role
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            ).fetchone()

    if res is None:
        return None
    return UserRoleResponse(user_id=res["user_id"], role=res["user_role"])


def update_username(user_id:str, new_username: str) -> UserRecord | None:
    with get_db_connection() as db:
        with db.cursor(row_factory=dict_row) as cs:
            res = cs.execute(
                """
                    UPDATE users 
                    SET username = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    RETURNING user_id, username, user_email, password_hash, user_role
                """, (new_username, user_id),
            ).fetchone()

    if res is None:
        return None

    return UserRecord(id=str(res["user_id"]), username=res["username"], 
                      email=res["user_email"], hashed_password=res["password_hash"], user_role=res["user_role"])

def update_user_email(user_id:str, new_user_email: str) -> UserRecord:
    with get_db_connection() as db:
        with db.cursor(row_factory=dict_row) as cs:
            res = cs.execute(
                """
                    UPDATE users 
                    SET user_email = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    RETURNING user_id, username, user_email, password_hash, user_role
                """, (new_user_email, user_id),
            ).fetchone()

    if res is None:
        return None
    
    return UserRecord(id=str(res["user_id"]), username=res["username"], 
                      email=res["user_email"], hashed_password=res["password_hash"], user_role=res["user_role"])
