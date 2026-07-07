import uvicorn
import os
os.makedirs("logs", exist_ok=True)
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
