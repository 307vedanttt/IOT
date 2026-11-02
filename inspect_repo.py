import urllib.request
import json
import os

repo_url = "https://api.github.com/repos/Sandesh64753/PPE-Gate-Compilance/contents"
req = urllib.request.Request(repo_url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as resp:
        items = json.loads(resp.read().decode())
        print("Files in repo:")
        for it in items:
            print(f"- {it['name']} ({it['type']})")
            if it['type'] == 'file' and it['name'].endswith(('.py', '.ino', '.txt', '.md', '.cpp', '.h', '.json')):
                # Fetch and print/save file
                print(f"  Downloading {it['name']}...")
                file_req = urllib.request.Request(it['download_url'], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(file_req) as f_resp:
                    content = f_resp.read().decode(errors='ignore')
                    out_path = os.path.join("repo_ref", it['name'])
                    os.makedirs("repo_ref", exist_ok=True)
                    with open(out_path, "w", encoding="utf-8") as out_f:
                        out_f.write(content)
                    print(f"  Saved to {out_path} ({len(content)} chars)")
            elif it['type'] == 'dir':
                # Check dir
                print(f"  Subdirectory: {it['name']}")
                sub_req = urllib.request.Request(it['url'], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(sub_req) as sub_resp:
                    sub_items = json.loads(sub_resp.read().decode())
                    for sit in sub_items:
                        print(f"    - {sit['name']} ({sit['type']})")
                        if sit['type'] == 'file' and sit['name'].endswith(('.py', '.ino', '.txt', '.md', '.cpp', '.h')):
                            sub_file_req = urllib.request.Request(sit['download_url'], headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(sub_file_req) as sf_resp:
                                sub_content = sf_resp.read().decode(errors='ignore')
                                sub_out_dir = os.path.join("repo_ref", it['name'])
                                os.makedirs(sub_out_dir, exist_ok=True)
                                with open(os.path.join(sub_out_dir, sit['name']), "w", encoding="utf-8") as out_f:
                                    out_f.write(sub_content)
                                print(f"    Saved {sit['name']} ({len(sub_content)} chars)")
except Exception as e:
    print("Error querying repo:", e)

