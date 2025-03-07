from fastapi import FastAPI, HTTPException, status, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import threading
from typing import Dict, Any
import os
import sys
import soundfile as sf
import subprocess
from readbooks.main import BookReaderApp
from taskcallback import TaskCallback
from ollama import Ollama
import webbrowser
from server_ip import get_lan_ip
from check_dependent import check_dependent
from check_nvidia import check_nvidia
from fastapi.responses import StreamingResponse
import asyncio
import json
import configparser

now_dir = os.getcwd()
sys.path.insert(0, now_dir)
tmp = os.path.join(now_dir, "temp")
os.makedirs(tmp, exist_ok=True)
os.environ["TEMP"] = tmp

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

olm = Ollama()

app = FastAPI()
task_store: Dict[str, Dict[str, Any]] = {}
book_task_store: Dict[str, Dict[str, Any]] = {}
task_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TTSRequest(BaseModel):
    content: str
    prompt_wav_path: str
    target_len: int
    slice_length: int
    n_timesteps: int
    output_dir: str = "output"

class BookRequest(BaseModel):
    file_path: str
    question: str
    model_name: str
    max_length: int
    timeout: int
    multi_thread: bool
    output_dir: str = "output"

def split_text(text: str, length: int = 100) -> list:
    import re
    cleaned_text = re.sub(r'[-*#]', '', text)
    cleaned_text = "\n".join([line for line in cleaned_text.split('\n') if line.strip() != ''])

    paragraphs = cleaned_text.split('\n')
    chunks = []

    for paragraph in paragraphs:
        if not paragraph.strip():  # 跳过空段落
            continue
        sentences = re.split(r'(?<=[；。！？\n])', paragraph)
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " "  # 使用空格而不是直接连接句子，以增加可读性
                current_chunk += sentence
        if current_chunk:
            chunks.append(current_chunk)
    print(f'将文本拆分为\t{len(chunks)}\t段')
    return chunks

def process_tts_task(task_id: str, request: TTSRequest):
    try:
        from models.tts.maskgct.maskgct_inference import maskgct_inference_pipeline
        
        with task_lock:
            task_store[task_id].update({
                "status": "processing",
                "logs": [],
                "progress": "0/0",
                "chunk": ""
            })

        dir_name = str(task_id)
        output_dir = os.path.join(request.output_dir, dir_name)
        os.makedirs(output_dir, exist_ok=True)

        callback = TaskCallback(
            task_id=task_id,
            task_store=book_task_store,
            lock=task_lock
        )        

        content_chunks = split_text(request.content, request.slice_length)
        total_chunks = len(content_chunks)
        audio_files = []
        for i, chunk in enumerate(content_chunks):
            print(f"Processing chunk {i+1}/{total_chunks}")

            with task_lock:
                task_store[task_id].update({
                    "progress": f"{i+1}/{total_chunks}",
                    "chunk": f"{chunk}"
                })
            chunk_filename = os.path.join(output_dir, f'chunk_{i}.wav')
            try:
                recovered_audio = maskgct_inference_pipeline.maskgct_inference(
                    request.prompt_wav_path, 
                    chunk, 
                    target_len=request.target_len, 
                    n_timesteps=request.n_timesteps
                )
                sf.write(chunk_filename, recovered_audio, 24000)
                audio_files.append(chunk_filename)
            except Exception as chunk_error:
                _log = f"处理第 {i+1} 个段落失败: {str(chunk_error)}"
                print(_log)
                callback(_log)
                continue

        try:
            ffmpeg_file_list_path = os.path.join(output_dir, 'file_list.txt')
            with open(ffmpeg_file_list_path, 'w') as f:
                for audio_file in audio_files:
                    f.write(f"file '{os.path.abspath(audio_file)}'\n")
            
            final_audio_path = os.path.join(output_dir, f'{dir_name}.wav')
            ffmpeg_path = os.path.join('resources', 'ffmpeg.exe')
            subprocess.run([
                ffmpeg_path, "-y", "-f", "concat", "-safe", "0",
                "-i", ffmpeg_file_list_path, "-c", "copy", final_audio_path
            ], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频合并失败: {str(e)}") from e
        # finally:        # 清理临时文件
        #     if os.path.exists(ffmpeg_file_list_path):
        #         os.remove(ffmpeg_file_list_path)
        #     for audio_file in audio_files:
        #         if os.path.exists(audio_file):
        #             os.remove(audio_file)

        with task_lock:
            task_store[task_id].update({
                "status": "completed",
                "result": {
                    "audio_path": final_audio_path,
                    "output_dir": os.path.join(request.output_dir, dir_name)
                }
            })

    except Exception as e:
        error_msg = f"任务处理失败: {str(e)}"
        print(f"Error in task {task_id}: {error_msg}")
        
        with task_lock:
            if task_id in task_store:  # 防止意外KeyError
                task_store[task_id].update({
                    "status": "failed",
                    "error": error_msg
                })

@app.post("/api/tts")
async def create_tts_task(
    content: str = Form(...),
    target_len: int = Form(...),
    slice_length: int = Form(...),
    n_timesteps: int = Form(...),
    prompt_file: UploadFile = File(None),
    prompt_wav_path: str = Form(None)
):
    # 文件处理逻辑
    final_prompt_path = None
    
    # 优先使用上传文件
    if prompt_file:
        if not prompt_file.filename.lower().endswith(".wav"):
            raise HTTPException(400, "只支持WAV格式音频")
        
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{uuid.uuid4()}.wav")
        
        try:
            contents = await prompt_file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
            final_prompt_path = file_path
        except Exception as e:
            raise HTTPException(500, f"文件保存失败: {str(e)}")
            
    elif prompt_wav_path:
        if not os.path.exists(prompt_wav_path):
            raise HTTPException(404, "指定音频路径不存在")
        final_prompt_path = prompt_wav_path
        
    if prompt_file and prompt_wav_path:
        # 优先使用上传文件
        final_prompt_path = file_path

    if not final_prompt_path:
        raise HTTPException(400, "必须提供参考音频（文件上传或路径）")

    request_data = {
        "content": content,
        "prompt_wav_path": final_prompt_path,
        "target_len": target_len,
        "slice_length": slice_length,
        "n_timesteps": n_timesteps,
        "output_dir": "output"
    }
    
    try:
        validated_request = TTSRequest(**request_data)
    except Exception as e:
        raise HTTPException(422, str(e))
    
    task_id = str(uuid.uuid4())
    
    with task_lock:
        task_store[task_id] = {
            "status": "pending",
            "request": validated_request.model_dump(),
            "result": None,
            "error": None
        }

    threading.Thread(
        target=process_tts_task,
        args=(task_id, validated_request)
    ).start()
    
    return {"task_id": task_id, "status_url": f"/api/tts/{task_id}"}

@app.get("/api/tts_sse/{task_id}")
async def tts_sse_endpoint(task_id: str, request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            with task_lock:
                task = task_store.get(task_id)
            
            if not task:
                yield "data: {\"error\": \"Task not found\"}\n\n"
                break
            
            response = {
                "task_id": task_id,
                "status": task["status"],
                "progress": task.get("progress", "0/0"),
                "chunk": task.get("chunk", ""),
                "result": None,
                "error": None
            }
            
            if task["status"] == "completed":
                response["result"] = task["result"]
            elif task["status"] == "failed":
                response["error"] = task["error"]
            
            yield f"data: {json.dumps(response)}\n\n"
            
            if task["status"] in ["completed", "failed"]:
                break
                        
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")



app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.mount("/output", StaticFiles(directory="output"), name="output")

@app.get("/")
async def read_root(request: Request):
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    question = config['PROMPTS']['Question']
    return templates.TemplateResponse("index.html", {"request": request, "question": question})

@app.post("/api/upload")
async def upload_prompt(file: UploadFile):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"filename": file.filename, "path": file_path}

def process_book_task(task_id: str, request: BookRequest):
    try:
        with task_lock:
            book_task_store[task_id] = {
                "status": "processing",
                "logs": [],
                "progress": "",
                "result": None,
                "error": None
            }

        dir_name = str(task_id)
        os.makedirs(os.path.join(request.output_dir, dir_name), exist_ok=True)

        callback = TaskCallback(
            task_id=task_id,
            task_store=book_task_store,
            lock=task_lock
        )        
        book_reader_app = BookReaderApp(
            task_id=task_id,
            book_path=request.file_path,
            question=request.question,
            model_name=request.model_name,
            max_length=request.max_length,
            timeout=request.timeout,
            multi_thread=request.multi_thread,
            callback=callback)

        # 调用书籍处理逻辑
        book_content_list = book_reader_app.process_book()
        ai_answer = book_reader_app.interact_with_ai(book_content_list)

        answer_path = os.path.join(request.output_dir, dir_name, f'{dir_name}.txt')
        with open(answer_path, 'w', encoding='utf-8') as file:
            file.write(ai_answer)

        with task_lock:
            book_task_store[task_id].update({
                "status": "completed",
                "result": {
                    "ai_answer": ai_answer,
                    "filename": os.path.basename(request.file_path),
                    "answer_path": answer_path
                }
            })

    except Exception as e:
        with task_lock:
            book_task_store[task_id].update({
                "status": "failed",
                "error": str(e)
            })

# 上传电子书
@app.post("/api/read_book")
async def read_book(
    book_file: UploadFile = File(None),
    book_path: str = Form(None),
    question: str = Form(...),
    model_name: str = Form(...),
    max_length: int = Form(...),
    timeout: int = Form(None),
    multi_thread: bool = Form(False)
    ):

    if not book_file and not book_path:
        raise HTTPException(400, "请选择电子书文件或填写书籍路径")
    
    use_file = book_file is not None
    
    if use_file:
        if not book_file.filename.lower().endswith(('.mobi', '.epub', '.pdf', '.txt')):
            raise HTTPException(400, "仅支持MOBI/EPUB/PDF/TXT格式")
        
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        file_name = book_file.filename        
        file_path = os.path.join(upload_dir, book_file.filename)

        with open(file_path, "wb") as f:
            content = await book_file.read()
            f.write(content)
    else:
        file_path = book_path
        if not os.path.exists(book_path) or not any(book_path.lower().endswith(ext) for ext in ('.mobi', '.epub', '.pdf', '.txt')):
            raise HTTPException(400, "提供的书籍路径无效或格式不受支持")
        file_name = os.path.basename(book_path)

    request_data = {
        "file_path": file_path,
        "question": question,
        "model_name": model_name,
        "max_length": max_length,
        "timeout": timeout,
        "multi_thread": multi_thread
    }
 
    try:
        validated_request = BookRequest(**request_data)
    except Exception as e:
        print(f"Validation error: {str(e)}")
        raise HTTPException(422, str(e))

    task_id = str(uuid.uuid4())
    
    with task_lock:
        book_task_store[task_id] = {
            "status": "pending",
            "filename": file_name,
            "filepath": file_path,
            "result": None,
            "error": None
        }
    
    threading.Thread(
        target=process_book_task,
        args=(task_id, validated_request)
    ).start()
    
    return {"task_id": task_id, "status_url": f"/api/book_task/{task_id}"}

@app.get("/api/book_sse/{task_id}")
async def book_sse_endpoint(task_id: str, request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            with task_lock:
                task = book_task_store.get(task_id)
            
            if not task:
                yield "data: {\"error\": \"Task not found\"}\n\n"
                break
            
            response = {
                "task_id": task_id,
                "status": task["status"],
                "logs": task.get("logs", []),
                "progress": task.get("progress", ""),
                "result": None,
                "error": None
            }
            
            if task["status"] == "completed":
                response["result"] = task["result"]
            elif task["status"] == "failed":
                response["error"] = task["error"]
            
            yield f"data: {json.dumps(response)}\n\n"
            
            if task["status"] in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

def get_default_files_fun(type, directory: str = "./uploads/default"):
    default_files = []
    if type == 'audio':
        valid_extensions = ('.mp3', '.wav')
    elif type == 'book':
        valid_extensions = ('.epub', '.mobi', '.pdf', '.txt')
    else:
        return default_files
    
    for filename in os.listdir(directory):
        if filename.endswith(valid_extensions):
            default_files.append(filename)
    
    return default_files

@app.post("/api/defaultFiles/{type}")
async def get_default_files(type: str):
    files = get_default_files_fun(type)

    if not files:
        raise HTTPException(status_code=404, detail="No files found or invalid type")

    return {"files": files}

@app.get("/api/getmodels")
async def local_models():
    models_list = olm.get_ollama_models()
    if not models_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No models found")
    models_name_list = [model['name'] for model in models_list]
    return {"local_models": models_name_list}

@app.get("/lan-content")
async def get_lan_content():
    ips = get_lan_ip()
    if ips:
        urls = [f'http://{ip}:8000' for ip in ips]
        links = [f"<a href='{url}'>{url}</a>" for url in urls]
        content = f"<p>局域网内其他用户可以通过浏览器访问{'或'.join(links)}使用本系统</p>"
        return {"content": content}
    else:
        content = f"<p>设备未联网，仅可本地运行。</p>"
        return {"content": content}

def open_local_browser():
    webbrowser.open_new_tab("http://127.0.0.1:8000")

if __name__ == "__main__":
    check_nvidia()              # 检查驱动程序
    check_dependent()           # 检查GPU状态
    olm.main()
    threading.Timer(3, open_local_browser).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
