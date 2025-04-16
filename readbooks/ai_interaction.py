import os
import requests
import time
import concurrent.futures
from functools import partial
from openai import OpenAI
from readbooks.external_api import external_api
from ollama import Ollama

class AIInteraction:
    def __init__(self, task_id, config, model_name, timeout=60, multi_thread=False, callback=None):
        self.task_id = task_id
        self.config = config
        self.model_name = model_name
        self.timeout = timeout
        self.multi_thread = multi_thread
        self.callback = callback
        self.api_key = self.check_api_key()

    def check_api_key(self):
        if self.model_name.startswith("Api-"):
            api_detail = external_api(self.model_name)
            api_key = self.config['API_KEY'].get(api_detail['name'], '')
            if api_key == '':
                _log = f"请先申请对应的API_KEY，并填入config.ini文件中"
                print(_log)
                self.callback(_log)
                raise ValueError(_log)
            return api_key

    def query_ai(self, prompt, Summary_prompt):
        """与AI交互"""
        if isinstance(prompt, list):
            if len(prompt) == 1:
                return self._single_query(prompt[0])
            else:
                return self._query_ai_segments(prompt, Summary_prompt)
        return self._single_query(prompt)

    def _single_query(self, prompt, txt_name='content.txt'):
        """单次请求"""
        messages = [{"role": "user", "content": prompt}]
        
        def call_api_with_timeout(api_detail, messages):
            client = OpenAI(
                api_key=self.api_key,
                base_url=api_detail["base_url"]
            )
            future = client.chat.completions.create(
                model=api_detail["data"]["model"],
                messages=messages,
                temperature=api_detail["data"]["temperature"],
                stream=api_detail["data"]["stream"],
            )

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_result = executor.submit(lambda: future)
                try:
                    single_result = future_result.result(timeout=self.timeout).choices[0].message.content
                    with open(os.path.join('./output', str(self.task_id), txt_name), 'w', encoding='utf-8') as f:
                        f.write(single_result)
                    return single_result
                except concurrent.futures.TimeoutError:
                    print(f"请求超过 {self.timeout} 秒未响应，返回空内容")
                    return ""
        
        if self.model_name.startswith("Api-"):
            api_detail = external_api(self.model_name)
            try:
                return call_api_with_timeout(api_detail, messages)
                
            except requests.exceptions.RequestException as e:
                print(f"{api_detail['name']} API 请求失败...")
                print(str(e))
        else:
            data = {
                'model': self.model_name,
                'messages': messages,
                'stream': False,
            }

            try:
                olm = Ollama(callback=self.callback)
                result = olm.chat_with_ollama(data=data)
                return result
            except Exception as e:
                print(f"本地模型请求失败...{str(e)}")

    def _query_ai_segments(self, segments, Summary_prompt):
        """分段请求并汇总结果"""
        if self.multi_thread:
            segment_results_prompt, total_time = self.for_multi_thread(segments)
        else:
            segment_results_prompt, total_time = self.single_thread(segments)

        _log = f"正在处理{len(segments)} 部分的汇总... \t 共计{len(segment_results_prompt)}tokens"
        print(_log)
        self.callback(_log, f"{len(segments)+1}/{len(segments)+1}")
        
        start_time = time.time()  # 记录汇总开始时间
        result = self._single_query(f"{Summary_prompt}\n\n{segment_results_prompt}\n")
        end_time = time.time()  # 记录汇总结束时间
        summary_time = end_time - start_time  # 计算汇总用时
        total_time += summary_time  # 累加总用时

        _log = f"汇总处理完成，用时: {summary_time:.2f} 秒"
        print(_log)
        self.callback(_log, f"{len(segments)+1}/{len(segments)+1}")
        _log = f"整体处理完成，总用时: {total_time:.2f} 秒"
        print(_log)
        self.callback(_log, f"{len(segments)+1}/{len(segments)+1}")

        return result

    def single_thread(self, segments):
        segment_results = []
        total_time = 0  # 用于记录总用时

        for i, segment in enumerate(segments):
            start_time = time.time()  # 记录开始时间
            _log = f"正在处理第 {i+1}/{len(segments)} 部分... \t 共计{len(segment)}tokens"
            print(_log)
            self.callback(_log, f"{i+1}/{len(segments)+1}")
            try:
                response = self._single_query(segment, f'{str(i)}.txt')
                segment_results.append(response)
            except Exception as e:
                print(f"第 {i+1} 部分处理失败: {str(e)}")
                segment_results.append(f"[处理失败] {str(e)}")
            
            end_time = time.time()  # 记录结束时间
            segment_time = end_time - start_time  # 计算当前分段处理时间
            total_time += segment_time  # 累加总用时
            _log = f"第 {i+1} 部分处理完成，用时: {segment_time:.2f} 秒"
            print(_log)
            self.callback(_log, f"{i+1}/{len(segments)+1}")

        segment_results = [str(item) for item in segment_results if item is not None]
        segment_results_prompt = '\n'.join(segment_results)
        return segment_results_prompt, total_time

    def for_multi_thread(self, segments):
        import threading
        import concurrent.futures
        import threading
        from concurrent.futures import ThreadPoolExecutor, TimeoutError

        lock = threading.Lock()
        segment_results = [None] * len(segments)
        total_segments = len(segments)

        with lock:
            self.callback(f"开始处理{total_segments}个分段，等待数据返回……")

        def _process_segment(index, segment):
            start_time = time.time()
            try:
                response = self._single_query(segment, f'{str(index+1)}.txt')
                segment_time = time.time() - start_time

                with lock:
                    _log = f"第 {index+1} 部分处理完成，用时: {segment_time:.2f} 秒"
                    print(_log)
                    self.callback(_log)
                return (index, response, segment_time)
            
            except Exception as e:
                segment_time = time.time() - start_time
                error_msg = f"[处理失败] 第 {index+1} 部分失败: {str(e)}"
                print(error_msg)
                self.callback(error_msg)
                return (index, error_msg, segment_time)

        start_time_total = time.time()
        try:
            with ThreadPoolExecutor(max_workers=min(10, len(segments)//2 + 1)) as executor:
                # 提交所有任务
                futures = [
                    executor.submit(_process_segment, i, seg)
                    for i, seg in enumerate(segments)
                ]

                # 等待所有任务完成或超时
                done, not_done = concurrent.futures.wait(
                    futures, timeout=self.timeout, return_when=concurrent.futures.ALL_COMPLETED
                )

                # 检查是否超时
                # if not_done:
                #     raise TimeoutError(f"请求超时，未完成的分段: {len(not_done)}")

                # 按完成顺序收集结果
                for future in done:
                    index, result, seg_time = future.result()
                    segment_results[index] = result  # 根据索引回填

        except TimeoutError as e:
            # 超时后取消所有未完成的任务
            for future in not_done:
                future.cancel()
            raise TimeoutError(f"请求超时: {str(e)}")

        finally:
            # 计算总耗时
            total_time = time.time() - start_time_total
        # 汇总结果
        segment_results = [str(item) for item in segment_results if item is not None]
        segment_results_prompt = '\n'.join(segment_results)

        return segment_results_prompt, total_time