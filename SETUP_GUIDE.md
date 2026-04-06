# Healoncal Setup Guide

## ✅ Setup Complete!

Your Healoncal project has been successfully set up and is running locally.

## What Was Done

1. ✅ **Virtual Environment Created**: `venv/` directory with Python 3.12.3
2. ✅ **Dependencies Installed**: All packages from `requirements.txt` installed
3. ✅ **Helper Scripts Created**: `setup.sh` and `run.sh` for easy management
4. ✅ **Application Running**: Server is running on http://localhost:8000

## Current Status

- **Server**: Running on http://0.0.0.0:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/healoncal/health ✅

## Quick Start Commands

### Activate Virtual Environment
```bash
source venv/bin/activate
```

### Run the Application
```bash
# Option 1 (recommended): Use the run script – activates venv and starts the server
./run.sh

# Option 2: Manual command – you must activate the venv first (see above)
source venv/bin/activate
uvicorn app.main_healoncal:app --reload --host 0.0.0.0 --port 8000

# Option 3: Run uvicorn via the venv without activating (any shell)
./venv/bin/uvicorn app.main_healoncal:app --reload --host 0.0.0.0 --port 8000
```

### Stop the Application
Press `Ctrl+C` in the terminal where the server is running.

## Environment Variables

⚠️ **Important**: You need to configure your environment variables for full functionality.

The application will work for basic testing without credentials, but for full features you need:

1. **Supabase Credentials** (for database):
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase anon/public key
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key
   - Get these from: https://app.supabase.com

2. **Gemini API Key** (for AI recommendations):
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - Get this from: https://makersuite.google.com/app/apikey

### Setting Up Environment Variables

Since `.env` files are protected, you have two options:

**Option 1: Create .env file manually**
```bash
# Copy the example (if it exists) or create manually
cp .env.example .env  # if .env.example exists
# Then edit .env with your credentials
nano .env  # or use your preferred editor
```

**Option 2: Export in terminal**
```bash
export SUPABASE_URL="your_url_here"
export SUPABASE_KEY="your_key_here"
export SUPABASE_SERVICE_ROLE_KEY="your_service_key_here"
export GEMINI_API_KEY="your_gemini_key_here"
```

## API Endpoints

### Available Endpoints

- `GET /` - Root endpoint with API information
- `GET /api/healoncal/health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

### Main Analysis Endpoints

- `POST /api/healoncal/capture` - Capture skin images
- `POST /api/healoncal/analyze` - Analyze skin images
- `GET /api/healoncal/results/{session_id}` - Get analysis results
- `GET /api/healoncal/recommendations` - Get product recommendations
- `GET /api/healoncal/session/{user_id}/latest` - Get latest session

## Testing the API

### Test Health Endpoint
```bash
curl http://localhost:8000/api/healoncal/health
```

### Test Root Endpoint
```bash
curl http://localhost:8000/
```

### View API Documentation
Open in browser: http://localhost:8000/docs

## Project Structure

```
Healoncal/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       └── healoncal_analysis.py
│   ├── core/
│   │   ├── config.py
│   │   └── secrets.py
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── main_healoncal.py
├── venv/              # Virtual environment
├── data/              # Data storage
├── uploads/           # Uploaded images
├── requirements.txt  # Dependencies
├── setup.sh          # Setup script
└── run.sh            # Run script
```

## Troubleshooting

### "uvicorn: command not found" or exit code 127
You're running `uvicorn` in a shell where the virtualenv isn't activated. Use one of:

- **Easiest:** `./run.sh` (from project root)
- **Or:** `source venv/bin/activate` then run your `uvicorn ...` command
- **Or:** `./venv/bin/uvicorn app.main_healoncal:app --reload --host 0.0.0.0 --port 8000`

### Port Already in Use
If port 8000 is already in use, change it:
```bash
uvicorn app.main_healoncal:app --reload --host 0.0.0.0 --port 8080
```

### Virtual Environment Issues
If you need to recreate the virtual environment:
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Import Errors
Make sure you're in the project root directory and virtual environment is activated:
```bash
cd /home/kamran/Downloads/no-backup/Healoncal
source venv/bin/activate
```

## Next Steps

1. **Configure Environment Variables**: Add your Supabase and Gemini API credentials
2. **Test API Endpoints**: Use the interactive docs at http://localhost:8000/docs
3. **Set Up Database**: Follow the database guide in `HEALONCAL_API_DATABASE_GUIDE.md`
4. **Upload Test Images**: Test the skin analysis functionality

## Notes

- The application is currently running in the background
- You can access the API documentation at http://localhost:8000/docs
- The health endpoint shows the service is running and connected
- Some features may require valid API keys to function fully

## Support

For issues or questions:
- Check the main README.md for detailed documentation
- Review API documentation at /docs endpoint
- Check logs in the terminal where the server is running

