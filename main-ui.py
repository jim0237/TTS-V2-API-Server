from typing import Dict
from datetime import datetime
from contextlib import asynccontextmanager
import io
import os
from pathlib import Path

import torch
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from huggingface_hub import hf_hub_download

# OpenAI API compatibility types
class AudioModel(str):
    tts_1 = "tts-1"
    tts_1_hd = "tts-1-hd"

class AudioResponseFormat(str):
    wav = "wav"  # We only support WAV for now

class AudioSpeechRequest(BaseModel):
    model: str = Field(default=AudioModel.tts_1)
    input: str = Field(..., description="The text to generate audio for")
    voice: str = Field(..., description="The voice to use")
    response_format: str = Field(default=AudioResponseFormat.wav)
    speed: float = Field(default=1.0, ge=0.25, le=4.0)

# Voice mapping
OPENAI_VOICE_MAP = {
    "alloy": "am_adam",      # Neutral male
    "echo": "af_nicole",     # Soft female
    "fable": "bf_emma",      # British female
    "onyx": "bm_george",     # Deep male
    "nova": "af_bella",      # Energetic female
    "shimmer": "af_sarah"    # Clear female
}

# Global state
model = None
pipeline = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the model and pipeline on server startup."""
    global model, pipeline
    try:
        # Import here to ensure files are downloaded
        from kokoro import KModel, KPipeline
        
        # Load model
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = KModel().to(device)
        state_dict = torch.load('kokoro-v1_0.pth', map_location=device)
        
        # Convert state dict to flattened format
        flattened_state_dict = {}
        for component in ['bert', 'bert_encoder', 'predictor', 'decoder', 'text_encoder']:
            if component in state_dict:
                for key, value in state_dict[component].items():
                    if key.startswith('module.'):
                        key = key[7:]  # Remove 'module.' prefix
                    flattened_state_dict[f"{component}.{key}"] = value
        
        model.load_state_dict(flattened_state_dict)
        model.eval()
        pipeline = KPipeline('a', model)  # 'a' for American English
        print("Model loaded successfully")
                
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load TTS model")
    
    yield
    
    # Cleanup
    model = None
    pipeline = None

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
templates = Jinja2Templates(directory="templates")

# Voice descriptions
VOICE_DESCRIPTIONS = {
    'af_bella': 'American Female - Bella',
    'af_sarah': 'American Female - Sarah',
    'am_adam': 'American Male - Adam',
    'am_michael': 'American Male - Michael',
    'bf_emma': 'British Female - Emma',
    'bf_isabella': 'British Female - Isabella',
    'bm_george': 'British Male - George',
    'bm_lewis': 'British Male - Lewis',
    'af_nicole': 'American Female - Nicole (ASMR voice)'
}

@app.get("/", response_class=HTMLResponse)
async def web_interface(request: Request):
    """Serve the web interface."""
    voices = [
        {
            "id": voice_id,
            "metadata": {
                "description": desc,
                "language": "American English" if voice_id.startswith('a') else "British English",
                "gender": "Female" if voice_id.endswith(('f', 'bella', 'sarah', 'emma', 'isabella', 'nicole'))
                         else "Male" if voice_id.endswith(('adam', 'michael', 'george', 'lewis'))
                         else "Mixed"
            }
        }
        for voice_id, desc in VOICE_DESCRIPTIONS.items()
    ]
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "voices": voices}
    )

@app.post("/tts")
async def text_to_speech(text: str, voice: str = 'af_bella') -> StreamingResponse:
    """Generate speech from text."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    if voice not in VOICE_DESCRIPTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Voice '{voice}' not found. Available voices: {list(VOICE_DESCRIPTIONS.keys())}"
        )
    
    try:
        print(f"Generating speech for text: {text} with voice: {voice}")
        temp_file = Path("temp.wav")
        
        # Generate audio using pipeline's generator pattern
        for i, (gs, ps, audio) in enumerate(pipeline(text, voice=voice, speed=1)):
            print(f"Generated chunk {i}: {gs}")
            sf.write(temp_file, audio.detach().cpu().numpy(), 24000)
        
        # Read and return audio
        with open(temp_file, 'rb') as f:
            audio_data = f.read()
        temp_file.unlink()
        
        return StreamingResponse(io.BytesIO(audio_data), media_type="audio/wav")
    
    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

@app.post("/v1/audio/speech")
async def create_speech(request: AudioSpeechRequest):
    """OpenAI-compatible endpoint to generate speech from text."""
    if not model:
        raise HTTPException(status_code=500, detail="Model not initialized")
    
    # Map OpenAI voice to internal voice
    internal_voice = OPENAI_VOICE_MAP.get(request.voice)
    if not internal_voice:
        raise HTTPException(
            status_code=400,
            detail=f"Voice '{request.voice}' not found. Available voices: {list(OPENAI_VOICE_MAP.keys())}"
        )
    
    try:
        print(f"Generating speech for text: {request.input} with voice: {internal_voice}")
        temp_file = Path("temp.wav")
        
        # Generate audio using pipeline's generator pattern
        for i, (gs, ps, audio) in enumerate(pipeline(
            request.input,
            voice=internal_voice,
            speed=request.speed
        )):
            print(f"Generated chunk {i}: {gs}")
            sf.write(temp_file, audio.detach().cpu().numpy(), 24000)
        
        # Read and return audio
        with open(temp_file, 'rb') as f:
            audio_data = f.read()
        temp_file.unlink()
        
        headers = {
            "Content-Disposition": f'attachment; filename="speech.{request.response_format}"'
        }
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers=headers
        )
    
    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Speech generation failed: {str(e)}")

@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible endpoint to list available models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "tts-1",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "kokoro",
                "permission": [],
                "root": "tts-1",
                "parent": None
            },
            {
                "id": "tts-1-hd",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "kokoro",
                "permission": [],
                "root": "tts-1-hd",
                "parent": None
            }
        ]
    }

if __name__ == "__main__":
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
    server = uvicorn.Server(config)
    server.run()
