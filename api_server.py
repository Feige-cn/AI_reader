from fastapi import FastAPI, HTTPException, status, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import threading
from typing import Dict, Any, Optional
import os
import sys
import shutil
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
    model_type: str
    slice_length: int
    output_dir: str = "output"
    # MaskGCT specific parameters
    prompt_wav_path: Optional[str] = None
    target_len: Optional[int] = None
    n_timesteps: Optional[int] = None
    # CosyVoice specific parameters
    voice_name: Optional[str] = None
    use_v2: Optional[bool] = False

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

def cleanup_temp():
    tmp = './temp'
    if os.path.exists(tmp):
        for name in os.listdir(tmp):
            if name == "jieba.cache":
                continue
            path = os.path.join(tmp,name)
            delete = os.remove if os.path.isfile(path) else shutil.rmtree
            try:
                delete(path)
            except Exception as e:
                pass

def process_tts_task(task_id: str, request: TTSRequest):
    try:
        
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

        if request.model_type == "maskgct":
            from Maskgct.models.tts.maskgct.maskgct_inference import maskgct_inference_pipeline
            if not request.prompt_wav_path:
                raise ValueError("MaskGCT模型需要提供参考音频")
            
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

        elif request.model_type == "cosyvoice":
            from cosyvoice import CosyVoiceSynthesizer
            
            if not request.voice_name:
                raise ValueError("CosyVoice模型需要提供音色名称")
            
            # 初始化语音合成器
            synthesizer = CosyVoiceSynthesizer()
            
            # 获取音色的真实名称（处理中文名称）
            voice_name = request.voice_name
            voice_code = None
            for name, code in synthesizer.AVAILABLE_VOICES.items():
                if code == request.voice_name:
                    voice_name = name
                    voice_code = code
                    break
            
            if not voice_code:
                voice_code = voice_name
            
            print(f"使用音色: {voice_name} (代码: {voice_code}, 使用V2: {request.use_v2})")
            
            # 确认v2版本支持情况
            if request.use_v2 and voice_code not in synthesizer.V2_VOICES:
                print(f"警告: 音色 {voice_name} 不支持V2版本，将使用V1版本")
            
            # 处理每个文本分块
            for i, chunk in enumerate(content_chunks):
                print(f"处理第 {i+1}/{total_chunks} 个文本块，使用音色: {voice_name}")

                with task_lock:
                    task_store[task_id].update({
                        "progress": f"{i+1}/{total_chunks}",
                        "chunk": f"{chunk}"
                    })
                
                chunk_filename = os.path.join(output_dir, f'chunk_{i}.wav')
                try:
                    # 对每个分块使用同步合成方式
                    success = synthesizer.synthesize(
                        text=chunk,
                        output_file=chunk_filename,
                        voice_name=voice_name,
                        use_v2=request.use_v2
                    )
                    
                    if success:
                        print(f"音频合成成功: {chunk_filename}")
                        audio_files.append(chunk_filename)
                    else:
                        _log = f"处理第 {i+1} 个段落失败: API返回失败"
                        print(_log)
                        callback(_log)
                        
                except Exception as e:
                    _log = f"处理第 {i+1} 个段落失败: {str(e)}"
                    print(_log)
                    callback(_log)
                    continue

        else:
            raise ValueError(f"不支持的语音模型类型: {request.model_type}")

        # 只有当音频文件列表不为空时才进行合并
        if audio_files:
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
            finally:        # 清理临时文件
                cleanup_temp()
                # if os.path.exists(ffmpeg_file_list_path):
                #     os.remove(ffmpeg_file_list_path)
                # for audio_file in audio_files:
                #     if os.path.exists(audio_file):
                #         os.remove(audio_file)

            with task_lock:
                task_store[task_id].update({
                    "status": "completed",
                    "result": {
                        "audio_path": final_audio_path,
                        "output_dir": os.path.join(request.output_dir, dir_name)
                    }
                })
        else:
            with task_lock:
                task_store[task_id].update({
                    "status": "failed",
                    "error": "没有生成任何有效的音频文件"
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

def convert_to_wav(input_path: str, output_path: str = None) -> str:
    """
    将音频文件转换为WAV格式
    Args:
        input_path: 输入音频文件路径
        output_path: 输出WAV文件路径，如果为None则使用输入路径的目录和文件名，仅改变扩展名
    Returns:
        转换后的WAV文件路径
    Raises:
        subprocess.CalledProcessError: 转换失败时抛出
    """
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + ".wav"
    
    ffmpeg_path = os.path.join('resources', 'ffmpeg.exe')
    subprocess.run([
        ffmpeg_path, "-y", "-i", input_path,
        "-acodec", "pcm_s16le", "-ar", "24000", "-ac", "1",
        output_path
    ], check=True)
    
    return output_path

@app.post("/api/tts")
async def create_tts_task(
    content: str = Form(...),
    model_type: str = Form(...),
    slice_length: int = Form(...),
    prompt_file: UploadFile = File(None),
    prompt_wav_path: str = Form(None),
    target_len: int = Form(None),
    n_timesteps: int = Form(None),
    voice_name: str = Form(None),
    use_v2: bool = Form(False)
):
    # 文件处理逻辑
    final_prompt_path = None
    
    # 优先使用上传文件
    if prompt_file:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, prompt_file.filename)
        
        try:
            contents = await prompt_file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
            
            # 如果文件不是WAV格式，使用ffmpeg转换
            if not prompt_file.filename.lower().endswith(".wav"):
                try:
                    wav_file_path = convert_to_wav(file_path)
                    final_prompt_path = wav_file_path
                    # 删除原始文件
                    os.remove(file_path)
                except subprocess.CalledProcessError as e:
                    raise HTTPException(500, f"音频格式转换失败: {str(e)}")
            else:
                final_prompt_path = file_path
                
        except Exception as e:
            raise HTTPException(500, f"文件处理失败: {str(e)}")
            
    elif prompt_wav_path:
        if not os.path.exists(prompt_wav_path):
            raise HTTPException(404, "指定音频路径不存在")
        final_prompt_path = prompt_wav_path

    if model_type == "maskgct" and not final_prompt_path:
        raise HTTPException(400, "MaskGCT模型需要提供参考音频（文件上传或路径）")

    # 对于CosyVoice模型，检查音色是否支持v2版本，如果支持则自动设置use_v2为true
    if model_type == "cosyvoice" and voice_name:
        # 检查是否是v2版本的音色
        if voice_name.endswith("_v2"):
            # 移除_v2后缀，并设置use_v2为true
            voice_name = voice_name.replace("_v2", "")
            use_v2 = True
        elif use_v2:
            # 如果用户直接设置了use_v2，检查音色是否支持v2
            from cosyvoice import CosyVoiceSynthesizer
            v2_voices = list(CosyVoiceSynthesizer.V2_VOICES.keys())
            
            # 如果音色不支持v2，则设置use_v2为false
            if voice_name not in v2_voices:
                use_v2 = False
                print(f"音色 {voice_name} 不支持V2版本，已自动切换为V1版本")

    request_data = {
        "content": content,
        "model_type": model_type,
        "slice_length": slice_length,
        "output_dir": "output",
        "prompt_wav_path": final_prompt_path,
        "target_len": target_len,
        "n_timesteps": n_timesteps,
        "voice_name": voice_name,
        "use_v2": use_v2
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
    with open('prompts.json', 'r', encoding='utf-8') as f:
        prompts = json.load(f)
    question = prompts['PROMPTS']['Question']
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

@app.get("/api/voice_sample/{voice_code}")
async def get_voice_sample(voice_code: str):
    """获取音色示例音频URL"""
    try:
        # 如果是V2版本，直接使用V1版本的示例
        if voice_code.endswith("_v2"):
            voice_code = voice_code[:-3]
            
        # 官方CDN链接映射
        official_samples = {
            "longwan": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240830/dzkngm/%E9%BE%99%E5%A9%89.mp3",
            "longcheng": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240830/ggjwfl/%E9%BE%99%E6%A9%99.wav",
            "longhua": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240830/jpjtvy/%E9%BE%99%E5%8D%8E.wav",
            "longxiaochun": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/rlfvcd/%E9%BE%99%E5%B0%8F%E6%B7%B3.mp3",
            "longxiaoxia": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/wzywtu/%E9%BE%99%E5%B0%8F%E5%A4%8F.mp3",
            "longxiaocheng": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/xrqksx/%E9%BE%99%E5%B0%8F%E8%AF%9A.mp3",
            "longxiaobai": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/vusvze/%E9%BE%99%E5%B0%8F%E7%99%BD.mp3",
            "longlaotie": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/pfsfir/%E9%BE%99%E8%80%81%E9%93%81.mp3",
            "longshu": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/azcerd/%E9%BE%99%E4%B9%A6.mp3",
            "longshuo": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/lcykpl/%E9%BE%99%E7%A1%95.mp3",
            "longjing": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/ozkbmb/%E9%BE%99%E5%A9%A7.mp3",
            "longmiao": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/zjnqis/%E9%BE%99%E5%A6%99.mp3",
            "longyue": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/nrkjqf/%E9%BE%99%E6%82%A6.mp3",
            "longyuan": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/xuboos/%E9%BE%99%E5%AA%9B.mp3",
            "longfei": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/bhkjjx/%E9%BE%99%E9%A3%9E.mp3",
            "longjielidou": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/dctiyg/%E9%BE%99%E6%9D%B0%E5%8A%9B%E8%B1%86.mp3",
            "longtong": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/qyqmvo/%E9%BE%99%E5%BD%A4.mp3",
            "longxiang": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/jybshd/%E9%BE%99%E7%A5%A5.mp3",
            "loongstella": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/haffms/Stella.mp3",
            "loongbella": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20240624/tguine/Bella.mp3",
        }
        
        # 检查是否有官方CDN链接
        if voice_code in official_samples:
            return {"sample_url": official_samples[voice_code]}
        
        # 如果没有找到对应的示例音频链接
        return {"error": f"未找到音色 {voice_code} 的示例音频", "sample_url": None}
    except Exception as e:
        print(f"获取示例音频失败: {str(e)}")
        return {"error": str(e), "sample_url": None}

def open_local_browser():
    webbrowser.open_new_tab("http://127.0.0.1:8000")

if __name__ == "__main__":
    check_nvidia()              # 检查驱动程序
    check_dependent()           # 检查GPU状态
    olm.main()
    threading.Timer(3, open_local_browser).start()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
