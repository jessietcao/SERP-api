import requests
import concurrent.futures

base = "http://127.0.0.1:8000/search?q=ai&engine=brave&limit=3"

def call():
    r = requests.get(base)
    return r.status_code

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(call) for _ in range(30)]
    for f in futures:
        print(f.result())


# # Example: POST request
# new_user = {"name": "Alice", "email": "alice@example.com"}
# response = requests.post(f"{base_url}/users", json=new_user)
# if response.status_code == 201: # 201 often means "Created"
#     created_user = response.json()
#     print(created_user)
# else:
#     print(f"Error: {response.status_code} - {response.text}")