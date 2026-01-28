# P&ID Digitization Tool

A web application for digitizing Piping and Instrumentation Diagrams (P&ID) and Process Flow Diagrams (PFD) with manual annotation and AI-assisted detection.

## Features

- ✅ PDF and image upload with multi-page support
- ✅ Pan/zoom canvas viewer
- ✅ Manual bounding box annotation
- ✅ Symbol palette from legend PDFs
- ✅ Connection/edge drawing
- ✅ XML and YOLO format export
- ✅ Multi-user authentication
- 🔄 AI symbol detection (YOLOv8/AWS model) - planned

## Quick Start with Docker

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/pid-digitizer.git
cd pid-digitizer

# Start with Docker Compose
docker-compose up --build

# Access at http://localhost
```

**Default Login**: `admin` / `admin123`

## Manual Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Poppler (for PDF processing)

```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pdf2image opencv-python-headless

# Run server
PYTHONPATH=$PYTHONPATH:. uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

**URLs**:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Project Structure

```
├── backend/
│   ├── app/              # FastAPI application
│   │   ├── main.py       # App entry point
│   │   ├── models.py     # Database models
│   │   ├── auth.py       # JWT authentication
│   │   └── routers/      # API endpoints
│   └── services/         # Business logic
├── frontend/
│   └── src/
│       ├── components/   # React components
│       └── pages/        # Page views
├── Symbol library/       # Legend PDFs
└── docker-compose.yml    # Docker orchestration
```

## Usage

1. **Upload** a P&ID/PFD document
2. **Extract symbols** from your legend PDFs (click button on dashboard)
3. **Draw bounding boxes** around symbols
4. **Assign symbol types** and tag IDs
5. **Export to XML** for downstream use

## AI Model Integration (Future)

Download pretrained weights for automatic detection:

```bash
# AWS P&ID Model
wget https://github.com/aws-solutions-library-samples/guidance-for-piping-and-instrumentation-diagrams-digitization-on-aws/releases/download/v1.0.0/model.tar.gz
```

## License

MIT
