const taskContainer = document.getElementById('taskContainer');
const TTSStatus = document.getElementById('TTSStatus');
const bookStatus = document.getElementById('bookStatus');
let tasks = new Map();

function addNewTask(taskId, type) {
    const taskElement = document.createElement('div');
    taskElement.className = 'task-item';
    taskElement.id = `task-${taskId}`;
    taskElement.innerHTML = `
        <div>
            <span>${type}任务ID: ${taskId}</span>
            <span class="task-status status-processing">处理中</span>
        </div>
        <div class="task-progress"></div>
        <div class="task-actions"></div>
    `;
    taskContainer.prepend(taskElement);
    tasks.set(taskId, taskElement);
}

// async function updateTaskStatus(taskId, taskType) {
//     const apiUrlMap = {
//         TTS: `/api/tts/${taskId}`,
//         BOOK: `/api/book_task/${taskId}`
//     };

//     try {
//         const response = await fetch(apiUrlMap[taskType]);
//         if (!response.ok) throw new Error('状态查询失败');

//         const data = await response.json();
//         const taskElement = tasks.get(taskId);
//         if (!taskElement) return;

//         const statusElement = taskElement.querySelector('.task-status');
//         const progressElement = taskElement.querySelector('.task-progress');
//         const actionsElement = taskElement.querySelector('.task-actions');

//         statusElement.className = `task-status status-${data.status}`;
//         statusElement.textContent = {
//             pending: '等待模型加载...',
//             processing: '处理中...',
//             completed: '已完成',
//             failed: '失败'
//         }[data.status];

//         if (data.status === 'processing') {
//             progressElement.className = `task-progress status-${data.status}`;
//             progressElement.textContent = `${data.progress}`;
//         }

//         if (taskType === 'TTS') {
//             TTSStatus.innerHTML = `<div>${data.chunk}</div>`;
//         } else if (taskType === 'BOOK') {
//             if(data.logs && data.logs.length > 0) {
//                 // 获取最新的日志信息（即列表中的最后一个元素）
//                 const latestLog = data.logs[data.logs.length - 1];
//                 // 更新bookStatusElement以仅显示最新的日志信息
//                 bookStatus.innerHTML = `<div>${latestLog}</div>`;
//             }
//         }

//         if (data.status === 'completed') {
//             progressElement.textContent = '';
//             if (taskType === 'TTS') {
//                 actionsElement.innerHTML = `
//                     <a href="/${data.result.audio_path}" 
//                        class="download-link"
//                        download>
//                         下载音频
//                     </a>
//                 `;
//                 TTSStatus.innerHTML = ``;
//             } else if (taskType === 'BOOK') {
//                 document.getElementById('content').value = data.result.ai_answer;
//                 actionsElement.innerHTML = `
//                     <a href="/${data.result.answer_path}" 
//                        class="download-link"
//                        download>
//                         下载笔记
//                     </a>
//                 `;
//                 bookStatus.innerHTML = ``;
//             }
//             return true;
//         }

//         if (data.status === 'failed') {
//             actionsElement.textContent = `错误: ${data.error}`;
//             return true;
//         }

//         return false;

//     } catch (error) {
//         console.error('状态更新失败:', error);
//         return true;
//     }
// }

// function startPolling(taskId, taskType) {
//     const interval = setInterval(async () => {
//         const shouldStop = await updateTaskStatus(taskId, taskType);
//         if (shouldStop) clearInterval(interval);
//     }, 2000);
// }

function startSSE(taskId, taskType) {
    const apiUrlMap = {
        TTS: `/api/tts_sse/${taskId}`,
        BOOK: `/api/book_sse/${taskId}`
    };

    const eventSource = new EventSource(apiUrlMap[taskType]);

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        const taskElement = tasks.get(taskId);
        if (!taskElement) return;
        updateTaskUI(taskElement, data, taskType);
        
        if(data.status === 'completed' || data.status === 'failed') {
            eventSource.close(); // 如果任务完成或失败，则关闭连接
        }
    };

    eventSource.onerror = function(error) {
        console.error('SSE error:', error);
        eventSource.close();
    };
}

function updateTaskUI(taskElement, data, taskType) {
        const statusElement = taskElement.querySelector('.task-status');
        const progressElement = taskElement.querySelector('.task-progress');
        const actionsElement = taskElement.querySelector('.task-actions');

        statusElement.className = `task-status status-${data.status}`;
        statusElement.textContent = {
            pending: '等待模型加载...',
            processing: '处理中...',
            completed: '已完成',
            failed: '失败'
        }[data.status];

        if (data.status === 'processing') {
            progressElement.className = `task-progress status-${data.status}`;
            progressElement.textContent = `${data.progress}`;
        }

        if (taskType === 'TTS') {
            TTSStatus.innerHTML = `<div>${data.chunk}</div>`;
        } else if (taskType === 'BOOK') {
            if(data.logs && data.logs.length > 0) {
                // 获取最新的日志信息（即列表中的最后一个元素）
                const latestLog = data.logs[data.logs.length - 1];
                // 更新bookStatusElement以仅显示最新的日志信息
                bookStatus.innerHTML = `<div>${latestLog}</div>`;
            }
        }

        if (data.status === 'completed') {
            progressElement.textContent = '';
            if (taskType === 'TTS') {
                actionsElement.innerHTML = `
                    <a href="/${data.result.audio_path}" 
                       class="download-link"
                       download>
                        下载音频
                    </a>
                `;
                TTSStatus.innerHTML = ``;
            } else if (taskType === 'BOOK') {
                document.getElementById('content').value = data.result.ai_answer;
                actionsElement.innerHTML = `
                    <a href="/${data.result.answer_path}" 
                       class="download-link"
                       download>
                        下载笔记
                    </a>
                `;
                bookStatus.innerHTML = ``;
            }
            return true;
        }

        if (data.status === 'failed') {
            actionsElement.textContent = `错误: ${data.error}`;
            return true;
        }
}

document.addEventListener('DOMContentLoaded', () => {
    
    const form = document.getElementById('ttsForm');
    const ttsModelSelect = document.getElementById('TTSmodelSelect');
    const maskgctPrompt = document.getElementById('maskgct-tts-prompt');
    const maskgctParams = document.getElementById('maskgct-tts-params');
    const cosyvoiceElement = document.getElementById('cosyvoice-tts');

    if (!ttsModelSelect || !maskgctPrompt || !maskgctParams || !cosyvoiceElement) {
        console.error('Required elements not found:', {
            ttsModelSelect: !!ttsModelSelect,
            maskgctPrompt: !!maskgctPrompt,
            maskgctParams: !!maskgctParams,
            cosyvoiceElement: !!cosyvoiceElement
        });
        return;
    }

    // 初始化时隐藏所有 maskgct-tts 元素
    maskgctPrompt.style.display = 'none';
    maskgctParams.style.display = 'none';

    // 添加 TTS 模型选择事件监听器
    ttsModelSelect.addEventListener('change', () => {
        const selectedModel = ttsModelSelect.value;
        
        if (selectedModel === 'maskgct') {
            maskgctPrompt.style.display = 'flex';  // 改为 flex 以保持 form-group 的样式
            maskgctParams.style.display = 'grid';  // 改为 grid 以保持 form-row 的样式
            cosyvoiceElement.style.display = 'none';
        } else {
            maskgctPrompt.style.display = 'none';
            maskgctParams.style.display = 'none';
            cosyvoiceElement.style.display = 'flex'; // 改为flex以保持标签和选择框的水平排列
        }
    });

    // 触发一次 change 事件以设置初始状态
    ttsModelSelect.dispatchEvent(new Event('change'));

    // 添加音色试听功能
    const previewVoiceBtn = document.getElementById('previewVoiceBtn');
    const voicePreview = document.getElementById('voicePreview');
    const voiceSelect = document.getElementById('voice_name');
    let currentSampleUrl = null;
    
    if (previewVoiceBtn && voicePreview && voiceSelect) {
        // 当选择音色变化时预加载示例音频
        voiceSelect.addEventListener('change', async () => {
            const selectedVoice = voiceSelect.value;
            previewVoiceBtn.textContent = '加载中...';
            previewVoiceBtn.disabled = true;
            
            try {
                // 预先获取示例音频URL
                const response = await fetch(`/api/voice_sample/${selectedVoice}`);
                const data = await response.json();
                
                if (data.sample_url) {
                    currentSampleUrl = data.sample_url;
                    previewVoiceBtn.disabled = false;
                    previewVoiceBtn.textContent = '试听';
                    console.log(`已加载音频: ${currentSampleUrl}`);
                } else {
                    throw new Error(data.error || '示例音频不存在');
                }
            } catch (error) {
                console.error(`音频加载错误: ${error.message}`);
                previewVoiceBtn.textContent = '无示例';
                previewVoiceBtn.disabled = true;
                currentSampleUrl = null;
            }
        });

        previewVoiceBtn.addEventListener('click', async () => {
            if (voicePreview.getAttribute('data-playing') === 'true') {
                // 如果正在播放，则停止播放
                voicePreview.pause();
                voicePreview.currentTime = 0;
                voicePreview.setAttribute('data-playing', 'false');
                previewVoiceBtn.textContent = '试听';
                previewVoiceBtn.classList.remove('playing');
                return;
            }
            
            if (!currentSampleUrl) {
                console.error('没有可用的示例音频');
                return;
            }
            
            try {
                // 播放音频
                voicePreview.src = currentSampleUrl;
                voicePreview.setAttribute('data-playing', 'true');
                previewVoiceBtn.classList.add('playing');
                previewVoiceBtn.textContent = '停止';
                
                // 添加加载事件
                voicePreview.onloadeddata = function() {
                    console.log('音频已加载完成，开始播放');
                };
                
                // 添加错误事件
                voicePreview.onerror = function(e) {
                    console.error('音频加载失败', e);
                    alert('音频播放失败，请稍后重试');
                    voicePreview.setAttribute('data-playing', 'false');
                    previewVoiceBtn.textContent = '试听';
                    previewVoiceBtn.classList.remove('playing');
                };
                
                await voicePreview.play();
                
                // 监听音频播放结束事件
                voicePreview.onended = function() {
                    voicePreview.setAttribute('data-playing', 'false');
                    previewVoiceBtn.textContent = '试听';
                    previewVoiceBtn.classList.remove('playing');
                };
                
            } catch (error) {
                console.error(`音频播放错误: ${error.message}`);
                alert(`播放失败: ${error.message}`);
                voicePreview.setAttribute('data-playing', 'false');
                previewVoiceBtn.textContent = '试听';
                previewVoiceBtn.classList.remove('playing');
            }
        });
        
        // 初始加载当前选中的音色示例
        voiceSelect.dispatchEvent(new Event('change'));
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');

        try {
            // 构建FormData对象
            const formData = new FormData();
            const selectedModel = ttsModelSelect.value;
            const content = document.getElementById('content').value;
            
            // 检查内容是否为空
            if (!content.trim()) {
                throw new Error('请输入需要合成的文本内容');
            }
            
            formData.append('content', content);
            formData.append('slice_length', document.getElementById('slice_length').value);
            formData.append('model_type', selectedModel);
            
            if (selectedModel === 'maskgct') {
                // MaskGCT-TTS 需要参考音频和其他参数
                formData.append('target_len', document.getElementById('targetLen').value);
                formData.append('n_timesteps', document.getElementById('nTimesteps').value);
                
                const fileInput = document.getElementById('promptFile');
                const pathInput = document.getElementById('promptPath');

                if (fileInput.files.length > 0) {
                    formData.append('prompt_file', fileInput.files[0]);
                } else if (pathInput.value) {
                    formData.append('prompt_wav_path', pathInput.value);
                } else {
                    throw new Error('请提供参考音频');
                }
            } else {
                // CosyVoice 需要选择音色
                const voiceName = document.getElementById('voice_name').value;
                if (!voiceName) {
                    throw new Error('请选择音色');
                }
                formData.append('voice_name', voiceName);
            }

            const response = await fetch('/api/tts', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('请求失败');
            
            const data = await response.json();
            addNewTask(data.task_id, 'TTS');
            startSSE(data.task_id, 'TTS');

        } catch (error) {
            alert(`错误: ${error.message}`);
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });

    // 文件选择时自动填充路径输入框
    document.getElementById('promptFile').addEventListener('change', (e) => {
        const pathInput = document.getElementById('promptPath');
        if (e.target.files.length > 0) {
            pathInput.disabled = true;
            pathInput.value = ''; // 清空之前的值
            pathInput.placeholder = "已选择文件上传";
        } else {
            pathInput.disabled = false;
            pathInput.placeholder = "或输入已有路径";
        }
    });

    document.getElementById('bookFile').addEventListener('change', (e) => {
        const pathInput = document.getElementById('bookPath');
        if (e.target.files.length > 0) {
            pathInput.disabled = true;
            pathInput.value = ''; // 清空之前的值
            pathInput.placeholder = "已选择文件上传";
        } else {
            pathInput.disabled = false;
            pathInput.placeholder = "或输入已有路径";
        }
    });

    lanPrompt();
    // 初始化本地模型
    loadModelOptions();
    // 加载音频和书籍文件列表
    fetchDefaultFiles('audio', 'promptPath', 'audioList');
    fetchDefaultFiles('book', 'bookPath', 'bookList');
    // 初始化音频和书籍的选择器
    initDropdown('promptPath', 'audioList');
    initDropdown('bookPath', 'bookList');
    
});

// 根据类型获取默认文件列表并填充下拉菜单
function fetchDefaultFiles(type, pathId, listId) {
    const promptPath = document.getElementById(pathId);
    const fileList = document.getElementById(listId);
    fileList.innerHTML = '';

    fetch(`/api/defaultFiles/${type}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
    })
    .then(response => response.json())
    .then(data => {
            data.files.forEach(file => {
                let option = document.createElement('li');
                option.textContent = file;
                option.onclick = function() {
                    promptPath.value = './uploads/default/' + file;
                    fileList.style.display = 'none';
                };
                fileList.appendChild(option);
            });
        })
        .catch(error => console.error('Error fetching default files:', error));
}

// 下拉选择默认文件
function initDropdown(pathId, listId) {
    const pathElement = document.getElementById(pathId);
    pathElement.addEventListener('focus', () => {
        const listElement = document.getElementById(listId);
        listElement.style.display = 'block';
    });

    window.addEventListener('click', function(event) {
        const listElement = document.getElementById(listId);
        if (!event.target.closest(`#${pathId}`)) {
            listElement.style.display = 'none';
        }
    });
}

// 加载本地模型
function loadModelOptions() {
    fetch('/api/getmodels')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            const selectElement = document.getElementById('modelSelect');
            data.local_models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                selectElement.appendChild(option);
            });
        })
        .catch(error => console.error('Error fetching models:', error));
}

// 新增书籍处理逻辑
async function processBook() {
    const fileInput = document.getElementById('bookFile');
    const bookPath = document.getElementById('bookPath');
    const question = document.getElementById('question');
    const modelName = document.getElementById('modelSelect');
    const maxLength = document.getElementById('max-length');
    const timeOut = document.getElementById('timeout');
    const multiThread = document.getElementById('multi_thread');

    const hasFile = fileInput.files.length > 0;
    const hasPath = bookPath.value.trim() !== '';

    if (!hasFile && !hasPath) {
        alert('请选择电子书文件或填写书籍路径');
        return;
    }

    let maxLengthValue = parseInt(maxLength.value.trim(), 10);
    if (isNaN(maxLengthValue)) {
        alert('请输入有效的最大长度（必须是整数）');
        return;
    } else if (maxLengthValue > 50000) {
        alert('最大长度不能超过50000');
        maxLength.value = 50000;
        return;
    }

    const formData = new FormData();

    if (hasFile) {
        formData.append('book_file', fileInput.files[0]);
    }

    formData.append('book_path', bookPath.value.trim());
    formData.append('question', question.value.trim());
    formData.append('model_name', modelName.value.trim());
    formData.append('max_length', maxLengthValue);
    formData.append('timeout', timeOut.value.trim());
    formData.append('multi_thread', multiThread.checked ? 'True' : 'False');

    try {
        const response = await fetch('/api/read_book', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        addNewTask(data.task_id, 'BOOK');  // 添加新任务到任务列表
        startSSE(data.task_id, 'BOOK');  // 开启SSE
    } catch (error) {
        console.error('Error:', error);
    }
}

async function lanPrompt() {
    fetch('/lan-content')
    .then(response => response.json())
    .then(data => {
        const lanPrompt = document.getElementById('lan-prompt');
        lanPrompt.innerHTML = data.content;
    })
    .catch(error => console.error('Error fetching lan content:', error));
}