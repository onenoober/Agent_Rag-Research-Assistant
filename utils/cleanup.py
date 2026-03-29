import os
files = ['test_phase11_create_smoke.py', 'test_phase11_eval.py']
for f in files:
    if os.path.exists(f):
        os.remove(f)
        print(f'已删除 {f}')