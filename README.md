# MobiKD Backend Documentation

The MobiKD backend is a fast, lightweight RESTful API built with **FastAPI**. It serves as the central brain connecting the MobiKD Flutter Mobile App and the Next.js Admin Dashboard. It handles user authentication, securely stores scan history, and performs AI inference on potato leaf images using TensorFlow.

## 🚀 Technology Stack
* **Framework:** FastAPI (Python)
* **Server:** Uvicorn
* **Database:** PostgreSQL (Production on Render) / SQLite (Local Development)
* **AI Inference:** TensorFlow CPU (for `.tflite` model execution)
* **Image Processing:** Pillow (PIL)

---

## 🛠 Local Development Setup

You can easily run this server on your local machine for testing. It will automatically use a local SQLite database (`mobikd.db`) so you don't have to install PostgreSQL.

1. **Install Dependencies**
   Ensure you have Python 3.11 installed. Open a terminal in the `backend/` directory and run:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Server**
   ```bash
   uvicorn main:app --reload
   ```

3. **View Interactive API Docs (Swagger UI)**
   Once running, visit: [http://localhost:8000/docs](http://localhost:8000/docs). This interactive page lets you test all endpoints directly from your browser!

---

## ☁️ Production Deployment (Render)

The backend is configured for seamless deployment on **Render.com**. 

It uses a `render.yaml` Blueprint which automatically provisions:
1. A **PostgreSQL Database** (`mobikd-db`)
2. A **Python Web Service** running Python 3.11

**How it works:**
* Render injects the database connection string via the `DATABASE_URL` environment variable.
* The `database.py` script automatically detects `DATABASE_URL` and switches from SQLite to `psycopg2` (PostgreSQL).
* On server startup (`@app.on_event("startup")`), the app checks if the necessary SQL tables exist and automatically creates them if they don't.

---

## 📚 API Endpoints Overview

### Authentication (`/auth`)
* `POST /auth/signup` - Registers a new farmer (Phone, Name, Password).
* `POST /auth/login` - Authenticates a user and returns their profile info.
* `GET /profile` - Retrieves user profile (requires `X-User-Phone` header).
* `POST /profile/update` - Updates a user's name or phone number.

### AI Diagnosis (`/diagnose`)
* `POST /diagnose` - Expects an uploaded image file (`UploadFile`) and a farmer's phone number (`X-User-Phone` header).
  * Runs the 2-Stage TFLite Model pipeline (Leaf Validation -> Disease Classification).
  * Automatically saves the result and image to the database history.
  * Returns the predicted disease, confidences, and server latency.

### History (`/history`)
* `GET /history` - Returns all previous scans for the authenticated user.
* `DELETE /history/clear` - Clears all history for the user.

### Admin Dashboard Endpoints (`/admin`)
* `GET /admin/users` - Retrieves a list of all registered users with their total scan counts.
* `GET /admin/scans` - Retrieves global scan history across all users.
* `GET /admin/stats` - Returns aggregate data for charts (Total users, Disease distribution, Monthly trend lines, Average AI confidences).
* `DELETE /admin/users/{phone}` - Deletes a user and cascades the deletion to remove all their history.

---

## 🧠 AI Inference Pipeline (`inference.py`)

The inference engine executes a two-stage classification process:

1. **Stage 1 (Leaf Validator):**
   Checks if the uploaded image is actually a potato leaf. If the confidence is too low or it detects a non-leaf object, it halts and returns "Not a Leaf" or "Unknown".
2. **Stage 2 (Disease Classifier):**
   If Stage 1 passes, the image is passed to the main MobileNetV2 disease model, which categorizes it into one of the classes: `Healthy`, `Early Blight`, `Late Blight`, or `Bacterial Wilt`.

## 🗄️ Database Schema

The database relies on two main tables:

**1. `users` Table**
* `phone` (Primary Key)
* `name`
* `password`

**2. `scan_history` Table**
* `id` (Primary Key)
* `user_phone` (Foreign Key -> users.phone)
* `image_base64`
* `stage1_label` & `stage1_confidence`
* `stage2_label` & `stage2_confidence`
* `timestamp`
