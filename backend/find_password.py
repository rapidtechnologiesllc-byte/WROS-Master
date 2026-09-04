import logging
import bcrypt

stored_hash = b'$2b$12$yv2ftrjtTOJaJKE890lrI.wlt.0eeGT6U6wNlO9PN/j58Ax19pknK'

passwords_to_try = [
    'TestRecruiter123',
    'TestRecruiter@123',
    'TestRecruiter123!',
    'Test@123',
    'password',
    'admin123',
    'Recruiter123',
    'Recruiter@123',
    'Admin123',
    'Admin@123',
]

print(f"Testing against hash: {stored_hash.decode()}\n")

for pwd in passwords_to_try:
    try:
        result = bcrypt.checkpw(pwd.encode('utf-8'), stored_hash)
        status = '✅' if result else '❌'
        print(f'{status} "{pwd}": {result}')
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f'❌ "{pwd}": Error - {type(e).__name__}: {e}')

print("\nIf none match, the password might be auto-generated in the database initialization script.")
