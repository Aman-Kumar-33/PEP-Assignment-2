import os

# Configuration
files_to_split = [
    {
        "path": "models/20180402-114759-vggface2.pt",
        "chunk_size": 90 * 1024 * 1024 # 90MB limit
    }
]

def split_file(file_path, chunk_size):
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    file_size = os.path.getsize(file_path)
    part_num = 1
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            part_name = f"{file_path}.part{part_num}"
            with open(part_name, 'wb') as chunk_file:
                chunk_file.write(chunk)
            
            print(f"✅ Created {part_name}")
            part_num += 1

    print(f"🎉 Splitting complete! You can now delete the original '{file_path}' before pushing to GitHub.")

if __name__ == "__main__":
    for item in files_to_split:
        split_file(item["path"], item["chunk_size"])