# Google Cloud Deployment Guide (Free Tier)

This guide takes you through deploying the SIM-PRO-MAX application across Google Cloud Run (Backend) and Firebase Hosting (Frontends).

## Prerequisites

1.  **Google Cloud Account:** Create one at [cloud.google.com](https://cloud.google.com) (you get $300 in free credits, plus the Always Free tier).
2.  **Google Cloud CLI (`gcloud`):** [Install it here](https://cloud.google.com/sdk/docs/install).
3.  **Firebase CLI:** Run `npm install -g firebase-tools` in your terminal.

---

## Phase 1: Deploy Backend to Google Cloud Run

Cloud Run scales to zero and is free for the first 2 million requests per month. I have already generated the `Dockerfile` and `.dockerignore` for you.

1.  **Open your terminal and authenticate:**
    ```powershell
    gcloud auth login
    ```

2.  **Create a New Google Cloud Project:**
    *(Replace `my-sim-project-123` with a unique ID)*
    ```powershell
    gcloud projects create my-sim-project-123
    gcloud config set project my-sim-project-123
    ```

3.  **Enable Required Cloud APIs:**
    ```powershell
    gcloud services enable run.googleapis.com cloudbuild.googleapis.com
    ```

4.  **Deploy the backend!** *(Run this from your root project folder `C:\Users\sam\Documents\Projects\sim-pro-max\modern ui`)*
    ```powershell
    gcloud run deploy sim-backend --source . --platform managed --region us-central1 --allow-unauthenticated --port 8000 --memory 2Gi
    ```
    *(When it asks if you want to enable Artifact Registry or continue, say **Yes** (`y`).)*

5.  **Save the URL:** Once deployed, it will output a Service URL (e.g., `https://sim-backend-xxxxx-uc.a.run.app`). 

*(Note: Every time Cloud Run spins down, the SQLite database resets. For a demo, this is fine because your system auto-generates the schema and you can inject your simulation events immediately. Later, you can mount a GCS bucket or switch to a persistent database if needed).*

---

## Phase 2: Deploy Main Frontend to Firebase Hosting

Firebase Hosting is perfect for React/Vite SPAs. I've automatically added the required `firebase.json` for routing.

1.  **Log in to Firebase & Initialize:**
    ```powershell
    cd frontend
    firebase login
    firebase init hosting
    ```
    *   Select **"Use an existing project"** and choose the Google Cloud Project you created in Phase 1 (`my-sim-project-123`).
    *   When asked "What do you want to use as your public directory?", type **`dist`** (or `build`, depending on your Vite config, usually `dist`).
    *   When asked "Configure as a single-page app?", type **`y`** (Yes).
    *   When asked "Set up automatic builds and deploys with GitHub?", type **`n`** (No).
    *   If it asks "File dist/index.html already exists. Overwrite?", type **`n`** (No).

2.  **Update API References:**
    Update your frontend's environment variable (e.g. `.env` or configuration file) to point to the new Cloud Run URL from Phase 1 instead of `http://127.0.0.1:8000`.

3.  **Build and Deploy:**
    ```powershell
    npm run build
    firebase deploy --only hosting
    ```
    You will receive a public URL for your web app!

---

## Phase 3: Deploy Driver App to Firebase Hosting

We'll repeat the same Frontend steps for the Driver app. If you want them in the exact same Firebase project, we can deploy to multiple sites, but it's often easier to just deploy to another Firebase project or set up Multi-Site Hosting.

1.  **Build and Deploy (using the same project as the main frontend but deploying to a secondary site or just overriding):**
    ```powershell
    cd ../driver-app-main
    
    # Initialize a secondary site (Follow console instructions if creating a new Firebase project)
    firebase init hosting
    ```
2.  **Update Driver App API References:**
    Just like the frontend, change `http://127.0.0.1:8000` to your Cloud Run URL.
    
3.  **Build and Deploy:**
    ```powershell
    npm run build
    firebase deploy --only hosting
    ```

Your entire ecosystem is now live on the internet, secure with SSL, and running inside Google's Always Free tier constraints!
