# import os
# import base64
# import numpy as np
# import cv2
# from flask import Flask, render_template, request, jsonify
# from datetime import datetime
# import torch
# from facenet_pytorch import MTCNN, InceptionResnetV1
# from PIL import Image
# from io import BytesIO

# # Initialize Flask App
# app = Flask(__name__)

# # --- CONFIGURATION ---
# DATASET_FOLDER = 'dataset'
# CSV_FILE = 'attendance.csv'
# os.makedirs(DATASET_FOLDER, exist_ok=True)

# # --- AI MODELS ---
# # MTCNN is for Face Detection (finding the face in the image)
# # InceptionResnetV1 is for Face Recognition (identifying who it is)
# device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# mtcnn = MTCNN(keep_all=False, device=device)
# # resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)
# # Load the model structure without downloading weights
# resnet = InceptionResnetV1(pretrained=None)

# # Load your local weights
# # Note: Ensure the filename matches exactly what you downloaded
# state_dict = torch.load('models/20180402-114759-vggface2.pt', map_location=device)
# resnet.load_state_dict(state_dict)

# resnet.eval().to(device)
# print(f"Models loaded on {device}")

# # --- ROUTES ---

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/register')
# def register_page():
#     return render_template('register.html')

# @app.route('/api/register', methods=['POST'])
# def api_register():
#     try:
#         data = request.json
#         name = data.get('name')
#         reg_no = data.get('reg_no')
#         images_b64 = data.get('images') # List of Base64 strings

#         if not name or not reg_no or not images_b64:
#             return jsonify({"status": "error", "message": "Missing data"}), 400

#         # Create Student Folder
#         student_folder = os.path.join(DATASET_FOLDER, reg_no)
#         os.makedirs(student_folder, exist_ok=True)

#         embeddings = []

#         # Process each image
#         for i, img_str in enumerate(images_b64):
#             # Decode Base64
#             if ',' in img_str:
#                 header, encoded = img_str.split(",", 1)
#             else:
#                 encoded = img_str
            
#             img_data = base64.b64decode(encoded)
#             image = Image.open(BytesIO(img_data)).convert('RGB')

#             # Get embedding using FaceNet
#             # mtcnn crops the face, resnet calculates embedding
#             face_tensor = mtcnn(image)
#             if face_tensor is not None:
#                 # Calculate embedding
#                 emb = resnet(face_tensor.unsqueeze(0).to(device))
#                 embeddings.append(emb.detach().cpu().numpy())
            
#             # Save raw image for reference (optional)
#             image.save(os.path.join(student_folder, f"{i}.jpg"))

#         if not embeddings:
#             return jsonify({"status": "error", "message": "No faces detected in images"}), 400

#         # Average the embeddings to create a master profile
#         master_embedding = np.mean(embeddings, axis=0)
        
#         # Save the master embedding
#         np.save(os.path.join(student_folder, "embedding.npy"), master_embedding)
        
#         # Save Info
#         with open(os.path.join(student_folder, "info.txt"), "w") as f:
#             f.write(f"{name},{reg_no}")

#         return jsonify({"status": "success", "message": f"Registered {name} successfully!"})

#     except Exception as e:
#         print(f"Error: {e}")
#         return jsonify({"status": "error", "message": str(e)}), 500

# if __name__ == '__main__':
#     app.run(debug=True)
import os
import base64
import numpy as np
import cv2
import pandas as pd
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from PIL import Image
from io import BytesIO
# ... existing imports ...
import glob

# --- HELPER: JOIN MODEL PARTS ---
def stitch_model():
    """
    Reconstructs the model file from parts if the full file doesn't exist.
    """
    model_path = os.path.join("models", '20180402-114759-vggface2.pt')
    
    # If the full model already exists, we are good.
    if os.path.exists(model_path):
        return

    print("🧩 Stitching model parts together...")
    
    # Find all parts (part1, part2, etc.)
    parts = sorted(glob.glob(f"{model_path}.part*"))
    
    if not parts:
        print("❌ No model parts found! Make sure you pushed the .part files.")
        return

    with open(model_path, 'wb') as output_file:
        for part in parts:
            with open(part, 'rb') as part_file:
                output_file.write(part_file.read())
    
    print("✅ Model reconstructed successfully!")

# --- CALL THE STITCH FUNCTION ---
stitch_model() 

# --- AI SETUP ---
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
# ... rest of your code ...
app = Flask(__name__)

# --- CONFIGURATION ---
DATASET_FOLDER = 'dataset'
CSV_FILE = 'attendance.csv'
MODELS_FOLDER = 'models'
os.makedirs(DATASET_FOLDER, exist_ok=True)

# --- GLOBAL VARIABLES (MEMORY) ---
# These lists will hold the data of all registered students in RAM
known_embeddings = []
known_reg_nos = []
known_names = []

# --- AI SETUP ---
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 1. Face Detector (MTCNN)
mtcnn = MTCNN(keep_all=False, device=device)

# 2. Face Recognizer (InceptionResnetV1) - OFFLINE MODE
resnet = InceptionResnetV1(pretrained=None) # Don't download
try:
    # Load your local weights
    state_dict = torch.load(os.path.join(MODELS_FOLDER, '20180402-114759-vggface2.pt'), map_location=device)
    resnet.load_state_dict(state_dict)
    print("✅ Local Model Loaded Successfully!")
except Exception as e:
    print(f"❌ Error loading model: {e}")
    print("Make sure '20180402-114759-vggface2.pt' is in the 'models' folder.")

resnet.eval().to(device)


# --- HELPER FUNCTIONS ---

def load_known_faces():
    """
    Scans the 'dataset' folder and loads all students' .npy files into memory.
    Run this on startup and after every new registration.
    """
    global known_embeddings, known_reg_nos, known_names
    
    known_embeddings = []
    known_reg_nos = []
    known_names = []

    if not os.path.exists(DATASET_FOLDER):
        return

    print("Loading registered faces...")
    
    for reg_no in os.listdir(DATASET_FOLDER):
        student_path = os.path.join(DATASET_FOLDER, reg_no)
        
        # Check if it's a valid directory
        if os.path.isdir(student_path):
            emb_path = os.path.join(student_path, "embedding.npy")
            info_path = os.path.join(student_path, "info.txt")
            
            if os.path.exists(emb_path) and os.path.exists(info_path):
                # Load Embedding
                emb = np.load(emb_path)
                known_embeddings.append(emb)
                known_reg_nos.append(reg_no)
                
                # Load Name
                with open(info_path, "r") as f:
                    data = f.read().split(',')
                    known_names.append(data[0]) # Name is the first item
    
    print(f"✅ Loaded {len(known_embeddings)} students.")

def mark_attendance_csv(name, reg_no):
    """
    Updates the CSV file. Checks for duplicates before writing.
    """
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    # 1. Check/Create File
    if not os.path.isfile(CSV_FILE):
        df = pd.DataFrame(columns=['Date', 'Time', 'Name', 'RegNo', 'Status'])
        df.to_csv(CSV_FILE, index=False)
    
    # 2. Read existing data
    df = pd.read_csv(CSV_FILE)
    
    # 3. Check Duplicate (Same Student, Same Date)
    # We filter the dataframe to see if this RegNo exists for Today
    already_present = df[(df['RegNo'] == reg_no) & (df['Date'] == date_str)]
    
    if already_present.empty:
        # Mark Present
        new_record = pd.DataFrame([{
            'Date': date_str,
            'Time': time_str,
            'Name': name,
            'RegNo': reg_no,
            'Status': 'Present'
        }])
        # Use pd.concat instead of append (deprecated)
        df = pd.concat([df, new_record], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
        return True # Successfully marked
    else:
        return False # Already marked

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.json
        name = data.get('name')
        reg_no = data.get('reg_no')
        images_b64 = data.get('images')

        if not name or not reg_no or not images_b64:
            return jsonify({"status": "error", "message": "Missing data"}), 400

        student_folder = os.path.join(DATASET_FOLDER, reg_no)
        os.makedirs(student_folder, exist_ok=True)

        embeddings = []

        for i, img_str in enumerate(images_b64):
            if ',' in img_str: header, encoded = img_str.split(",", 1)
            else: encoded = img_str
            
            img_data = base64.b64decode(encoded)
            image = Image.open(BytesIO(img_data)).convert('RGB')

            # Detect & Embed
            face_tensor = mtcnn(image)
            if face_tensor is not None:
                emb = resnet(face_tensor.unsqueeze(0).to(device))
                embeddings.append(emb.detach().cpu().numpy())

        if not embeddings:
            return jsonify({"status": "error", "message": "No faces detected"}), 400

        # Average and Save
        master_embedding = np.mean(embeddings, axis=0)
        np.save(os.path.join(student_folder, "embedding.npy"), master_embedding)
        
        with open(os.path.join(student_folder, "info.txt"), "w") as f:
            f.write(f"{name},{reg_no}")

        # RELOAD MEMORY to include this new student immediately
        load_known_faces()

        return jsonify({"status": "success", "message": f"Registered {name}!"})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/mark_attendance', methods=['POST'])
def api_mark_attendance():
    global known_embeddings, known_names, known_reg_nos
    
    data = request.json
    image_data = data.get('image')

    if not image_data:
        return jsonify({"status": "error"}), 400

    # Decode Image
    if ',' in image_data: header, encoded = image_data.split(",", 1)
    else: encoded = image_data
    img_bytes = base64.b64decode(encoded)
    image = Image.open(BytesIO(img_bytes)).convert('RGB')

    # Detect Face
    face_tensor = mtcnn(image)
    if face_tensor is None:
        return jsonify({"match": False}) # No face found

    # Generate Embedding
    current_emb = resnet(face_tensor.unsqueeze(0).to(device)).detach().cpu().numpy()

    # MATCHING LOGIC
    if len(known_embeddings) == 0:
        return jsonify({"match": False})

    # Calculate Distance (Euclidean)
    # We compare current_emb against ALL known_embeddings at once
    dist_list = []
    for known_emb in known_embeddings:
        dist = np.linalg.norm(current_emb - known_emb)
        dist_list.append(dist)
    
    min_dist = min(dist_list)
    min_index = dist_list.index(min_dist)

    # Threshold (0.6 - 0.8 is usually good for FaceNet)
    if min_dist < 0.8:
        name = known_names[min_index]
        reg_no = known_reg_nos[min_index]
        
        # Mark in CSV
        mark_attendance_csv(name, reg_no)
        
        return jsonify({
            "match": True,
            "student": name,
            "reg_no": reg_no
        })
    else:
        return jsonify({"match": False})

# --- STARTUP ---
if __name__ == '__main__':
    load_known_faces() # Load faces before starting server
    app.run(debug=True)