from werkzeug.security import generate_password_hash

# Replace with your actual password
plain_password = "wo123"

hashed_pw = generate_password_hash(plain_password)
print("Hashed password:", hashed_pw)
