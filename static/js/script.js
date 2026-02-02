/* static/js/script.js */
const video = document.getElementById("videoElement");
const canvas = document.getElementById("canvasElement");
const context = canvas.getContext("2d");
const statusDiv = document.getElementById("status");

let capturedImages = [];
let attendanceInterval = null;

// --- CAMERA FUNCTIONS ---

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    statusDiv.innerText = "Camera started.";
  } catch (err) {
    statusDiv.innerText = "Error accessing camera: " + err;
    console.error("Camera Error:", err);
  }
}

function stopCamera() {
  const stream = video.srcObject;
  if (stream) {
    const tracks = stream.getTracks();
    tracks.forEach((track) => track.stop());
    video.srcObject = null;
  }
}

// --- REGISTRATION LOGIC ---

async function captureFaces() {
  capturedImages = [];
  let count = 0;
  const totalNeeded = 50;
  const progressDiv = document.getElementById("progress");
  const submitBtn = document.getElementById("submitBtn");

  statusDiv.innerText = "Capturing... Please move your head slightly.";

  // Capture 1 photo every 100ms
  let interval = setInterval(() => {
    if (count >= totalNeeded) {
      clearInterval(interval);
      statusDiv.innerText = "Capture Complete! Click 'Save Student' to finish.";
      submitBtn.disabled = false;
      return;
    }

    // Draw video frame to canvas
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to Base64 (JPEG format, 0.7 quality to save size)
    const dataURL = canvas.toDataURL("image/jpeg", 0.7);
    capturedImages.push(dataURL);

    count++;
    progressDiv.innerText = `Photos Taken: ${count} / ${totalNeeded}`;
  }, 100);
}

async function submitRegistration() {
  const name = document.getElementById("name").value;
  const reg_no = document.getElementById("reg_no").value;
  const department = document.getElementById("department").value;

  if (!name || !reg_no || capturedImages.length === 0) {
    alert("Please fill all fields and capture photos first.");
    return;
  }

  statusDiv.innerText = "Uploading data... This may take a moment.";

  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        reg_no: reg_no,
        department: department,
        images: capturedImages,
      }),
    });

    const result = await response.json();
    if (result.status === "success") {
      alert("Registration Successful!");
      window.location.href = "/";
    } else {
      alert("Error: " + result.message);
    }
  } catch (error) {
    console.error("Error:", error);
    statusDiv.innerText = "Upload Failed.";
  }
}

// --- ATTENDANCE LOGIC ---

function startAttendance() {
  startCamera();
  statusDiv.innerText = "System Active. Scanning for faces...";

  // Send a frame every 3 seconds to avoid overloading server
  attendanceInterval = setInterval(async () => {
    if (!video.srcObject) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0);

    const dataURL = canvas.toDataURL("image/jpeg", 0.7);

    try {
      const response = await fetch("/api/mark_attendance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataURL }),
      });

      const result = await response.json();

      // Just logging for now, we will add UI updates in Step 3
      console.log("Server Response:", result);

      if (result.match) {
        statusDiv.innerText = `✅ Marked Present: ${result.student}`;
        statusDiv.style.color = "green";

        // Reset status after 2 seconds
        setTimeout(() => {
          statusDiv.innerText = "Scanning...";
          statusDiv.style.color = "black";
        }, 2000);
      }
    } catch (error) {
      console.error("Attendance API Error:", error);
    }
  }, 3000); // 3000ms = 3 seconds
}

function stopAttendance() {
  clearInterval(attendanceInterval);
  stopCamera();
  statusDiv.innerText = "System Stopped.";
}
