# Deployment Guide

This guide explains the easiest way to deploy **Eleviro** so others can use it.

## Recommended Platform: Render.com

We recommend **Render** because it is:
*   **Easy to use**: Connects directly to your GitHub repository.
*   **Cost-effective**: Has a generous free tier for web services.
*   **Zero-config**: Can automatically detect the `Dockerfile` we just added.

## Step 1: Push Code to GitHub

Ensure your latest code (including the new `Dockerfile`) is pushed to GitHub.

## Step 2: Deploy on Render

1.  **Sign Up/Login**: Go to [dashboard.render.com](https://dashboard.render.com/) and log in.
2.  **New Web Service**: Click **New +** > **Web Service**.
3.  **Connect Repo**: Select your `eleviro` repository from the list.
4.  **Configure**:
    *   **Name**: `eleviro` (or your preferred name)
    *   **Region**: Choose the one closest to you (e.g., Oregon, Frankfurt).
    *   **Runtime**: Select **Docker** (It should be auto-selected because of the `Dockerfile`).
    *   **Instance Type**: **Free** (for hobby use) or **Starter** ($7/mo) for better performance/no spin-down.
5.  **Environment Variables**:
    *   Scroll down to the "Environment Variables" section.
    *   Add Key: `OPENAI_API_KEY`
    *   Add Value: Paste your actual OpenAI API key (from your `.env` file).
6.  **Deploy**: Click **Create Web Service**.

## Step 3: Verify

Render will start building your app using the Dockerfile. It usually takes 2-3 minutes.
Once finished, you will see a green "Live" badge and a URL (e.g., `https://eleviro.onrender.com`).
Click the URL to open your live app!

## Alternative: Railway.app

**Railway** is another excellent choice if you prefer it.
1.  Go to **Railway.app**.
2.  "Start a New Project" > "Deploy from GitHub repo".
3.  Select your repo.
4.  Add the `OPENAI_API_KEY` in the specific "Variables" tab.
5.  It will automatically detect the Dockerfile and deploy.
