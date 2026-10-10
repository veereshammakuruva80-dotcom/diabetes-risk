import re
from typing import Dict, Any, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from db import query_one, execute_commit

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^[+]?[\d\s\-\(\)]{7,20}$")
ALLOWED_GENDERS = ["Male", "Female", "Other", "Prefer not to say"]


def validate_email_format(email: str) -> bool:
    """Check if email matches standard pattern."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Retrieve user record by email (case-insensitive)."""
    if not email:
        return None
    query = """
        SELECT id, full_name, email, password_hash, age, gender, phone, created_at, updated_at
        FROM users
        WHERE LOWER(email) = LOWER(%s)
        LIMIT 1
    """
    return query_one(query, (email.strip(),))


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve sanitized user record by primary key id."""
    if not user_id:
        return None
    query = """
        SELECT id, full_name, email, password_hash, age, gender, phone, created_at, updated_at
        FROM users
        WHERE id = %s
        LIMIT 1
    """
    return query_one(query, (user_id,))


def register_user(
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
    age: Optional[Any] = None,
    gender: Optional[str] = None,
    phone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate, securely hash, and register a new user in the database.
    Rejects duplicate emails and invalid field values.
    """
    # 1. Full name validation
    if not full_name or not isinstance(full_name, str) or len(full_name.strip()) < 2:
        return {"success": False, "error": "Full name is required and must be at least 2 characters."}
    full_name = full_name.strip()
    if len(full_name) > 100:
        return {"success": False, "error": "Full name cannot exceed 100 characters."}

    # 2. Email validation
    if not email or not isinstance(email, str):
        return {"success": False, "error": "Email address is required."}
    email = email.strip().lower()
    if not validate_email_format(email):
        return {"success": False, "error": "Please provide a valid email address (e.g. name@example.com)."}

    # 3. Duplicate email prevention
    existing = get_user_by_email(email)
    if existing:
        return {"success": False, "error": "An account with this email address already exists. Please log in instead."}

    # 4. Password validation
    if not password or not isinstance(password, str):
        return {"success": False, "error": "Password is required."}
    if len(password) < 8:
        return {"success": False, "error": "Password must be at least 8 characters long."}
    if password != confirm_password:
        return {"success": False, "error": "Passwords do not match. Please re-enter your password."}

    # 5. Optional profile fields validation
    parsed_age = None
    if age not in (None, ""):
        try:
            parsed_age = int(age)
            if parsed_age < 1 or parsed_age > 120:
                return {"success": False, "error": "Age must be between 1 and 120."}
        except (ValueError, TypeError):
            return {"success": False, "error": "Age must be a valid number."}

    clean_gender = None
    if gender not in (None, ""):
        clean_gender = str(gender).strip()
        if clean_gender not in ALLOWED_GENDERS:
            return {"success": False, "error": f"Gender must be one of: {', '.join(ALLOWED_GENDERS)}."}

    clean_phone = None
    if phone not in (None, ""):
        clean_phone = str(phone).strip()
        if not PHONE_REGEX.match(clean_phone):
            return {"success": False, "error": "Please enter a valid phone number."}

    # 6. Secure password hashing
    password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    # 7. Database insertion
    insert_query = """
        INSERT INTO users (full_name, email, password_hash, age, gender, phone)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        user_id = execute_commit(
            insert_query,
            (full_name, email, password_hash, parsed_age, clean_gender, clean_phone)
        )
        return {
            "success": True,
            "user_id": user_id,
            "message": "Account created successfully! You can now log in."
        }
    except Exception as e:
        return {"success": False, "error": f"Registration failed due to a database error: {str(e)}"}


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user by verifying their email and hashed password.
    Returns generic error to prevent user enumeration.
    """
    if not email or not password:
        return {"success": False, "error": "Both email and password are required."}

    email = email.strip().lower()
    user = get_user_by_email(email)

    if not user:
        return {"success": False, "error": "Invalid email or password."}

    stored_hash = user.get("password_hash")
    if not stored_hash or not check_password_hash(stored_hash, password):
        return {"success": False, "error": "Invalid email or password."}

    # Sanitize user dict (remove password_hash before returning to session)
    safe_user = {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"],
        "age": user.get("age"),
        "gender": user.get("gender"),
        "phone": user.get("phone"),
        "created_at": user.get("created_at")
    }

    return {"success": True, "user": safe_user}


def update_user_profile(
    user_id: int,
    full_name: str,
    age: Optional[Any] = None,
    gender: Optional[str] = None,
    phone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update approved profile fields for the authenticated user.
    Strictly prohibits modifying other members' data or sensitive medical records.
    """
    if not user_id:
        return {"success": False, "error": "Authentication required."}

    existing = get_user_by_id(user_id)
    if not existing:
        return {"success": False, "error": "User account not found."}

    # Validate full name
    if not full_name or not isinstance(full_name, str) or len(full_name.strip()) < 2:
        return {"success": False, "error": "Full name is required (min 2 characters)."}
    full_name = full_name.strip()
    if len(full_name) > 100:
        return {"success": False, "error": "Full name cannot exceed 100 characters."}

    # Validate age
    parsed_age = None
    if age not in (None, ""):
        try:
            parsed_age = int(age)
            if parsed_age < 1 or parsed_age > 120:
                return {"success": False, "error": "Age must be between 1 and 120."}
        except (ValueError, TypeError):
            return {"success": False, "error": "Age must be a valid number."}

    # Validate gender
    clean_gender = None
    if gender not in (None, ""):
        clean_gender = str(gender).strip()
        if clean_gender not in ALLOWED_GENDERS:
            return {"success": False, "error": f"Gender must be one of: {', '.join(ALLOWED_GENDERS)}."}

    # Validate phone
    clean_phone = None
    if phone not in (None, ""):
        clean_phone = str(phone).strip()
        if not PHONE_REGEX.match(clean_phone):
            return {"success": False, "error": "Please enter a valid phone number."}

    update_query = """
        UPDATE users
        SET full_name = %s, age = %s, gender = %s, phone = %s
        WHERE id = %s
    """
    try:
        execute_commit(update_query, (full_name, parsed_age, clean_gender, clean_phone, user_id))
        return {
            "success": True,
            "message": "Profile updated successfully.",
            "updated_profile": {
                "id": user_id,
                "full_name": full_name,
                "age": parsed_age,
                "gender": clean_gender,
                "phone": clean_phone
            }
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to update profile: {str(e)}"}
