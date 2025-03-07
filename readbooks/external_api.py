def external_api(api_choice: str):
    api_name_list = api_choice.split('-')
    apis = {
        "Qwen":{
            "name": "Qwen",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "data": {
                "model": "qwen-plus",
                "temperature": 1.5,
                "stream": False
                }
        },
        "Deepseek":{
            "name": "Deepseek",
            "base_url": "https://api.deepseek.com",
            "data": {
                "model": "deepseek-chat",
                "temperature": 1.5,
                "stream": False
                }
        },

    }
    return apis[api_name_list[1]]