import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

results = []

try:
    import main
    from fastapi.testclient import TestClient
    results.append(('import_main', True, 'OK'))
except Exception as exc:
    results.append(('import_main', False, traceback.format_exc()))
    print(results)
    raise SystemExit(1)

client = TestClient(main.app)

# local temporary DB so tests don't affect production file
os.environ['DB_PATH'] = os.path.join(tempfile.gettempdir(), 'test_tutor.db')


def run_test(name, func):
    try:
        value = func()
        results.append((name, True, value))
    except Exception:
        results.append((name, False, traceback.format_exc()))


run_test('root', lambda: (client.get('/').status_code, client.get('/').json()))
run_test('openapi', lambda: client.get('/openapi.json').status_code)

# Registration/login flow
import random
import string
email = f"test+{''.join(random.choice(string.ascii_lowercase) for _ in range(6))}@example.com"
password = 'password123'
run_test('register', lambda: client.post('/register', json={'name':'Test User','email':email,'password':password}).json())
run_test('login', lambda: client.post('/login', json={'email':email,'password':password}).json())
resp = client.post('/login', json={'email':email,'password':password})
if resp.status_code == 200:
    token = resp.json().get('token')
else:
    token = None
headers = {'Authorization': f'Bearer {token}'} if token else {}

run_test('chat', lambda: client.post('/chat', json={'message':'I need help with loops in Python'}, headers=headers).json())
run_test('hint', lambda: client.post('/hint', json={'question':'How do I loop through a list?','hint_level':1}, headers=headers).json())
run_test('progress', lambda: client.get('/progress', headers=headers).json())
run_test('history', lambda: client.get('/history', headers=headers).json())
run_test('summary', lambda: client.get('/summary', headers=headers).json())
run_test('summary_generate', lambda: client.post('/summary/generate', json={'topic':'Python'}, headers=headers).json())
run_test('evaluate', lambda: client.post('/evaluate', json={'question':'What is a loop?','student_answer':'A loop repeats actions','topic':'Python'}, headers=headers).json())
run_test('roadmap', lambda: client.get('/roadmap', headers=headers).json())
run_test('weak_topics', lambda: client.get('/weak-topics', headers=headers).json())
run_test('dashboard_overview', lambda: client.get('/dashboard/overview', headers=headers).json())

# Admin access
admin_resp = client.post('/login', json={'email':'admin@tutor.com','password':'admin123'})
run_test('admin_login', lambda: admin_resp.json())
admin_token = admin_resp.json().get('token') if admin_resp.status_code == 200 else None
admin_headers = {'Authorization': f'Bearer {admin_token}'} if admin_token else {}
run_test('admin_stats', lambda: client.get('/admin/stats', headers=admin_headers).json())

# RAG route existence
run_test('rag_route_exists', lambda: [r.path for r in main.app.routes if r.path.startswith('/rag')])

for item in results:
    name, ok, value = item
    status = 'PASS' if ok else 'FAIL'
    print(f'{name}: {status}')
    if not ok:
        print(value)

if any(not ok for _, ok, _ in results):
    raise SystemExit(1)
