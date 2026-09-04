import requests
import json

try:
    print("Testing login endpoint at http://localhost:8080/api/v1/auth/login")
    r = requests.post(
        'http://localhost:8080/api/v1/auth/login',
        json={'email': 'superuser@blitzenx.com', 'password': 'Test@12345'},
        timeout=5
    )

    print(f'\nStatus Code: {r.status_code}')
    print(f'Response:\n{r.text}')

    if r.status_code == 200:
        data = r.json()
        if 'access_token' in data:
            print('\n' + '='*50)
            print('✓✓✓ LOGIN SUCCESSFUL ✓✓✓')
            print('='*50)
            print(f'Token: {data["access_token"][:50]}...')
            if 'user' in data:
                print(f'User: {data["user"].get("user_name")}')
        else:
            print(f'\nError: {data.get("detail")}')

except Exception as e:
    print(f'Request failed: {type(e).__name__}: {e}')
