"""Password hashing with stdlib PBKDF2-HMAC-SHA256 (no external dependency)."""
import hashlib,hmac,secrets
_ITERATIONS=300_000
def hash_password(password:str)->str:
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,_ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"
def verify_password(password:str,stored:str)->bool:
    try:
        scheme,iterations,salt_hex,hash_hex=stored.split("$")
        if scheme!="pbkdf2": return False
        digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt_hex),int(iterations))
        return hmac.compare_digest(digest.hex(),hash_hex)
    except (ValueError,AttributeError):
        return False
